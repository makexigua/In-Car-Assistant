# 作用：基于“规则粗召回 + LLM 语义重排”从全量 function 定义里召回最相关的 top-k 候选函数。

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from main.utils import logger
from task.execute.function_registry import FUNCTION_TOOLS
from task.llm_client import call_llm_json, is_llm_ready
from task.settings import FUNCTION_CALL_MODEL


# 规则召回后，交给 LLM 语义重排的候选上限。
RULE_STAGE_LIMIT = 20


@dataclass
class ToolEntry:
    tool_schema: Dict[str, Any]
    function_name: str
    description: str
    search_text: str
    tokens: Set[str]


def _tokenize(text: str) -> Set[str]:
    text = (text or "").strip().lower()
    if not text:
        return set()

    tokens: Set[str] = set()
    chunks = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    for chunk in chunks:
        tokens.add(chunk)
        if re.fullmatch(r"[\u4e00-\u9fff]+", chunk):
            # 中文短句切成单字+双字片段，降低口语表达和配置描述不一致导致的漏召回。
            for char in chunk:
                tokens.add(char)
            for index in range(len(chunk) - 1):
                tokens.add(chunk[index : index + 2])
    return tokens


def _build_tool_entries() -> List[ToolEntry]:
    entries: List[ToolEntry] = []
    for tool in FUNCTION_TOOLS:
        function_meta = tool.get("function", {})
        name = str(function_meta.get("name", "")).strip()
        description = str(function_meta.get("description", "")).strip()
        if not name:
            continue
        # 合并召回关键词（仅用于规则匹配，不传给 LLM）
        recall_kw = tool.get("recall_keywords", "")
        search_text = f"{name} {description}"
        if recall_kw:
            search_text += f" {recall_kw}"
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
    if not query_tokens:
        return 0.0

    overlap = len(query_tokens & entry.tokens)
    coverage = overlap / max(1, len(query_tokens))
    jaccard = overlap / max(1, len(query_tokens | entry.tokens))
    string_ratio = SequenceMatcher(None, query, entry.search_text).ratio()
    return 0.55 * coverage + 0.25 * jaccard + 0.20 * string_ratio


def _build_rule_candidates(query_text: str, top_k: int) -> List[ToolEntry]:
    query_tokens = _tokenize(query_text)
    if not query_tokens:
        return []

    scored: List[Tuple[float, ToolEntry]] = []
    for entry in ALL_TOOL_ENTRIES:
        scored.append((_score_tool(query_text, query_tokens, entry), entry))
    scored.sort(key=lambda item: item[0], reverse=True)

    # 候选池放大后再语义重排，通常比直接规则 top-k 更稳。
    stage_limit = min(len(scored), max(RULE_STAGE_LIMIT, max(1, top_k) * 4))
    candidates: List[ToolEntry] = []
    selected_names: Set[str] = set()
    for _, entry in scored:
        if entry.function_name in selected_names:
            continue
        candidates.append(entry)
        selected_names.add(entry.function_name)
        if len(candidates) >= stage_limit:
            break
    return candidates


def _extract_message_text(message: Dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    text_obj = item.get("text")
                    if isinstance(text_obj, dict):
                        parts.append(str(text_obj.get("value", "")))
                    else:
                        parts.append(str(text_obj))
        return "\n".join([part for part in parts if part]).strip()
    return ""


def _parse_ranked_names(raw_text: str) -> List[str]:
    text = (raw_text or "").strip()
    if not text:
        return []

    # 先尝试整段 JSON，再尝试提取第一个 JSON 对象，兼容模型偶发多余解释文本。
    json_candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        json_candidates.append(match.group(0))

    for candidate in json_candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        ranked = parsed.get("ranked_names")
        if isinstance(ranked, list):
            return [str(name).strip() for name in ranked if str(name).strip()]
    return []


def _build_rerank_payload(query: str, candidates: List[ToolEntry]) -> Dict[str, Any]:
    candidate_rows = []
    for idx, entry in enumerate(candidates, start=1):
        candidate_rows.append(
            {
                "index": idx,
                "function_name": entry.function_name,
                "description": entry.description,
            }
        )

    system_prompt = (
        "你是车载 Agent 的召回重排器。"
        "你只做一件事：根据用户 query 的语义相关性，从候选函数里挑最相关的函数名排序。"
        "禁止输出解释，只能输出 JSON。"
        "输出格式严格为：{\"ranked_names\": [\"func_a\", \"func_b\", \"func_c\"]}"
    )

    user_prompt = json.dumps(
        {"query": query, "candidates": candidate_rows},
        ensure_ascii=False,
    )

    return {
        "model": FUNCTION_CALL_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 1e-6,
        "top_p": 0,
    }


def _llm_rerank(query: str, candidates: List[ToolEntry], top_k: int) -> Optional[List[ToolEntry]]:
    if not candidates:
        return None
    if not is_llm_ready():
        return None
    if not FUNCTION_CALL_MODEL:
        return None

    try:
        payload = _build_rerank_payload(query, candidates)
        data = call_llm_json(payload)
        message = ((data.get("choices") or [{}])[0]).get("message", {})
        ranked_names = _parse_ranked_names(_extract_message_text(message))
    except Exception as err:
        logger.warning(f"task recall llm rerank failed, fallback to rules: {err}")
        return None

    if not ranked_names:
        return None

    candidate_map = {entry.function_name: entry for entry in candidates}
    result: List[ToolEntry] = []
    selected_names: Set[str] = set()
    for name in ranked_names:
        if name in selected_names:
            continue
        entry = candidate_map.get(name)
        if entry is None:
            continue
        result.append(entry)
        selected_names.add(name)
        if len(result) >= max(1, top_k):
            return result

    # LLM 输出不满 top_k 时，按规则顺序补齐，保证稳定返回数量。
    for entry in candidates:
        if entry.function_name in selected_names:
            continue
        result.append(entry)
        selected_names.add(entry.function_name)
        if len(result) >= max(1, top_k):
            break
    return result


def recall_top_tools(query: str, top_k: int) -> List[Dict[str, Any]]:
    query_text = (query or "").strip().lower()
    if not query_text:
        return []

    rule_candidates = _build_rule_candidates(query_text, top_k)
    if not rule_candidates:
        return []

    reranked = _llm_rerank(query_text, rule_candidates, top_k)
    final_entries = reranked if reranked else rule_candidates[: max(1, top_k)]

    selected = [entry.tool_schema for entry in final_entries[: max(1, top_k)]]
    # 剥离召回专用字段，避免传给 LLM
    for tool in selected:
        tool.pop("recall_keywords", None)
    logger.info(
        f"task recall top{top_k}: {[tool.get('function', {}).get('name') for tool in selected]}"
    )
    return selected
