import os
import pickle
from typing import Any

import numpy as np
import torch
from langchain_core.documents import Document
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from kb.offline.config.settings import EMBEDDING_MODEL, PROCESSED_INDEX_DIR
from kb.offline.config.mongodb_config import MongoConfig
from kb.offline.config.env_loader import load_project_env

load_project_env()

FAISS_INDEX_PATH = str(PROCESSED_INDEX_DIR / "faiss.index")
FAISS_IDS_PATH = str(PROCESSED_INDEX_DIR / "faiss_ids.pkl")

# 懒加载状态
_initialized = False
_index = None
_ids_list = None
_embedding_handler = None
_mongo_collection = None


def _init_faiss():
    """懒加载 FAISS 索引和 embedding 模型。"""
    global _initialized, _index, _ids_list, _embedding_handler, _mongo_collection
    if _initialized:
        return

    import faiss

    _index = faiss.read_index(FAISS_INDEX_PATH)
    _ids_list = pickle.load(open(FAISS_IDS_PATH, "rb"))
    _mongo_collection = MongoConfig.get_collection("manual_text")

    embedding_device = os.getenv(
        "RAG_EMBED_DEVICE",
        "cuda" if torch.cuda.is_available() else "cpu",
    )
    _embedding_handler = BGEM3EmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        device=embedding_device,
    )
    _initialized = True


class FaissRetriever:
    """FAISS dense 向量检索器。"""

    def __init__(self, docs=None, retrieve=False):
        _init_faiss()

    def retrieve_topk(self, query: str, topk: int = 10) -> list[Document]:
        """基于 dense embedding 做 FAISS 检索，回查 MongoDB 返回完整文档。"""
        query_embeddings = _embedding_handler.encode_queries([query])
        dense_vector = np.array(query_embeddings["dense"], dtype="float32")

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
