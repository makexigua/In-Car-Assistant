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

from config.settings import (
    bm25_pickle_path,
    stopwords_path,
    milvus_db_path,
    EMBEDDING_MODEL,
    PROCESSED_INDEX_DIR,
)
from config.mongodb_config import MongoConfig
from config.models import ManualInfo
from config.env_loader import load_project_env

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
    """统一索引构建器：负责将文档写入 MongoDB、Milvus、BM25、FAISS。"""

    def __init__(self, docs: list[Document]):
        self.docs = docs

    def build_all(self):
        """一键构建全部索引。"""
        self.build_mongodb()
        self.build_bm25()
        self.build_faiss()
        # self.build_milvus()

    def build_mongodb(self, collection_name: str = "manual_text"):
        """将文档批量写入 MongoDB。"""
        collection = MongoConfig.get_collection(collection_name)
        for doc in tqdm(self.docs, desc="MongoDB"):
            metadata = doc.metadata
            unique_id = metadata.get("unique_id")
            if not unique_id:
                continue

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
        print(f"MongoDB 写入完成，共 {len(self.docs)} 条")

    def build_bm25(self):
        """构建 BM25 索引并持久化到本地。"""
        retriever = BM25Retriever.from_documents(self.docs, preprocess_func=_tokenize)
        pickle.dump(retriever, open(bm25_pickle_path, "wb"))
        print(f"BM25 索引构建完成，已持久化到 {bm25_pickle_path}")

    def build_faiss(self):
        """构建 FAISS dense 向量索引。"""
        try:
            import faiss
        except ImportError:
            print("faiss 未安装，跳过 FAISS 索引构建。")
            return

        embedding_device = os.getenv(
            "RAG_EMBED_DEVICE",
            "cuda" if torch.cuda.is_available() else "cpu",
        )
        embedding_handler = BGEM3EmbeddingFunction(
            model_name=EMBEDDING_MODEL,
            device=embedding_device,
        )

        raw_texts = [doc.page_content for doc in self.docs]
        unique_ids = [doc.metadata["unique_id"] for doc in self.docs]

        texts_embeddings = embedding_handler(raw_texts)
        dense_vectors = np.array(texts_embeddings["dense"], dtype="float32")

        # 归一化，使内积等价于余弦相似度
        faiss.normalize_L2(dense_vectors)

        dim = dense_vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(dense_vectors)

        faiss.write_index(index, FAISS_INDEX_PATH)
        pickle.dump(unique_ids, open(FAISS_IDS_PATH, "wb"))

        print(f"FAISS 索引构建完成，共 {len(self.docs)} 条，维度 {dim}")

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

        raw_texts = [doc.page_content for doc in self.docs]
        unique_ids = [doc.metadata["unique_id"] for doc in self.docs]
        texts_embeddings = embedding_handler(raw_texts)

        for i in range(0, len(self.docs), EMB_BATCH):
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
