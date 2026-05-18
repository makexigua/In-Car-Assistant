# 作用：调用仲裁大模型，把用户请求分流成 task / faq / chat 三类。

import json
import os
import time

import prompts
import requests
from utils import logger
from utils.env_loader import load_project_env
from utils.redis_tool import RedisClient


TIMEOUT = 2.0
MAX_HIS = 6
TTL = 60
CHUNK_SIZE = 1024
MAX_TOKEN = 2048
REDIS_KEY = "voice:arbitration_history:{}"
_redis_client = RedisClient()


load_project_env()
ARBITRATION_API_KEY = os.getenv("ARBITRATION_API_KEY", os.getenv("LLM_API_KEY", ""))
ARBITRATION_BASE_URL = os.getenv("ARBITRATION_BASE_URL", os.getenv("LLM_BASE_URL", ""))
ARBITRATION_MODEL = os.getenv("ARBITRATION_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
SYSTEM_PROMPT = prompts.ARBITRAION_SYSTEM_PROMPT


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
    流式返回里只取第一个有效字符（A/B/C/D），保持和旧逻辑一致。
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

        delta = payload.get("choices", [{}])[0].get("delta", {})
        text = delta.get("content", "")
        if not text:
            continue
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
    if not ARBITRATION_BASE_URL or not ARBITRATION_API_KEY:
        logger.error("arbitration model config missing: need ARBITRATION_BASE_URL and ARBITRATION_API_KEY.")
        return "task"

    headers = {
        "Content-Type": "application/json",
        "Authorization": ARBITRATION_API_KEY,
    }

    start_time = time.time()
    history = _read_history(sender_id)
    history.append({"role": "user", "content": query})

    body = {
        "model": ARBITRATION_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        "max_tokens": MAX_TOKEN,
        "temperature": 0,
        "stream": True,
    }

    try:
        response = requests.post(
            ARBITRATION_BASE_URL,
            headers=headers,
            json=body,
            stream=True,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        code = _extract_code_from_stream(response)

        if code not in ["A", "B", "C", "D"]:
            code = "A"

        history.append({"role": "assistant", "content": code})
        history_str = json.dumps(history[-MAX_HIS:], ensure_ascii=False)
        _redis_client.set(REDIS_KEY.format(sender_id), history_str, ex=TTL)

        route = _to_route(code)
        logger.info(
            f"Arbitration history: {history}, query:{query}, result:{code}, "
            f"route:{route}, cost time:{time.time() - start_time}"
        )
        return route
    except Exception as err:
        logger.info(f"Arbitration API error: {err}")
        return "task"


if __name__ == "__main__":
    while True:
        query = input("输入:")
        print(request_arbitration(query, "131"))
