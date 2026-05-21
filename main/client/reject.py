# 作用：调用 reject skill，判断用户问题是否需要拒识。

import re

from main.skills.runtime import call_skill, is_llm_ready
from main.utils import logger


SKILL_NAME = "reject"
REQUEST_TIMEOUT = 5.0


def _normalize_reject_result(text: str) -> str:
    """
    大模型输出统一归一到“是/否”。
    """
    value = (text or "").strip().lower()
    if re.search(r"(否|false|no|reject|非法)", value):
        return "否"
    return "是"


def request_reject(query, trace_id):
    if not is_llm_ready():
        logger.error("reject skill config missing: need LLM_BASE_URL and LLM_API_KEY, default pass.")
        return "是"

    try:
        response = call_skill(
            skill_name=SKILL_NAME,
            user_messages=[{"role": "user", "content": query}],
            timeout=REQUEST_TIMEOUT,
            trace_id=trace_id,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        result = _normalize_reject_result(raw)
        logger.info(f"拒识模型输出：{raw}, normalize:{result}")
        return result
    except Exception as err:
        logger.error(f"call reject skill failed:{err}")
        return "是"


if __name__ == "__main__":
    while True:
        query = input("Input:")
        print(request_reject(query, "123"))
