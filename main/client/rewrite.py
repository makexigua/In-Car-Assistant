# 作用：调用 rewrite skill 做指代消解，把用户原问题改成更完整可理解的问题。

import json

from skills.runtime import call_skill, is_llm_ready
from utils import logger
from utils.redis_tool import RedisClient


SKILL_NAME = "rewrite"
TTL = 40
MAX_HISTORY = 6
REQUEST_TIMEOUT = 8.0
REDIS_KEY = "voice:rewrite_history:{}"
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


def _build_history_prompt(history, query: str) -> str:
    split_history = [history[i : i + 2] for i in range(0, len(history), 2)]
    rows = []
    for item in split_history:
        user_text = item[0].get("content", "") if item else ""
        assistant_text = item[1].get("content", "") if len(item) > 1 else ""
        rows.append(f"A：{user_text}\nB：{assistant_text}" if assistant_text else f"A：{user_text}")

    return "#对话历史#\n{}\nA：{}\n".format("\n".join(rows), query)


def request_rewrite(query, last_answer, sender_id):
    """
    有历史上下文才调用改写 skill，没有历史直接返回原 query。
    """
    history = _read_history(sender_id)[-MAX_HISTORY:]

    # 上一轮缓存里 assistant 可能是空串，这里用主链路回答补齐。
    if history and last_answer:
        history[-1]["content"] = last_answer

    if not history:
        result = query
    elif not is_llm_ready():
        logger.error("rewrite skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        result = query
    else:
        prompt = _build_history_prompt(history, query)
        logger.info(f"对话历史：{prompt}")
        try:
            response = call_skill(
                skill_name=SKILL_NAME,
                user_messages=[{"role": "user", "content": prompt}],
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]

            # 防止误改过大：和原句重叠过少则回退。
            if len(set(result).intersection(query)) < len(query) / 4:
                result = query
        except Exception as err:
            logger.error(f"call rewrite skill failed:{err}")
            result = query

    logger.info(f"改写后：{result}")

    history.append({"role": "user", "content": result})
    history.append({"role": "assistant", "content": ""})
    _redis_client.set(REDIS_KEY.format(sender_id), json.dumps(history, ensure_ascii=False), ex=TTL)
    return result
