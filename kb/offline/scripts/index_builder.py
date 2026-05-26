import os
import pickle

import jieba
import numpy as np
import torch
from tqdm import tqdm
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
)
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from kb.offline.config.settings import (
    bm25_pickle_path,
    stopwords_path,
    milvus_db_path,
    EMBEDDING_MODEL,
    PROCESSED_INDEX_DIR,
)
from kb.offline.config.mongodb_config import MongoConfig
from kb.offline.config.models import ManualInfo
from kb.offline.config.env_loader import load_project_env

load_project_env()

# BM25 停用词
with open(stopwords_path) as fd:
    _stopwords = [t.strip() for t in fd.readlines()]

# Milvus 配置
EMB_BATCH = 50
MAX_TEXT_LENGTH = 512
ID_MAX_LENGTH = 100
MILVUS_COL_NAME = "hybrid_bge_m3"

# FAISS 配置
FAISS_INDEX_PATH = str(PROCESSED_INDEX_DIR / "faiss.index")
FAISS_IDS_PATH = str(PROCESSED_INDEX_DIR / "faiss_ids.pkl")


def _tokenize(text: str) -> list[str]:
    tokens = jieba.lcut(text)
    return [t for t in tokens if t not in _stopwords]


class IndexBuilder:
    """统一索引构建器：负责将文档写入 MongoDB、Milvus、BM25、FAISS。

    Args:
        retrieval_docs: 子块 + 小父块 → 写入 FAISS/BM25（检索索引）
        parent_docs:    所有父块 → 写入 MongoDB（文档存储，供子块回查）
    """

    def __init__(self, retrieval_docs: list[Document], parent_docs: list[Document]):
        self.retrieval_docs = retrieval_docs
        self.parent_docs = parent_docs

    def build_all(self):
        """一键构建全部索引。"""
        self.build_mongodb()
        self.build_bm25()
        self.build_faiss()
        # self.build_milvus()

    def build_mongodb(self, collection_name: str = "manual_text"):
        """将所有文档写入 MongoDB（父子都存，供 FAISS 回查 + merge_docs 替换为父块）。"""
        collection = MongoConfig.get_collection(collection_name)
        # 去重合并：子块/小父块用于 FAISS 回查命中，父块用于 merge_docs 替换
        all_docs = self.retrieval_docs + self.parent_docs
        seen = set()
        for doc in tqdm(all_docs, desc="MongoDB"):
            metadata = doc.metadata
            unique_id = metadata.get("unique_id")
            if not unique_id or unique_id in seen:
                continue
            seen.add(unique_id)

            doc_record = ManualInfo(
                unique_id=unique_id,
                page_content=doc.page_content,
                metadata=metadata,
            )
            collection.update_one(
                {"unique_id": doc_record.unique_id},
                {"$set": doc_record.model_dump()},
                upsert=True,
            )
        print(f"MongoDB 写入完成，共 {len(seen)} 条（父块 {len(self.parent_docs)} + 检索单元 {len(self.retrieval_docs)}，去重）")

    def build_bm25(self):
        """构建 BM25 索引（仅子块 + 小父块）。"""
        retriever = BM25Retriever.from_documents(self.retrieval_docs, preprocess_func=_tokenize)
        pickle.dump(retriever, open(bm25_pickle_path, "wb"))
        print(f"BM25 索引构建完成，共 {len(self.retrieval_docs)} 条")

    def build_faiss(self):
        """构建 FAISS dense 向量索引（仅子块 + 小父块）。"""
        try:
            import faiss
        except ImportError:
            print("faiss 未安装，跳过 FAISS 索引构建。")
            return

        raw_texts = [doc.page_content for doc in self.retrieval_docs]
        unique_ids = [doc.metadata["unique_id"] for doc in self.retrieval_docs]

        # 通过大模型 Embedding API 获取向量
        embeddings = self._get_embeddings_via_api(raw_texts)
        dense_vectors = np.array(embeddings, dtype="float32")

        # 归一化，使内积等价于余弦相似度
        faiss.normalize_L2(dense_vectors)

        dim = dense_vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(dense_vectors)

        faiss.write_index(index, FAISS_INDEX_PATH)
        pickle.dump(unique_ids, open(FAISS_IDS_PATH, "wb"))

        print(f"FAISS 索引构建完成（API embedding），共 {len(self.retrieval_docs)} 条，维度 {dim}")

    @staticmethod
    def _get_embeddings_via_api(texts: list[str], batch_size: int = 64) -> list[list[float]]:
        """通过大模型 Embedding API 批量获取向量。"""
        from openai import OpenAI
        from tqdm import tqdm

        client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", "").removeprefix("Bearer ").strip(),
            base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
        )
        model = os.getenv("EMBEDDING_MODEL", "")

        all_embeddings = []
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding API"):
            batch = texts[i:i + batch_size]
            response = client.embeddings.create(model=model, input=batch)
            all_embeddings.extend([item.embedding for item in response.data])

        return all_embeddings

    def build_milvus(self, collection_name: str = MILVUS_COL_NAME):
        """构建 Milvus 向量索引。"""
        self._connect_milvus()

        embedding_device = os.getenv(
            "RAG_EMBED_DEVICE",
            "cuda" if torch.cuda.is_available() else "cpu",
        )
        embedding_handler = BGEM3EmbeddingFunction(
            model_name=EMBEDDING_MODEL,
            device=embedding_device,
        )

        fields = [
            FieldSchema(
                name="unique_id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                max_length=ID_MAX_LENGTH,
            ),
            FieldSchema(
                name="text",
                dtype=DataType.VARCHAR,
                max_length=MAX_TEXT_LENGTH,
            ),
            FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
            FieldSchema(
                name="dense_vector",
                dtype=DataType.FLOAT_VECTOR,
                dim=embedding_handler.dim["dense"],
            ),
        ]
        schema = CollectionSchema(fields)

        if utility.has_collection(collection_name):
            Collection(collection_name).drop()

        col = Collection(collection_name, schema, consistency_level="Strong")

        sparse_index = {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP"}
        dense_index = {"index_type": "AUTOINDEX", "metric_type": "IP"}
        col.create_index("sparse_vector", sparse_index)
        col.create_index("dense_vector", dense_index)
        col.load()

        raw_texts = [doc.page_content for doc in self.retrieval_docs]
        unique_ids = [doc.metadata["unique_id"] for doc in self.retrieval_docs]
        texts_embeddings = embedding_handler(raw_texts)

        for i in range(0, len(self.retrieval_docs), EMB_BATCH):
            batched_entities = [
                unique_ids[i : i + EMB_BATCH],
                raw_texts[i : i + EMB_BATCH],
                texts_embeddings["sparse"][i : i + EMB_BATCH],
                texts_embeddings["dense"][i : i + EMB_BATCH],
            ]
            col.insert(batched_entities)

        print(f"Milvus 索引构建完成，集合 {collection_name}，共 {col.num_entities} 条")

    @staticmethod
    def _connect_milvus():
        """连接 Milvus。"""
        if connections.has_connection("default"):
            return

        milvus_uri = os.getenv("MILVUS_URI", "").strip()
        milvus_host = os.getenv("MILVUS_HOST", "").strip()
        milvus_port = os.getenv("MILVUS_PORT", "19530").strip()

        if milvus_uri:
            connections.connect(uri=milvus_uri)
            return
        if milvus_host:
            connections.connect(host=milvus_host, port=milvus_port)
            return

        connections.connect(uri=milvus_db_path)
