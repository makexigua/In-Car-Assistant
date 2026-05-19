# 作用：调用 arbitration skill，把用户请求分流成 task / faq / chat 三类。

import json
import time

import requests
from skills.runtime import call_skill, is_llm_ready
from utils import logger
from utils.redis_tool import RedisClient


SKILL_NAME = "arbitration"
TIMEOUT = 2.0
MAX_HIS = 6
TTL = 60
CHUNK_SIZE = 1024
REDIS_KEY = "voice:arbitration_history:{}"
_redis_client = RedisClient()


def _read_history(sender_id: str):
    history_str = _redis_client.get(REDIS_KEY.format(sender_id))
    if not history_str:
        return []
    try:
        history = json.loads(history_str)
        return history if isinstance(history, list) else []
    except Exception:
        return []


def _extract_code_from_stream(response: requests.Response) -> str:
    """
    仲裁 skill 预期输出 A/B/C/D，这里只取第一段有效内容。
    """
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


def request_arbitration(query, sender_id):
    if not is_llm_ready():
        logger.error("arbitration skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        return "task"

    start_time = time.time()
    history = _read_history(sender_id)
    history.append({"role": "user", "content": query})

    try:
        response = call_skill(
            skill_name=SKILL_NAME,
            user_messages=history,
            timeout=TIMEOUT,
            stream_override=True,
        )
        response.raise_for_status()
        code = _extract_code_from_stream(response)
        if code not in ["A", "B", "C", "D"]:
            code = "A"

        history.append({"role": "assistant", "content": code})
        _redis_client.set(
            REDIS_KEY.format(sender_id),
            json.dumps(history[-MAX_HIS:], ensure_ascii=False),
            ex=TTL,
        )

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
