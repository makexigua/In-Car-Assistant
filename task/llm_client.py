# 作用：封装 task 链路对统一大模型 API 的基础调用，供识别和 NLG 复用。

import json
from typing import Any, Dict

import requests

from task.settings import LLM_API_KEY, LLM_BASE_URL, REQUEST_TIMEOUT


def is_llm_ready() -> bool:
    return bool(LLM_BASE_URL and LLM_API_KEY)


def call_llm_json(payload: Dict[str, Any], timeout: float = REQUEST_TIMEOUT) -> Dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": LLM_API_KEY,
    }
    response = requests.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()
