# 作用：按需加载单个 skill 的 Markdown 提示词，并通过统一大模型 API 执行。

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

from utils.env_loader import load_project_env


load_project_env()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
SKILL_CONFIG_DIR = Path(__file__).resolve().parent / "config"

# 这些是“运行参数”，和 prompt 文案分离，避免把大段提示词堆在 yaml 文件里。
SKILL_RUNTIME_OPTIONS: Dict[str, Dict[str, Any]] = {
    "reject": {
        "model_env": "REJECT_MODEL",
        "fallback_model_env": "DEFAULT_CHAT_MODEL",
        "temperature": 0,
        "top_p": 0,
        "max_tokens": 8,
        "stream": False,
    },
    "rewrite": {
        "model_env": "REWRITE_MODEL",
        "fallback_model_env": "DEFAULT_CHAT_MODEL",
        "temperature": 0.001,
        "top_p": 0,
        "stream": False,
    },
    "arbitration": {
        "model_env": "ARBITRATION_MODEL",
        "fallback_model_env": "DEFAULT_CHAT_MODEL",
        "temperature": 0,
        "max_tokens": 2048,
        "stream": True,
    },
    "chat": {
        "model_env": "CHAT_MODEL",
        "fallback_model_env": "DEFAULT_CHAT_MODEL",
        "stream": True,
    },
}


def is_llm_ready() -> bool:
    return bool(LLM_API_KEY and LLM_BASE_URL)


def _parse_markdown_front_matter(raw_text: str, skill_path: Path) -> Tuple[Dict[str, Any], str]:
    """
    解析 markdown 的 YAML 头和正文。
    文件格式要求：
    ---
    name: xxx
    description: xxx
    ---
    这里是 prompt 正文
    """
    if not raw_text.startswith("---\n"):
        raise ValueError(f"invalid skill markdown front matter: {skill_path}")

    end_index = raw_text.find("\n---\n", 4)
    if end_index == -1:
        raise ValueError(f"invalid skill markdown boundary: {skill_path}")

    meta_raw = raw_text[4:end_index]
    body = raw_text[end_index + len("\n---\n"):].strip()
    meta = yaml.safe_load(meta_raw) or {}

    if not isinstance(meta, dict):
        raise ValueError(f"invalid skill markdown meta: {skill_path}")
    if not body:
        raise ValueError(f"empty skill prompt body: {skill_path}")
    return meta, body


@lru_cache(maxsize=64)
def load_skill(skill_name: str) -> Dict[str, Any]:
    """
    按 skill 名称读取单个 markdown 文件并缓存。
    这里是“渐进式披露”：只加载当前调用的 skill，不会全量读所有文件。
    """
    skill_path = SKILL_CONFIG_DIR / f"{skill_name}.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"skill config not found: {skill_path}")

    raw_text = skill_path.read_text(encoding="utf-8")
    meta, prompt_body = _parse_markdown_front_matter(raw_text, skill_path)

    meta_name = str(meta.get("name", "")).strip()
    if meta_name and meta_name != skill_name:
        raise ValueError(f"skill name mismatch: {meta_name} != {skill_name}")

    if skill_name not in SKILL_RUNTIME_OPTIONS:
        raise ValueError(f"skill runtime options not found: {skill_name}")

    skill_config: Dict[str, Any] = {
        "name": meta_name or skill_name,
        "description": str(meta.get("description", "")).strip(),
        "system_prompt": prompt_body,
    }
    skill_config.update(SKILL_RUNTIME_OPTIONS[skill_name])
    return skill_config


def resolve_model(skill_name: str) -> str:
    """
    按 skill 的 model_env 读取模型名，缺省时再走 fallback。
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
    根据 skill 配置组装请求体，业务层只需要传消息内容。
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

    # 只透传这几个稳定的采样字段，避免误把描述类字段塞进 API。
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
