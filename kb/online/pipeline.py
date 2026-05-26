import os
import re
import logging
from typing import Any
from pathlib import Path

from kb.online.retrieval.recall.bm25_retriever import BM25
from kb.online.retrieval.recall.faiss_retriever import FaissRetriever
from kb.online.retrieval.rerank.reranker import ApiReranker
from kb.online.retrieval.postprocess import merge_docs, rrf_rank, post_processing
from kb.online.config.llm_client import request_chat
from kb.offline.config.settings import RERANK_MODEL
from kb.offline.config.env_loader import load_project_env

load_project_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 召回/排序数量（从环境变量读取）
FAISS_TOPK = int(os.getenv("FAISS_TOPK", "20"))
BM25_TOPK = int(os.getenv("BM25_TOPK", "20"))
RRF_TOPK = int(os.getenv("RRF_TOPK", "20"))
RERANK_TOPK = int(os.getenv("RERANK_TOPK", "5"))

# 懒加载组件
_components = {}


def _init_components():
    """初始化召回、重排组件，只执行一次。"""
    if _components:
        return

    _components["bm25"] = BM25(docs=None, retrieve=True)
    _components["faiss"] = FaissRetriever(docs=None, retrieve=True)
    _components["reranker"] = ApiReranker(model_path=RERANK_MODEL)


def process(query: str) -> dict:
    """
    RAG 链路主入口。

    流程：
    1. FAISS dense 召回 top FAISS_TOPK
    2. BM25 召回 top BM25_TOPK
    3. merge 去重
    4. RRF 排序取 top RRF_TOPK
    5. rerank 取 top RERANK_TOPK
    6. LLM 生成答案
    """
    _init_components()

    logger.info("========== RAG 链路开始 ==========")
    logger.info("[RAG] 用户问题: %s", query)

    # 1. 双路召回
    bm25_docs = _components["bm25"].retrieve_topk(query, topk=BM25_TOPK)
    logger.info("[RAG][召回] BM25 召回 %d 条", len(bm25_docs))

    faiss_docs = _components["faiss"].retrieve_topk(query, topk=FAISS_TOPK)
    logger.info("[RAG][召回] FAISS 召回 %d 条", len(faiss_docs))

    # 2. 去重
    merged_docs = merge_docs(bm25_docs, faiss_docs)
    logger.info("[RAG][合并] 去重合并后 %d 条 (BM25: %d + FAISS: %d)",
                len(merged_docs), len(bm25_docs), len(faiss_docs))
    if merged_docs:
        logger.info("[RAG][合并] Top-3 摘要: %s",
                    [d.page_content[:60] for d in merged_docs[:3]])
    if not merged_docs:
        return {"answer": "", "hit": False, "docs_count": 0}

    # 3. RRF 排序
    rrf_docs = rrf_rank([bm25_docs, faiss_docs])[:RRF_TOPK]
    logger.info("[RAG][RRF] RRF 重排后取 Top-%d: %d 条", RRF_TOPK, len(rrf_docs))
    if rrf_docs:
        logger.info("[RAG][RRF] Top-3 摘要: %s",
                    [d.page_content[:60] for d in rrf_docs[:3]])

    # 4. rerank
    ranked_docs = _components["reranker"].rank(query, rrf_docs, topk=RERANK_TOPK)
    logger.info("[RAG][Rerank] Rerank 后取 Top-%d: %d 条", RERANK_TOPK, len(ranked_docs))
    if ranked_docs:
        logger.info("[RAG][Rerank] Top-3 摘要: %s",
                    [d.page_content[:60] for d in ranked_docs[:3]])

    # 5. 子块替换为父块，拼 context
    context_docs = merge_docs(ranked_docs, [])
    logger.info("[RAG][生成] 子块→父块替换后: %d 条, 拼入 context", len(context_docs))
    context = "\n".join([
        f"【{idx + 1}】(第{doc.metadata.get('page', '?')}页){doc.page_content}"
        for idx, doc in enumerate(context_docs)
    ])
    raw_answer = request_chat(query, context, stream=False)
    logger.info("[RAG][生成] LLM 返回原始长度: %d 字符", len(raw_answer or ""))
    answer = _normalize_answer(raw_answer)

    result = {
        "answer": answer,
        "hit": bool(answer),
        "docs_count": len(context_docs),
        "citations": [],
        "cite_pages": [],
        "related_images": [],
    }
    if answer:
        # 解析 LLM 输出中的引用和图片（传入 context_docs 保证编号对齐）
        parsed = post_processing(raw_answer, context_docs)
        result.update(parsed)

    logger.info("[RAG][结果] hit=%s, docs_count=%d, citations=%s, cite_pages=%s",
                result["hit"], result["docs_count"],
                result.get("citations", []), result.get("cite_pages", []))
    logger.info("[RAG][结果] 最终答案(前100字): %s", answer[:100] if answer else "无答案")
    logger.info("========== RAG 链路结束 ==========")

    return result


def _normalize_answer(answer: Any) -> str:
    """清洗 LLM 输出。"""
    text = str(answer or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"无答案[。！？!?.]*", text):
        return ""
    if text.lower() in {"none", "null", "n"}:
        return ""
    return text


if __name__ == "__main__":
    while True:
        query = input("输入—>")
        result = process(query)
        print(result)
        print("=" * 100)
