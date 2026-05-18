# 作用：调用闲聊大模型并把流式返回切帧，供主链路实时下发给前端。

import json
import os
import re

import prompts
import requests
from utils import logger
from utils.env_loader import load_project_env
from utils.redis_tool import RedisClient


MAX_HIS = 6
TTL = 45
REDIS_KEY = "voice:chat_history:{}"
REQUEST_TIMEOUT = 30.0
_redis_client = RedisClient()


load_project_env()
CHAT_API_KEY = os.getenv("CHAT_API_KEY", os.getenv("BOT_API_KEY", os.getenv("LLM_API_KEY", "")))
CHAT_BASE_URL = os.getenv("CHAT_BASE_URL", os.getenv("BOT_BASE_URL", os.getenv("LLM_BASE_URL", "")))
CHAT_MODEL = os.getenv("CHAT_MODEL", os.getenv("BOT_MODEL", os.getenv("DEFAULT_CHAT_MODEL", "")))
SYSTEM_PROMPT = prompts.BOT_CHAT_SYSTEM_PROMPT


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
    if not CHAT_BASE_URL or not CHAT_API_KEY:
        logger.error("chat model config missing: need CHAT_BASE_URL and CHAT_API_KEY.")
        return "N"

    history = _read_history(sender_id) if multiturn else []

    headers = {"Authorization": CHAT_API_KEY, "Content-Type": "application/json"}
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": query}]
    logger.info(f"request message:{messages}")

    data = {"model": CHAT_MODEL, "messages": messages, "stream": True}

    try:
        return requests.post(
            CHAT_BASE_URL,
            headers=headers,
            data=json.dumps(data, ensure_ascii=False),
            stream=True,
            timeout=REQUEST_TIMEOUT,
        )
    except Exception as err:
        logger.error(f"Bot Chat error:{err}")
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

        # 命中常见标点就尽快吐一帧，提升前端可读性。
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
