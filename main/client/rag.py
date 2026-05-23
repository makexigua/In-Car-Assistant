# 作用：本地 RAG 链路入口（召回 + 重排 + LLM 总结），不再依赖 RAG_URL。

import os
import re
import threading
from typing import Any, Dict

from main.utils import logger
from main.utils.env_loader import load_project_env


load_project_env()

# 可通过环境变量调整召回和精排条数，默认保持与你当前链路一致。
RAG_TOPK_RECALL = int(os.getenv("RAG_TOPK_RECALL", "10"))
RAG_TOPK_RERANK = int(os.getenv("RAG_TOPK_RERANK", "5"))

# 组件懒加载状态（首次请求时初始化，后续请求复用）。
_ONLINE_READY = False
_INIT_ERROR = ""
_INIT_LOCK = threading.Lock()

# 懒加载对象
_bm25_retriever = None
_milvus_retriever = None
_reranker = None
_request_chat = None
_merge_docs = None


def _normalize_answer(answer: Any) -> str:
    """
    统一清洗 LLM 输出：
    1) 空字符串按未命中处理
    2) “无答案”按未命中处理，让主链路回退 chat 兜底
    """
    text = str(answer or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"无答案[。！？!?.]*", text):
        return ""
    if text.lower() in {"none", "null", "n"}:
        return ""
    return text


def _safe_merge_docs(docs1: list[Any], docs2: list[Any]) -> list[Any]:
    """
    优先用 kb/online 的 merge_docs；
    如果 merge 过程报错，退化为本地去重，避免整条 FAQ 链路失败。
    """
    global _merge_docs
    try:
        return _merge_docs(docs1, docs2)
    except Exception as err:
        logger.error(f"merge docs failed, fallback local dedupe: {err}")

    merged_docs = []
    seen_ids = set()
    for doc in (docs1 or []) + (docs2 or []):
        metadata = getattr(doc, "metadata", {}) or {}
        unique_id = str(metadata.get("unique_id") or metadata.get("parent_id") or "")
        if not unique_id:
            unique_id = str(hash(getattr(doc, "page_content", "")))
        if unique_id in seen_ids:
            continue
        seen_ids.add(unique_id)
        merged_docs.append(doc)
    return merged_docs


def _init_online_components() -> bool:
    """
    初始化本地 RAG 组件。
    设计要点：
    1) 线程安全：多并发只会有一个线程执行初始化
    2) 可用性优先：双路召回允许单路失败
    3) rerank 可降级：模型不可用时退化成不 rerank
    """
    global _ONLINE_READY, _INIT_ERROR
    global _bm25_retriever, _milvus_retriever, _reranker
    global _request_chat, _merge_docs

    if _ONLINE_READY:
        return True

    with _INIT_LOCK:
        if _ONLINE_READY:
            return True

        try:
            from kb.online.retrieval.recall.bm25_retriever import BM25
            from kb.online.retrieval.recall.milvus_retriever import MilvusRetriever
            from kb.online.retrieval.rerank.bge_m3_reranker import BGEM3ReRanker
            from kb.online.retrieval.postprocess import merge_docs
            from kb.online.src.client.llm_api_client import request_chat
            from kb.online.src.constant import bge_reranker_model_path
        except Exception as err:
            _INIT_ERROR = str(err)
            logger.error(f"load online rag modules failed: {err}")
            return False

        # 初始化召回器：单路失败时继续尝试另一路，尽量保服务可用。
        try:
            _bm25_retriever = BM25(docs=None, retrieve=True)
        except Exception as err:
            logger.error(f"init bm25 retriever failed: {err}")
            _bm25_retriever = None

        try:
            _milvus_retriever = MilvusRetriever(docs=None, retrieve=True)
        except Exception as err:
            logger.error(f"init milvus retriever failed: {err}")
            _milvus_retriever = None

        if _bm25_retriever is None and _milvus_retriever is None:
            _INIT_ERROR = "both bm25 and milvus retriever init failed"
            logger.error(_INIT_ERROR)
            return False

        _merge_docs = merge_docs
        _request_chat = request_chat

        # 你的 reranker 当前是强依赖 CUDA 的，初始化失败时降级即可。
        try:
            _reranker = BGEM3ReRanker(model_path=bge_reranker_model_path)
        except Exception as err:
            _reranker = None
            logger.warning(f"init reranker failed, fallback without rerank: {err}")

        _ONLINE_READY = True
        logger.info("local rag pipeline initialized.")
        return True


def _run_recall(query: str) -> tuple[list[Any], list[Any]]:
    """
    执行双路召回，分别返回 BM25 和 Milvus 结果。
    """
    bm25_docs: list[Any] = []
    milvus_docs: list[Any] = []

    if _bm25_retriever is not None:
        try:
            bm25_docs = _bm25_retriever.retrieve_topk(query, topk=RAG_TOPK_RECALL)
        except Exception as err:
            logger.error(f"bm25 recall failed: {err}")

    if _milvus_retriever is not None:
        try:
            milvus_docs = _milvus_retriever.retrieve_topk(query, topk=RAG_TOPK_RECALL)
        except Exception as err:
            logger.error(f"milvus recall failed: {err}")

    return bm25_docs, milvus_docs


def _build_context(ranked_docs: list[Any]) -> str:
    """
    组装 LLM 提示词上下文：
    【1】doc1
    【2】doc2
    """
    lines = []
    for idx, doc in enumerate(ranked_docs):
        content = getattr(doc, "page_content", "")
        if not content:
            continue
        lines.append(f"【{idx + 1}】{content}")
    return "\n".join(lines)


def request_rag(query: str, trace_id: str, sender_id: str) -> Dict[str, Any]:
    """
    FAQ 链路入口：
    query -> 双路召回 -> 去重 -> rerank top5 -> LLM 总结
    """
    _ = trace_id
    _ = sender_id

    query = (query or "").strip()
    if not query:
        return {"answer": "", "hit": False}

    if not _init_online_components():
        logger.error(f"local rag init failed: {_INIT_ERROR}")
        return {"answer": "", "hit": False}

    try:
        bm25_docs, milvus_docs = _run_recall(query)
        merged_docs = _safe_merge_docs(bm25_docs, milvus_docs)
        if not merged_docs:
            logger.info("rag recall got empty docs.")
            return {"answer": "", "hit": False, "docs_count": 0}

        # 优先走 rerank；如果 rerank 不可用，退化为 merge 后直接截取 top5。
        if _reranker is not None:
            try:
                ranked_docs = _reranker.rank(query, merged_docs, topk=RAG_TOPK_RERANK)
            except Exception as err:
                logger.warning(f"rerank failed, fallback merged topk: {err}")
                ranked_docs = merged_docs[:RAG_TOPK_RERANK]
        else:
            ranked_docs = merged_docs[:RAG_TOPK_RERANK]

        context = _build_context(ranked_docs)
        if not context:
            logger.info("rag context is empty.")
            return {"answer": "", "hit": False, "docs_count": 0}

        # stream=False：FAQ 链路是单帧非流式返回，和你当前 start 分支一致。
        raw_answer = _request_chat(query, context, stream=False)
        answer = _normalize_answer(raw_answer)
        return {
            "answer": answer,
            "hit": bool(answer),
            "docs_count": len(ranked_docs),
        }
    except Exception as err:
        logger.error(f"local rag pipeline failed: {err}")
        return {"answer": "", "hit": False}
