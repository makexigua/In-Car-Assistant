# 作用：调用 arbitration skill，把用户请求分流成 task_vehicle / task_mcp / rag / chat 四类。

import time
from typing import Tuple

from openai import Stream
from openai.types.chat import ChatCompletionChunk
from main.skills.runtime import call_skill, is_llm_ready
from main.utils import logger
from main.utils.session_memory import build_role_history


SKILL_NAME = "arbitration"
TIMEOUT = 60.0
MAX_HIS = 3

VALID_CODES = {"A1", "A2", "B", "C", "D"}


def _extract_code_from_stream(stream: Stream[ChatCompletionChunk]) -> str:
    code = "A2"
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        if content:
            code = content.strip()
            break
    return code


def _to_route(code: str) -> Tuple[str, str]:
    """返回 (route, function_scope)。

    route 用于 start.py 判断走哪条链路（task/rag/chat）。
    function_scope 用于 task pipeline 限定召回范围（local_only/mcp_only/all）。
    """
    if code == "A1":
        return "task", "local_only"
    if code == "A2":
        return "task", "mcp_only"
    if code == "B":
        return "rag", "all"
    return "chat", "all"


def request_arbitration(query, sender_id, trace_id=""):
    if not is_llm_ready():
        logger.error("arbitration skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        return "task", "all"

    start_time = time.time()
    history = build_role_history(
        sender_id=sender_id,
        limit=MAX_HIS,
        exclude_trace_id=trace_id,
    )
    history.append({"role": "user", "content": query})

    try:
        stream = call_skill(
            skill_name=SKILL_NAME,
            user_messages=history,
            timeout=TIMEOUT,
            stream_override=True,
            trace_id=trace_id,
        )
        code = _extract_code_from_stream(stream)
        code = code if code in VALID_CODES else "A2"
        route, function_scope = _to_route(code)
        logger.info(
            f"Arbitration query:{query}, result:{code}, "
            f"route:{route}, scope:{function_scope}, "
            f"cost time:{time.time() - start_time}"
        )
        return route, function_scope
    except Exception as err:
        logger.error(f"Arbitration skill error: {err}")
        return "task", "all"
