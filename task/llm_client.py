# 作用：封装 task 链路对统一大模型 API 的基础调用，供识别和 NLG 复用。

import os
from typing import Any, Dict

from main.utils.llm_client import get_llm_client, is_llm_ready  # re-export is_llm_ready, used by task/pipeline.py and task/intent/recall.py

from task.settings import REQUEST_TIMEOUT

# OpenAI SDK 兼容的请求参数白名单
_OPENAI_PARAMS = frozenset({
    "model", "messages", "temperature", "top_p", "max_tokens", "stream",
    "stop", "frequency_penalty", "presence_penalty", "seed",
    "tools", "tool_choice", "tool_calls",
})


def call_llm_json(payload: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    valid_params = {k: v for k, v in payload.items() if k in _OPENAI_PARAMS and v is not None}
    client = get_llm_client()
    response = client.chat.completions.create(**valid_params)
    return response.model_dump()
