import os
import re
from typing import Any
from pathlib import Path

from kb.online.retrieval.recall.bm25_retriever import BM25
from kb.online.retrieval.recall.faiss_retriever import FaissRetriever
from kb.online.retrieval.rerank.bge_m3_reranker import BGEM3ReRanker
from kb.online.retrieval.postprocess import merge_docs, rrf_rank
from kb.online.config.llm_client import request_chat
from kb.offline.config.settings import RERANK_MODEL
from kb.offline.config.env_loader import load_project_env

load_project_env()

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
    _components["reranker"] = BGEM3ReRanker(model_path=RERANK_MODEL)


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

    # 1. 双路召回
    bm25_docs = _components["bm25"].retrieve_topk(query, topk=BM25_TOPK)
    faiss_docs = _components["faiss"].retrieve_topk(query, topk=FAISS_TOPK)

    # 2. 去重
    merged_docs = merge_docs(bm25_docs, faiss_docs)
    if not merged_docs:
        return {"answer": "", "hit": False, "docs_count": 0}

    # 3. RRF 排序
    rrf_docs = rrf_rank([bm25_docs, faiss_docs])[:RRF_TOPK]

    # 4. rerank
    ranked_docs = _components["reranker"].rank(query, rrf_docs, topk=RERANK_TOPK)

    # 5. LLM 生成答案
    context = "\n".join([
        f"【{idx + 1}】{doc.page_content}"
        for idx, doc in enumerate(ranked_docs)
    ])
    raw_answer = request_chat(query, context, stream=False)
    answer = _normalize_answer(raw_answer)

    return {
        "answer": answer,
        "hit": bool(answer),
        "docs_count": len(ranked_docs),
    }


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
