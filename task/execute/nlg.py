# 作用：把 task 识别结果和执行结果整理成最终给用户看的自然语言回复。

import json
from typing import Any, Dict

from task.llm_client import call_llm_json
from task.settings import NLG_MODEL


TASK_NLG_PROMPT = (
    "你是车载语音助手，请基于用户问题和工具结果输出简洁、自然、礼貌的中文回复。"
    "要求：\n"
    "1) 回复简洁，不重复。\n"
    "2) 不编造工具结果里没有的信息。\n"
    "3) 如果工具没有有效结果，直接说明当前无法完成，并给一个简短建议。\n"
)


def generate_nlg(query: str, function_name: str, slots: Dict[str, Any], tool_response: Any) -> str:
    tool_response_text = ""
    if tool_response is not None:
        tool_response_text = json.dumps(tool_response, ensure_ascii=False)

    user_content = (
        f"用户问题：{query}\n"
        f"识别函数：{function_name}\n"
        f"槽位：{json.dumps(slots, ensure_ascii=False)}\n"
        f"工具结果：{tool_response_text or '无'}"
    )
    payload = {
        "model": NLG_MODEL,
        "messages": [
            {"role": "system", "content": TASK_NLG_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "top_p": 0.9,
    }
    data = call_llm_json(payload)
    return (((data.get("choices") or [{}])[0]).get("message", {}) or {}).get("content", "").strip()
