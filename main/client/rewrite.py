# 作用：调用 rewrite skill 做指代消解，把用户原问题改成更完整可理解的问题。

from skills.runtime import call_skill, is_llm_ready
from utils import logger
from utils.session_memory import get_completed_turns


SKILL_NAME = "rewrite"
MAX_HISTORY = 3
REQUEST_TIMEOUT = 10.0


def _build_history_prompt(turns, query: str) -> str:
    rows = []
    for turn in turns:
        user_text = turn.get("query", "")
        assistant_text = turn.get("answer", "")
        rows.append(f"A：{user_text}\nB：{assistant_text}" if assistant_text else f"A：{user_text}")

    return "#对话历史#\n{}\nA：{}\n".format("\n".join(rows), query)


def request_rewrite(query, sender_id, trace_id=""):
    """
    只结合 Redis 里还没过期的短期记忆做改写。
    没有可用历史时直接返回原 query。
    """
    turns = get_completed_turns(
        sender_id=sender_id,
        limit=MAX_HISTORY,
        exclude_trace_id=trace_id,
    )

    if not turns:
        result = query
    elif not is_llm_ready():
        logger.error("rewrite skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        result = query
    else:
        prompt = _build_history_prompt(turns, query)
        logger.info(f"对话历史：{prompt}")
        try:
            response = call_skill(
                skill_name=SKILL_NAME,
                user_messages=[{"role": "user", "content": prompt}],
                timeout=REQUEST_TIMEOUT,
                trace_id=trace_id,
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
    return result
