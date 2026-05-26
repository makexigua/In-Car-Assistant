# 作用：RAG 链路入口，调用 kb/online RAG 链路。

from typing import Any, Dict

from main.utils import logger


def request_rag(query: str, trace_id: str, sender_id: str) -> Dict[str, Any]:
    """
    RAG 链路入口：向 kb/online/pipeline 发送请求，获取 RAG 答案。
    """
    _ = trace_id
    _ = sender_id

    query = (query or "").strip()
    if not query:
        return {"answer": "", "hit": False}

    try:
        from kb.online.pipeline import process
    except Exception as err:
        logger.error(f"load online pipeline failed: {err}")
        return {"answer": "", "hit": False}

    try:
        result = process(query)
        return result
    except Exception as err:
        logger.error(f"rag pipeline failed: {err}")
        return {"answer": "", "hit": False}
