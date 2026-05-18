# 作用：调用改写大模型做指代消解，把用户原问题改成更完整可理解的问题。

import json
import os

import prompts
import requests
from utils import logger
from utils.env_loader import load_project_env
from utils.redis_tool import RedisClient


TTL = 40
MAX_HISTORY = 6
REDIS_KEY = "voice:rewrite_history:{}"
REQUEST_TIMEOUT = 8.0
_redis_client = RedisClient()


load_project_env()
REWRITE_API_KEY = os.getenv("REWRITE_API_KEY", os.getenv("LLM_API_KEY", ""))
REWRITE_BASE_URL = os.getenv("REWRITE_BASE_URL", os.getenv("LLM_BASE_URL", ""))
REWRITE_MODEL = os.getenv("REWRITE_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))


def _read_history(sender_id: str):
    history_str = _redis_client.get(REDIS_KEY.format(sender_id))
    if not history_str:
        return []
    try:
        history = json.loads(history_str)
        return history if isinstance(history, list) else []
    except Exception:
        return []


def _build_history_prompt(history, query: str) -> str:
    split_history = [history[i : i + 2] for i in range(0, len(history), 2)]
    rows = []

    for item in split_history:
        user_text = item[0].get("content", "") if item else ""
        assistant_text = item[1].get("content", "") if len(item) > 1 else ""
        if assistant_text:
            rows.append(f"A：{user_text}\nB：{assistant_text}")
        else:
            rows.append(f"A：{user_text}")

    return "#对话历史#\n{}\nA：{}\n".format("\n".join(rows), query)


def request_rewrite(query, last_answer, sender_id):
    """
    有历史上下文才调用改写模型，没有历史就直接返回原 query。
    """
    history = _read_history(sender_id)[-MAX_HISTORY:]

    # 上一轮缓存里 assistant 可能是空串，这里用主链路计算出的回答补齐。
    if history and last_answer:
        history[-1]["content"] = last_answer

    if not history:
        result = query
    elif not REWRITE_BASE_URL or not REWRITE_API_KEY:
        logger.error("rewrite model config missing: need REWRITE_BASE_URL and REWRITE_API_KEY.")
        result = query
    else:
        prompt = _build_history_prompt(history, query)
        logger.info(f"对话历史：{prompt}")

        data = {
            "model": REWRITE_MODEL,
            "messages": [
                {"role": "system", "content": prompts.REWRITE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.001,
            "top_p": 0,
        }
        headers = {"Authorization": REWRITE_API_KEY, "Content-Type": "application/json"}

        try:
            response = requests.post(
                REWRITE_BASE_URL,
                headers=headers,
                data=json.dumps(data, ensure_ascii=False),
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]

            # 防止误改过大：如果和原句重叠过少，就回退到原句。
            if len(set(result).intersection(query)) < len(query) / 4:
                result = query
        except Exception as err:
            logger.error(f"call rewrite failed:{err}")
            result = query

    logger.info(f"改写后：{result}")

    history.append({"role": "user", "content": result})
    history.append({"role": "assistant", "content": ""})
    _redis_client.set(REDIS_KEY.format(sender_id), json.dumps(history, ensure_ascii=False), ex=TTL)
    return result
