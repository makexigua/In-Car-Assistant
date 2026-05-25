# 作用：调用 arbitration skill，把用户请求分流成 task / faq / chat 三类。

import json
import time

import requests
from main.skills.runtime import call_skill, is_llm_ready
from main.utils import logger
from main.utils.session_memory import build_role_history


SKILL_NAME = "arbitration"
TIMEOUT = 60.0
MAX_HIS = 3
CHUNK_SIZE = 1024


def _extract_code_from_stream(response: requests.Response) -> str:

    code = "A"
    for row in response.iter_lines(chunk_size=CHUNK_SIZE, decode_unicode=False, delimiter=b"\n"):
        line = row.decode("utf-8").strip()
        if not line:
            continue

        line = line.lstrip("data: ").strip()
        if line == "[DONE]":
            break

        try:
            payload = json.loads(line)
        except Exception:
            continue

        text = payload.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if text:
            code = text
            break

    return code


def _to_route(code: str) -> str:
    if code in ["C", "D"]:
        return "chat"
    if code == "B":
        return "faq"
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
        response = call_skill(
            skill_name=SKILL_NAME,
            user_messages=history,
            timeout=TIMEOUT,
            stream_override=True,
            trace_id=trace_id,
        )
        response.raise_for_status()
        code = _extract_code_from_stream(response)
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
