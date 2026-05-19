# 作用：统一加载 skill 配置，并通过同一个大模型 API 执行 skill。

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yaml

from utils.env_loader import load_project_env


load_project_env()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
SKILL_CONFIG_DIR = Path(__file__).resolve().parent / "config"


def is_llm_ready() -> bool:
    """
    判断统一大模型配置是否完整。
    """
    return bool(LLM_API_KEY and LLM_BASE_URL)


@lru_cache(maxsize=64)
def load_skill(skill_name: str) -> Dict[str, Any]:
    """
    读取并缓存单个 skill 配置，避免每次请求都读磁盘。
    """
    skill_path = SKILL_CONFIG_DIR / f"{skill_name}.yaml"
    if not skill_path.exists():
        raise FileNotFoundError(f"skill config not found: {skill_path}")

    with skill_path.open("r", encoding="utf-8") as stream:
        skill = yaml.safe_load(stream) or {}

    if not isinstance(skill, dict):
        raise ValueError(f"invalid skill config format: {skill_path}")
    if "system_prompt" not in skill:
        raise ValueError(f"skill missing system_prompt: {skill_path}")

    return skill


def resolve_model(skill_name: str) -> str:
    """
    按 skill 配置的 model_env 读取模型名，读取不到再走 fallback。
    """
    skill = load_skill(skill_name)
    model_env = str(skill.get("model_env", "DEFAULT_CHAT_MODEL"))
    fallback_env = str(skill.get("fallback_model_env", "DEFAULT_CHAT_MODEL"))
    model_name = os.getenv(model_env, "")
    if model_name:
        return model_name
    return os.getenv(fallback_env, "")


def build_payload(
    skill_name: str,
    user_messages: List[Dict[str, str]],
    trace_id: str = "",
    stream_override: Optional[bool] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    根据 skill 配置组装调用 payload，业务侧只传“用户消息”即可。
    """
    skill = load_skill(skill_name)
    model_name = resolve_model(skill_name)
    if not model_name:
        model_env = str(skill.get("model_env", "DEFAULT_CHAT_MODEL"))
        fallback_env = str(skill.get("fallback_model_env", "DEFAULT_CHAT_MODEL"))
        raise RuntimeError(
            f"model missing for skill {skill_name}: need env {model_env} or {fallback_env}"
        )

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "system", "content": skill["system_prompt"]}] + user_messages,
    }

    # skill 里的常用采样参数统一透传。
    for key in ("temperature", "top_p", "max_tokens", "stream"):
        if key in skill and skill[key] is not None:
            payload[key] = skill[key]

    if stream_override is not None:
        payload["stream"] = bool(stream_override)

    if trace_id:
        payload["trace_id"] = trace_id

    if extra_fields:
        payload.update(extra_fields)

    return payload


def call_skill(
    skill_name: str,
    user_messages: List[Dict[str, str]],
    timeout: float,
    trace_id: str = "",
    stream_override: Optional[bool] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    """
    执行 skill：统一走 LLM_BASE_URL + LLM_API_KEY。
    """
    if not is_llm_ready():
        raise RuntimeError("LLM config missing: need LLM_BASE_URL and LLM_API_KEY")

    payload = build_payload(
        skill_name=skill_name,
        user_messages=user_messages,
        trace_id=trace_id,
        stream_override=stream_override,
        extra_fields=extra_fields,
    )

    headers = {"Authorization": LLM_API_KEY, "Content-Type": "application/json"}
    is_stream = bool(payload.get("stream", False))
    return requests.post(
        LLM_BASE_URL,
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False),
        stream=is_stream,
        timeout=timeout,
    )
