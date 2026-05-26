# 作用：调用 arbitration skill，把用户请求分流成 task / rag / chat 三类。

import time

from openai import Stream
from openai.types.chat import ChatCompletionChunk
from main.skills.runtime import call_skill, is_llm_ready
from main.utils import logger
from main.utils.session_memory import build_role_history


SKILL_NAME = "arbitration"
TIMEOUT = 60.0
MAX_HIS = 3


def _extract_code_from_stream(stream: Stream[ChatCompletionChunk]) -> str:

    code = "A"
    for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        if content:
            code = content.strip()
            break
    return code


def _to_route(code: str) -> str:
    if code in ["C", "D"]:
        return "chat"
    if code == "B":
        return "rag"
    return "task"


def request_arbitration(query, sender_id, trace_id=""):
    if not is_llm_ready():
        logger.error("arbitration skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        return "task"

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
        if code not in ["A", "B", "C", "D"]:
            code = "A"

        route = _to_route(code)
        logger.info(
            f"Arbitration history: {history}, query:{query}, result:{code}, "
            f"route:{route}, cost time:{time.time() - start_time}"
        )
        return route
    except Exception as err:
        logger.error(f"Arbitration skill error: {err}")
        return "task"


if __name__ == "__main__":
    while True:
        query = input("输入:")
        print(request_arbitration(query, "131"))
