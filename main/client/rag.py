# -*- coding: utf-8 -*-
# --------------------------------------------
# 项目名称: LLM任务型对话Agent
# 版权所有  ©2025丁师兄大模型
# 生成时间: 2026-05
# --------------------------------------------

import json
import os
from typing import Dict, Any

import requests

from utils import logger
from utils.env_loader import load_project_env


load_project_env()
RAG_URL = os.getenv("RAG_URL", "")
RAG_TIMEOUT = float(os.getenv("RAG_TIMEOUT", "8.0"))


def request_rag(query: str, trace_id: str, sender_id: str) -> Dict[str, Any]:
    """
    统一的知识库问答 API 调用入口。
    后续如果 RAG 服务协议有变化，只改这个文件就行。
    """
    if not RAG_URL:
        logger.error("RAG_URL is empty, fallback to no-answer.")
        return {"answer": "", "hit": False}

    payload = {
        "query": query,
        "trace_id": trace_id,
        "sender_id": sender_id
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            RAG_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False),
            timeout=RAG_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        # 兼容几种常见响应格式：{"answer": "..."} 或 {"data": {"answer":"..."}}
        if isinstance(data, dict) and "answer" in data:
            answer = data.get("answer") or ""
            return {"answer": answer, "hit": bool(answer), "raw": data}
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            answer = data["data"].get("answer") or ""
            return {"answer": answer, "hit": bool(answer), "raw": data}
        return {"answer": "", "hit": False, "raw": data}
    except Exception as err:
        logger.error(f"call RAG failed: {err}")
        return {"answer": "", "hit": False}

