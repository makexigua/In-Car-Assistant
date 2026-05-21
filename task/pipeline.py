# 作用：在主进程内执行 task 链路（意图召回、function calling、MCP 调用、NLG 生成），不再依赖本地 NLU HTTP 服务。

import asyncio
import json
import os
import re
import time
from datetime import datetime
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from sinan import Sinan

from main.utils import logger
from main.utils.env_loader import load_project_env
from task.function_call.function import tools1
from task.mcp_core.mcp_client import MCPClient


load_project_env()
TASK_DIR = Path(__file__).resolve().parent

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
FUNCTION_CALL_MODEL = os.getenv("FUNCTION_CALL_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
NLG_MODEL = os.getenv("NLG_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
REQUEST_TIMEOUT = float(os.getenv("TASK_LLM_TIMEOUT", "12"))
RECALL_TOP_K = int(os.getenv("TASK_RECALL_TOP_K", "5"))
DEFAULT_NLG = os.getenv("DEFAULT_NLG", "抱歉，这个问题我还在学习中")

CLASS_FILE = TASK_DIR / "config" / "class.txt"
SLOT_INTENT_FILE = TASK_DIR / "config" / "slot_intent.json"
AMP_SERVER_PATH = str(TASK_DIR / "mcp_core" / "amp_server.py")
MUSIC_SERVER_PATH = str(TASK_DIR / "mcp_core" / "music_server.py")

# 这个系统提示词用于“意图确认 + 槽位抽取”，和原 task 服务保持同一目标。
TASK_SYSTEM_PROMPT = (
    "你是车载助手的任务解析器。"
    "你会收到用户输入和候选工具列表，只能从候选工具中选择最匹配的一个函数。"
    "如果用户输入缺少关键对象（比如只说‘打开这个’），优先选择 Unknown。"
    "如果输入是百科/闲聊/推荐/翻译/无意义乱序内容，也优先选择 Unknown。"
)

# 这个提示词用于最终 NLG：把工具结果转成对用户更自然的一句话或几句话。
TASK_NLG_PROMPT = (
    "你是车载语音助手，请基于用户问题和工具结果输出简洁、自然、礼貌的中文回复。"
    "要求：\n"
    "1) 回复简洁，不重复。\n"
    "2) 不编造工具结果里没有的信息。\n"
    "3) 如果工具没有有效结果，直接说明当前无法完成，并给一个简短建议。\n"
)


@dataclass
class ToolEntry:
    tool_schema: Dict[str, Any]
    function_name: str
    description: str
    search_text: str
    tokens: Set[str]


def _build_intent_maps() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    读取 class.txt，建立三个映射：
    1) id -> function
    2) function -> 中文意图名
    3) 中文意图名 -> id
    """
    id2func: Dict[str, str] = {}
    func2name: Dict[str, str] = {}
    name2id: Dict[str, str] = {}

    with open(CLASS_FILE, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            intent_id, intent_name, func_name = parts
            id2func[intent_id] = func_name
            # 重名时保留第一次，避免后续被覆盖导致结果漂移。
            func2name.setdefault(func_name, intent_name)
            name2id.setdefault(intent_name, intent_id)
    return id2func, func2name, name2id


ID2FUNC, FUNC2NAME, NAME2ID = _build_intent_maps()
SLOT_MAP = json.loads(SLOT_INTENT_FILE.read_text(encoding="utf-8"))

POSITION_MAP = {
    "主驾": "MAIN",
    "副驾": "VICE",
    "左侧": "LEFT",
    "右侧": "RIGHT",
    "前排": "FRONT",
    "后排": "REAR",
    "左后": "LEFT_REAR",
    "右后": "RIGHT_REAR",
    "主对角": "MAIN_DIAGONAL",
    "副对角": "VICE_DIAGONAL",
    "所有": "ALL",
    "吹脚": "FOOT",
    "吹脸": "FACE",
    "吹窗": "WINDOW",
    "吹脸吹脚": "FACE_AND_FOOT",
    "吹窗吹脚": "WINDOW_AND_FOOT",
    "左前": "MAIN",
    "右前": "VICE",
    "主副驾": "FRONT",
}


def _tokenize(text: str) -> Set[str]:
    """
    轻量 tokenizer：不依赖额外服务，兼容中英文。
    - 英文/数字按词切分
    - 中文按连续片段切分，并补充单字和双字片段
    """
    text = (text or "").strip().lower()
    if not text:
        return set()

    tokens: Set[str] = set()
    chunks = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    for chunk in chunks:
        tokens.add(chunk)
        # 连续中文片段再拆单字和双字，提高短 query 召回稳定性。
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
            for c in chunk:
                tokens.add(c)
            for i in range(len(chunk) - 1):
                tokens.add(chunk[i : i + 2])
    return tokens


def _build_tool_entries() -> List[ToolEntry]:
    entries: List[ToolEntry] = []
    for tool in tools1:
        func = tool.get("function", {})
        name = str(func.get("name", "")).strip()
        description = str(func.get("description", "")).strip()
        if not name:
            continue
        # 把函数名和描述一起作为召回语料。
        search_text = f"{name} {description}"
        entries.append(
            ToolEntry(
                tool_schema=tool,
                function_name=name,
                description=description,
                search_text=search_text,
                tokens=_tokenize(search_text),
            )
        )
    return entries


ALL_TOOL_ENTRIES = _build_tool_entries()


def _score_tool(query: str, query_tokens: Set[str], entry: ToolEntry) -> float:
    """
    打分由三部分组成：
    1) query-token 覆盖率（主权重）
    2) Jaccard（防止长描述虚高）
    3) 字符串相似度（补偿词法不完全重合）
    """
    if not query_tokens:
        return 0.0

    overlap = len(query_tokens & entry.tokens)
    coverage = overlap / max(1, len(query_tokens))
    jaccard = overlap / max(1, len(query_tokens | entry.tokens))
    string_ratio = SequenceMatcher(None, query, entry.search_text).ratio()
    return 0.55 * coverage + 0.25 * jaccard + 0.20 * string_ratio


def recall_top_tools(query: str, top_k: int = RECALL_TOP_K) -> List[Dict[str, Any]]:
    """
    从全部 function 里召回最相关 top-k。
    为了避免同名函数重复占位，会按 function_name 去重。
    """
    query_text = (query or "").strip().lower()
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []

    scored: List[Tuple[float, ToolEntry]] = []
    for entry in ALL_TOOL_ENTRIES:
        score = _score_tool(query_text, query_tokens, entry)
        scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)

    selected: List[Dict[str, Any]] = []
    selected_names: Set[str] = set()
    for score, entry in scored:
        if entry.function_name in selected_names:
            continue
        selected.append(entry.tool_schema)
        selected_names.add(entry.function_name)
        if len(selected) >= max(1, top_k):
            break

    logger.info(
        f"task recall top{top_k}: {[t.get('function', {}).get('name') for t in selected]}"
    )
    return selected


def _build_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": LLM_API_KEY,
    }


def _call_llm(payload: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    response = requests.post(
        LLM_BASE_URL,
        headers=_build_headers(),
        data=json.dumps(payload, ensure_ascii=False),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _safe_json_loads(text: Any) -> Any:
    if isinstance(text, (dict, list)):
        return text
    if not isinstance(text, str):
        return text
    raw = text.strip()
    if not raw:
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def _parse_tool_call_arguments(raw_args: Any) -> Dict[str, Any]:
    """
    LLM 的 function arguments 在不同网关里可能是 dict 或 JSON 字符串，这里统一做容错解析。
    """
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            if isinstance(parsed, dict):
                return parsed
            return {}
        except Exception:
            return {}
    return {}


def _safe_to_float(raw_value: str) -> Optional[float]:
    """
    只做受控数字解析，不用 eval，避免把任意表达式喂给解释器。
    """
    value = (raw_value or "").strip()
    if not value:
        return None

    # 允许纯数字、小数和简单分数写法，例如 1/2。
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return float(value)
    if re.fullmatch(r"-?\d+(\.\d+)?/-?\d+(\.\d+)?", value):
        left, right = value.split("/", 1)
        denominator = float(right)
        if denominator == 0:
            return None
        return float(left) / denominator
    return None


def _normalize_slot_value(slot_key: str, slot_value: Any) -> Any:
    """
    兼容旧 task 链路的槽位值归一化逻辑。
    """
    if slot_value is None:
        return slot_value

    value = str(slot_value).strip()
    if not value:
        return value

    key_lower = slot_key.lower()
    if key_lower in {"number", "ratio"}:
        if "%" in value:
            number = _safe_to_float(value.replace("%", ""))
            return number / 100 if number is not None else value
        number = _safe_to_float(value)
        return number if number is not None else value

    if slot_key in {"POSITION", "位置"}:
        return POSITION_MAP.get(value, value)

    if slot_key == "对话时长":
        return value.replace("秒", "")

    if slot_key == "Extreme":
        if value in {"最大", "最高", "最强", "最亮", "最热"}:
            return "最大"
        if value in {"最小", "最低", "最弱", "最暗", "最冷"}:
            return "最小"

    return value


def _normalize_slots(function_name: str, raw_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    兼容旧 slot_process.py：
    1) 先按 slot_intent.json 做槽位名映射
    2) 再做数值/位置/极值归一化
    """
    if not isinstance(raw_slots, dict):
        return {}

    slot_rules = SLOT_MAP.get(function_name)
    normalized: Dict[str, Any] = {}
    for raw_key, raw_value in raw_slots.items():
        if raw_value in (None, "", "不限"):
            continue

        mapped_key = raw_key
        if isinstance(slot_rules, dict):
            mapped_key = slot_rules.get(raw_key, raw_key)

        normalized[mapped_key] = _normalize_slot_value(mapped_key, raw_value)
    return normalized


def _normalize_nlu_result(function_name: str, slots: Dict[str, Any], query: str, trace_id: str) -> Dict[str, Any]:
    intent_name = FUNC2NAME.get(function_name, "未知")
    intent_id = NAME2ID.get(intent_name, "")
    return {
        "query": query,
        "trace_id": trace_id,
        "intent": intent_name,
        "intent_id": intent_id,
        "function": function_name,
        "slots": slots,
    }


def _function_call_infer(query: str, tools: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    """
    用全局同一套 LLM API 做 function calling：
    - 入参为 top-k 候选 tools
    - 输出 function_name + slots
    """
    if not tools:
        return "Unknown", {}

    payload = {
        "model": FUNCTION_CALL_MODEL,
        "messages": [
            {"role": "system", "content": TASK_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "tools": tools,
        "temperature": 1e-6,
        "top_p": 0,
        # 明确要求走函数选择，降低“直接闲聊文本”概率。
        "tool_choice": "auto",
    }
    data = _call_llm(payload)
    message = ((data.get("choices") or [{}])[0]).get("message", {})
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return "Unknown", {}

    first_call = tool_calls[0]
    function_obj = first_call.get("function", {})
    function_name = str(function_obj.get("name", "")).strip() or "Unknown"
    raw_slots = _parse_tool_call_arguments(function_obj.get("arguments", "{}"))
    slots = _normalize_slots(function_name, raw_slots)
    return function_name, slots


async def _call_mcp_tool(server_path: str, function_name: str, tool_args: Dict[str, Any]) -> Any:
    """
    单次 MCP 调用：连接 -> 调工具 -> 清理。
    这样不会在服务里残留长期子进程。
    """
    client = MCPClient()
    try:
        await client.connect_to_server(server_path)
        response_text = await client.execute(function_name, tool_args)
        return _safe_json_loads(response_text)
    finally:
        await client.cleanup()


def _run_async(coro: Any) -> Any:
    """
    统一执行协程。主流程是同步函数，所以这里桥接 asyncio。
    """
    try:
        return asyncio.run(coro)
    except RuntimeError as err:
        # 少数运行环境里当前线程可能已经有 event loop，这里做兜底。
        if "asyncio.run() cannot be called from a running event loop" not in str(err):
            raise
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _try_call_mcp(function_name: str, slots: Dict[str, Any]) -> Optional[Any]:
    """
    只对已定义的 MCP 场景做调用：
    - 天气：Query_Weather / Query_Timely_Weather -> maps_weather
    - 地图：Go_POI -> maps_text_search
    - 音乐：Search_Music -> search_music
    """
    if function_name in {"Query_Weather", "Query_Timely_Weather"}:
        city = str(slots.get("city", "北京") or "北京")
        date = str(slots.get("date", "")).strip()
        if date:
            try:
                date_parsed = Sinan(date).parse()
                if "datetime" in date_parsed:
                    date = date_parsed["datetime"][0].split(" ")[0]
            except Exception as err:
                logger.error(f"weather date parse failed: {err}")
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        return _run_async(
            _call_mcp_tool(
                server_path=AMP_SERVER_PATH,
                function_name="maps_weather",
                tool_args={"city": city, "date": date},
            )
        )

    if function_name == "Go_POI":
        keyword_parts: List[str] = []
        for key in ("city", "landmark", "POI"):
            value = str(slots.get(key, "")).strip()
            if value:
                keyword_parts.append(value)
        keyword = "".join(keyword_parts).strip()
        if not keyword:
            keyword = "附近"
        tool_args: Dict[str, Any] = {"keywords": keyword}
        city_value = str(slots.get("city", "")).strip()
        if city_value:
            tool_args["city"] = city_value
        return _run_async(
            _call_mcp_tool(
                server_path=AMP_SERVER_PATH,
                function_name="maps_text_search",
                tool_args=tool_args,
            )
        )

    if function_name == "Search_Music":
        keyword = " ".join([str(v) for v in slots.values() if str(v).strip()]).strip()
        if not keyword:
            keyword = "流行"
        return _run_async(
            _call_mcp_tool(
                server_path=MUSIC_SERVER_PATH,
                function_name="search_music",
                tool_args={"keyword": keyword, "page": 1, "num": 3},
            )
        )

    return None


def _generate_nlg(query: str, function_name: str, slots: Dict[str, Any], tool_response: Any) -> str:
    """
    统一 NLG：
    - 有工具结果时，带上结构化结果
    - 没工具结果时，也给出任务识别结果解释
    """
    tool_response_text = ""
    if tool_response is not None:
        tool_response_text = json.dumps(tool_response, ensure_ascii=False)

    user_content = (
        f"用户问题：{query}\n"
        f"识别函数：{function_name}\n"
        f"槽位：{json.dumps(slots, ensure_ascii=False)}\n"
        f"工具结果：{tool_response_text or '无'}"
    )
    payload = {
        "model": NLG_MODEL,
        "messages": [
            {"role": "system", "content": TASK_NLG_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
    }
    data = _call_llm(payload)
    return (((data.get("choices") or [{}])[0]).get("message", {}) or {}).get("content", "").strip()


def run_task_pipeline(query: str, trace_id: str, enable_dm: bool = True) -> Dict[str, Any]:

    begin = time.time()

    if not LLM_BASE_URL or not LLM_API_KEY:
        logger.error("task pipeline config missing: LLM_BASE_URL or LLM_API_KEY is empty")
        return {
            "query": query,
            "trace_id": trace_id,
            "intent": "未知",
            "intent_id": "",
            "function": "Unknown",
            "slots": {},
            "nlg": DEFAULT_NLG,
            "cost": time.time() - begin,
        }

    try:
        # 1) 召回 top-5 候选 function
        candidate_tools = recall_top_tools(query, RECALL_TOP_K)

        # 2) 大模型做意图确认 + 槽位抽取
        function_name, slots = _function_call_infer(query, candidate_tools)
        result = _normalize_nlu_result(function_name, slots, query, trace_id)

        # 3) 命中 MCP 场景时，调用 MCP 工具
        tool_response: Optional[Any] = None
        if enable_dm:
            tool_response = _try_call_mcp(function_name, slots)
            if tool_response is not None:
                result["tool"] = tool_response

        # 4) 统一 NLG 输出
        nlg_text = _generate_nlg(query, function_name, slots, tool_response)
        if not nlg_text:
            nlg_text = DEFAULT_NLG
        result["nlg"] = nlg_text
        result["cost"] = time.time() - begin
        return result

    except Exception as err:
        logger.error(f"run_task_pipeline failed: {err}")
        return {
            "query": query,
            "trace_id": trace_id,
            "intent": "未知",
            "intent_id": "",
            "function": "Unknown",
            "slots": {},
            "nlg": DEFAULT_NLG,
            "cost": time.time() - begin,
        }
