# 作用：封装 chat skill 调用与流式切帧逻辑，供主链路做闲聊兜底输出。

import re

from main.skills.runtime import call_skill, is_llm_ready
from main.utils import logger
from main.utils.session_memory import build_role_history


SKILL_NAME = "chat"
MAX_HIS = 3
REQUEST_TIMEOUT = 60.0


def request_chat(query, sender_id, trace_id="", multiturn=True):
    if not is_llm_ready():
        logger.error("chat skill config missing: need LLM_BASE_URL and LLM_API_KEY.")
        return "N"

    history = (
        build_role_history(
            sender_id=sender_id,
            limit=MAX_HIS,
            exclude_trace_id=trace_id,
        )
        if multiturn
        else []
    )
    messages = history + [{"role": "user", "content": query}]
    logger.info(f"request message:{messages}")

    try:
        return call_skill(
            skill_name=SKILL_NAME,
            user_messages=messages,
            timeout=REQUEST_TIMEOUT,
            stream_override=True,
            trace_id=trace_id,
        )
    except Exception as err:
        logger.error(f"chat skill error:{err}")
        return "N"


def process_chat(stream, query, sender_id):
    if stream is None:
        yield "抱歉，此为敏感信息，请您换个问题"
        return

    if stream == "N":
        yield "抱歉，网络有点问题，请您再试一下"
        return

    counter = 1
    chunk_text = ""
    answer = ""

    for chunk in stream:
        if chunk.choices[0].finish_reason == "stop":
            break

        text = chunk.choices[0].delta.content or ""
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


if __name__ == "__main__":
    while True:
        query = input("-->")
        res = request_chat(query, "1", multiturn=True)
        for frame in process_chat(res, query, "1"):
            print(frame)
