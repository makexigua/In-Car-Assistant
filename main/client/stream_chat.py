# 作用：调用 chat skill 并把流式返回切帧，供主链路实时下发给前端。

import json
import re

from skills.runtime import call_skill, is_llm_ready
from utils import logger
from utils.redis_tool import RedisClient


SKILL_NAME = "chat"
MAX_HIS = 6
TTL = 45
REQUEST_TIMEOUT = 30.0
REDIS_KEY = "voice:chat_history:{}"
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


def request_chat(query, sender_id, multiturn=True):
    if not is_llm_ready():
        logger.error("chat skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        return "N"

    history = _read_history(sender_id) if multiturn else []
    messages = history + [{"role": "user", "content": query}]
    logger.info(f"request message:{messages}")

    try:
        return call_skill(
            skill_name=SKILL_NAME,
            user_messages=messages,
            timeout=REQUEST_TIMEOUT,
            stream_override=True,
        )
    except Exception as err:
        logger.error(f"chat skill error:{err}")
        return "N"


def process_chat(response, query, sender_id):
    if response is None:
        yield "抱歉，此为敏感信息，请您换个问题"
        return

    if response == "N":
        yield "抱歉，网络有点问题，请您再试一下"
        return

    counter = 1
    chunk_text = ""
    answer = ""

    for row in response.iter_lines(chunk_size=1, decode_unicode=False, delimiter=b"\n"):
        line = row.decode("utf-8").strip()
        if not line:
            continue

        try:
            payload = json.loads(line.lstrip("data: "))
        except Exception:
            continue

        if payload.get("choices", [{}])[0].get("finish_reason", {}) == "stop":
            break

        text = payload.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if not text:
            continue

        chunk_text += text
        answer += text

        # 命中常见标点尽快吐帧，前端感知会更顺滑。
        if re.search("，|。|？|；", text):
            yield chunk_text
            chunk_text = ""
            counter = 1

        if counter % 5 == 0 and chunk_text:
            yield chunk_text
            chunk_text = ""

        counter += 1

    if chunk_text.strip():
        yield chunk_text

    logger.info(f"bot_Chat Result: {answer}")
    history = _read_history(sender_id)
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": answer})
    _redis_client.set(REDIS_KEY.format(sender_id), json.dumps(history[-MAX_HIS:], ensure_ascii=False), ex=TTL)


if __name__ == "__main__":
    while True:
        query = input("-->")
        res = request_chat(query, "1", True)
        for frame in process_chat(res, query, "1"):
            print(frame)
