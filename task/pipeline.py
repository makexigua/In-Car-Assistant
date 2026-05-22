# 作用：串联 task 主流程：意图召回 -> 意图识别/槽位抽取 -> 本地或 MCP 执行 -> NLG。

import time
from typing import Any, Dict, Optional

from main.utils import logger
from task.execute.local_executor import build_local_action
from task.execute.mcp_executor import execute_mcp_function, is_mcp_function
from task.execute.nlg import generate_nlg
from task.intent.recall import recall_top_tools
from task.intent.recognize import build_task_result, recognize_intent_and_slots
from task.llm_client import is_llm_ready
from task.settings import DEFAULT_NLG, RECALL_TOP_K


def _build_fallback_result(query: str, trace_id: str, begin: float) -> Dict[str, Any]:
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


def _dispatch_execution(function_name: str, slots: Dict[str, Any], enable_mcp: bool) -> Dict[str, Any]:
    if enable_mcp and is_mcp_function(function_name):
        mcp_result = execute_mcp_function(function_name, slots)
        if mcp_result is not None:
            return mcp_result

    local_action = build_local_action(function_name, slots)
    if local_action is None:
        return {"executor": "none", "tool": None}
    return {"executor": "local", "tool": local_action}


def run_task_pipeline(query: str, trace_id: str, enable_dm: bool = True) -> Dict[str, Any]:
    begin = time.time()

    if not is_llm_ready():
        logger.error("task pipeline config missing: LLM_BASE_URL or LLM_API_KEY is empty")
        return _build_fallback_result(query, trace_id, begin)

    try:
        candidate_tools = recall_top_tools(query, RECALL_TOP_K)
        function_name, slots = recognize_intent_and_slots(query, candidate_tools)
        result = build_task_result(function_name, slots, query, trace_id)

        execution = _dispatch_execution(function_name, slots, enable_dm)
        result["executor"] = execution.get("executor", "none")

        tool_response: Optional[Any] = execution.get("tool")
        if tool_response is not None:
            result["tool"] = tool_response

        nlg_text = generate_nlg(query, function_name, slots, tool_response)
        result["nlg"] = nlg_text or DEFAULT_NLG
        result["cost"] = time.time() - begin
        return result

    except Exception as err:
        logger.error(f"run_task_pipeline failed: {err}")
        return _build_fallback_result(query, trace_id, begin)
