# 作用：全局共享的 LLM API 客户端单例，避免不同模块各自维护连接，
# 实现全链路 TCP 连接复用（拒识/改写/仲裁/chat/task/RAG 共用同一连接）。

import os
import threading
from typing import Optional

from openai import OpenAI

from main.utils.env_loader import load_project_env

load_project_env()

_LLM_API_KEY = os.getenv("LLM_API_KEY", "").removeprefix("Bearer ").strip()
_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")

_client: Optional[OpenAI] = None
_lock = threading.Lock()


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = OpenAI(
                    api_key=_LLM_API_KEY,
                    base_url=_LLM_BASE_URL,
                    timeout=60.0,
                )
    return _client


def is_llm_ready() -> bool:
    return bool(_LLM_API_KEY and _LLM_BASE_URL)
