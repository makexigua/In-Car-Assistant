import os
import pickle
from typing import Any

import numpy as np
from langchain_core.documents import Document

from kb.offline.config.settings import PROCESSED_INDEX_DIR
from kb.offline.config.mongodb_config import MongoConfig
from kb.offline.config.env_loader import load_project_env

load_project_env()

FAISS_INDEX_PATH = str(PROCESSED_INDEX_DIR / "faiss.index")
FAISS_IDS_PATH = str(PROCESSED_INDEX_DIR / "faiss_ids.pkl")

# 懒加载状态
_initialized = False
_index = None
_ids_list = None
_mongo_collection = None


def _init_faiss():
    """懒加载 FAISS 索引。"""
    global _initialized, _index, _ids_list, _mongo_collection
    if _initialized:
        return

    import faiss

    _index = faiss.read_index(FAISS_INDEX_PATH)
    _ids_list = pickle.load(open(FAISS_IDS_PATH, "rb"))
    _mongo_collection = MongoConfig.get_collection("manual_text")
    _initialized = True


class FaissRetriever:
    """FAISS dense 向量检索器（embedding 通过 API 获取）。"""

    def __init__(self, docs=None, retrieve=False):
        _init_faiss()

    def retrieve_topk(self, query: str, topk: int = 10) -> list[Document]:
        """基于 dense embedding 做 FAISS 检索，回查 MongoDB 返回完整文档。"""
        query_embedding = self._get_embedding(query)
        dense_vector = np.array([query_embedding], dtype="float32")

        import faiss
        faiss.normalize_L2(dense_vector)

        scores, indices = _index.search(dense_vector, topk)

        related_docs = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(_ids_list):
                continue
            unique_id = _ids_list[idx]
            search_res = _mongo_collection.find_one({"unique_id": unique_id})
            if not search_res:
                continue
            doc = Document(
                page_content=search_res["page_content"],
                metadata=search_res["metadata"],
            )
            related_docs.append(doc)

        return related_docs

    @staticmethod
    def _get_embedding(text: str) -> list[float]:
        """通过大模型 Embedding API 获取单个文本的向量。"""
        from openai import OpenAI

        client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", ""),
        )
        response = client.embeddings.create(
            model=os.getenv("EMBEDDING_MODEL", ""),
            input=text,
        )
        return response.data[0].embedding
