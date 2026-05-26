# 作用：封装 task 链路对统一大模型 API 的基础调用，供识别和 NLG 复用。

import os
from typing import Any, Dict

from openai import OpenAI

from task.settings import REQUEST_TIMEOUT


_LLM_API_KEY = os.getenv("LLM_API_KEY", "").removeprefix("Bearer ").strip()
_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")

# OpenAI SDK 兼容的请求参数白名单
_OPENAI_PARAMS = frozenset({
    "model", "messages", "temperature", "top_p", "max_tokens", "stream",
    "stop", "frequency_penalty", "presence_penalty", "seed",
    "tools", "tool_choice", "tool_calls",
})


def is_llm_ready() -> bool:
    return bool(_LLM_API_KEY and _LLM_BASE_URL)


def call_llm_json(payload: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    valid_params = {k: v for k, v in payload.items() if k in _OPENAI_PARAMS and v is not None}
    client = OpenAI(api_key=_LLM_API_KEY, base_url=_LLM_BASE_URL, timeout=timeout)
    response = client.chat.completions.create(**valid_params)
    return response.model_dump()
