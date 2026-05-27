# 作用：基于候选 function 做意图识别和槽位抽取，并输出标准任务解析结果。

import json
from typing import Any, Dict, List, Tuple

from task.execute.slot_normalizer import normalize_slots
from task.llm_client import call_llm_json
from task.settings import CLASS_FILE, FUNCTION_CALL_MODEL


TASK_SYSTEM_PROMPT = (
    "你是车载助手的任务解析器。"
    "你会收到用户输入和候选工具列表，只能从候选工具中选择最匹配的一个函数。"
    "如果用户输入缺少关键对象（比如只说’打开这个’），优先选择 Unknown。"
    "如果输入是百科/闲聊/推荐/翻译/无意义乱序内容，也优先选择 Unknown。"
    "注意：系统支持查天气、导航、搜地点、查路线等在线服务。"
    "当用户问天气、温度、下雨等 → 用 maps_weather。"
    "当用户想要导航、开车路线、怎么去某地 → 用 maps_direction_driving。"
    "当用户问怎么坐公交/地铁 → 用 maps_direction_transit_integrated。"
    "当用户要找景点/餐厅/酒店等地方 → 用 maps_text_search。"
    "当用户要查某地点的开放时间/电话/地址 → 用 maps_search_detail。"
    "当用户要查附近有什么 → 用 maps_around_search。"
)


def _build_intent_maps() -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    id2func: Dict[str, str] = {}
    func2name: Dict[str, str] = {}
    name2id: Dict[str, str] = {}

    with open(CLASS_FILE, "r", encoding="utf-8") as file_obj:
        for raw_line in file_obj:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            intent_id, intent_name, function_name = parts
            id2func[intent_id] = function_name
            func2name.setdefault(function_name, intent_name)
            name2id.setdefault(intent_name, intent_id)
    return id2func, func2name, name2id


ID2FUNC, FUNC2NAME, NAME2ID = _build_intent_maps()


def _parse_tool_call_arguments(raw_args: Any) -> Dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def recognize_intent_and_slots(query: str, candidate_tools: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    if not candidate_tools:
        return "Unknown", {}

    payload = {
        "model": FUNCTION_CALL_MODEL,
        "messages": [
            {"role": "system", "content": TASK_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "tools": candidate_tools,
        "temperature": 1e-6,
        "top_p": 0,
        "tool_choice": "auto",
    }
    data = call_llm_json(payload)
    message = ((data.get("choices") or [{}])[0]).get("message", {})
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return "Unknown", {}

    first_call = tool_calls[0]
    function_obj = first_call.get("function", {})
    function_name = str(function_obj.get("name", "")).strip() or "Unknown"
    raw_slots = _parse_tool_call_arguments(function_obj.get("arguments", "{}"))
    return function_name, normalize_slots(function_name, raw_slots)


def build_task_result(function_name: str, slots: Dict[str, Any], query: str, trace_id: str) -> Dict[str, Any]:
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
