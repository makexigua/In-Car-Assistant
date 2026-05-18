# 作用：调用 RAG 服务并统一解析返回，给主链路输出标准 answer/hit 结构。

import json
import os
from typing import Any, Dict

import requests
from utils import logger
from utils.env_loader import load_project_env


load_project_env()
RAG_URL = os.getenv("RAG_URL", "")
RAG_TIMEOUT = float(os.getenv("RAG_TIMEOUT", "8.0"))


def request_rag(query: str, trace_id: str, sender_id: str) -> Dict[str, Any]:
    if not RAG_URL:
        logger.error("RAG_URL is empty, fallback to no-answer.")
        return {"answer": "", "hit": False}

    payload = {"query": query, "trace_id": trace_id, "sender_id": sender_id}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            RAG_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False),
            timeout=RAG_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        # 兼容几种常见响应格式：{"answer": "..."} 或 {"data": {"answer": "..."}}
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
