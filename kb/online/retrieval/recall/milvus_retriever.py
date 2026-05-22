import os
import time
import hashlib
import pandas as pd
import torch
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
    AnnSearchRequest,
    RRFRanker,
    WeightedRanker
)
from langchain_core.documents import Document
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

from src.constant import test_doc_path, bge_m3_model_path, milvus_db_path
from src.client.mongodb_config import MongoConfig
from src.client.env_loader import load_project_env

# 每批次向 Milvus 写入的文本数量，避免一次性写入过多导致内存和延迟压力。
EMB_BATCH = 50
# Milvus 中 text 字段的最大字符长度，需与字段 Schema 保持一致。
MAX_TEXT_LENGTH = 512
# Milvus 主键 unique_id 的最大长度限制。
ID_MAX_LENGTH = 100
# 向量集合（Collection）名称，构建索引和检索都基于该名称。
COL_NAME = "hybrid_bge_m3"


def _connect_milvus() -> None:
    """
    按优先级连接 Milvus：
    1) MILVUS_URI（推荐：远端服务统一走 URI）
    2) MILVUS_HOST + MILVUS_PORT
    3) 回退到本地 milvus-lite 文件（兼容旧开发模式）
    """
    load_project_env()
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


# 获取 MongoDB 中文本数据集合，用于检索后回表拿完整文档内容与元信息。
mongo_collection = MongoConfig.get_collection("manual_text")
# 连接 Milvus 服务。
_connect_milvus()
# 初始化 BGE-M3 向量模型，同时支持 dense/sparse 混合向量表示。
embedding_device = os.getenv(
    "RAG_EMBED_DEVICE",
    "cuda" if torch.cuda.is_available() else "cpu",
)
embedding_handler = BGEM3EmbeddingFunction(
    model_name=bge_m3_model_path,
    device=embedding_device,
)


class MilvusRetriever:
    def __init__ (self, docs, retrieve=False):
        # 定义 Milvus 集合字段：主键、原文、稀疏向量、稠密向量。
        fields = [
            # 构建查询ID，primary key
            FieldSchema(name="unique_id", dtype=DataType.VARCHAR, is_primary=True, max_length=ID_MAX_LENGTH),
            # 存储原文，dense vector和sparse vector
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=MAX_TEXT_LENGTH),
            FieldSchema(name="sparse_vector", dtype=DataType.SPARSE_FLOAT_VECTOR),
            # dense 向量维度直接读取模型输出维度，避免手写维度导致不一致。
            FieldSchema(name="dense_vector", dtype=DataType.FLOAT_VECTOR, dim=embedding_handler.dim["dense"]),
        ]
        # 使用字段定义创建集合 Schema。
        schema = CollectionSchema(fields)

        # 如果当前不是“纯检索模式”，且旧集合已存在，则先删掉旧集合重建索引数据。
        if not retrieve and utility.has_collection(COL_NAME):
            Collection(COL_NAME).drop()
        # 创建或加载集合对象，使用 Strong 一致性确保读写可见性更强。
        self.col = Collection(COL_NAME, schema, consistency_level="Strong")

        # 稀疏向量使用倒排索引，度量方式为 IP（内积）。
        sparse_index = {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "IP"}
        # 稠密向量使用 AUTOINDEX，度量方式同样为 IP（通常配合归一化向量）。
        dense_index = {"index_type": "AUTOINDEX", "metric_type": "IP"}
        # 为稀疏向量字段创建索引。
        self.col.create_index("sparse_vector", sparse_index)
        # 为稠密向量字段创建索引。
        self.col.create_index("dense_vector", dense_index)
        # 将集合加载到内存，后续可直接检索。
        self.col.load()

        # 如果是非检索阶段，先构建索引
        if not retrieve:
            # 将传入文档批量向量化并写入 Milvus。
            self.save_vectorstore(docs)


    def save_vectorstore(self, docs: list[str]): 

        # 提取每个文档的正文文本，用于向量化。
        raw_texts = [doc.page_content for doc in docs]
        # 提取每个文档的唯一 ID，作为 Milvus 主键写入。
        unique_ids = [doc.metadata["unique_id"] for doc in docs]

        # 计算embedding
        # 一次性计算全部文本的 dense/sparse 向量表示。
        texts_embeddings = embedding_handler(raw_texts)

        # batch embedding 插入
        # 按固定批次切片写入，降低单次写入开销并提升稳定性。
        for i in range(0, len(docs), EMB_BATCH):
            # batched_entities 顺序必须与字段顺序一致：id、text、sparse、dense。
            batched_entities = [
                # 当前批次的唯一 ID 切片。
                unique_ids[i : i + EMB_BATCH],
                # 当前批次的原文文本切片。
                raw_texts[i : i + EMB_BATCH],
                # 当前批次的稀疏向量切片。
                texts_embeddings["sparse"][i : i + EMB_BATCH],
                # 当前批次的稠密向量切片。
                texts_embeddings["dense"][i : i + EMB_BATCH],
            ]
            # 将当前批次实体写入 Milvus。
            self.col.insert(batched_entities)
        # 打印入库数量，方便确认索引构建结果。
        print("索引构建完成，插入了{}条数据:".format(self.col.num_entities))


    def dense_search(self, query_dense_embedding, limit):
        # dense 检索参数：使用内积，额外参数为空字典。
        search_params = {"metric_type": "IP", "params": {}}
        # 基于 dense_vector 字段执行向量检索。
        res = self.col.search(
            # Milvus 查询接口要求二维结构，这里包一层列表。
            [query_dense_embedding],
            # 指定检索的向量字段为稠密向量字段。
            anns_field="dense_vector",
            # 返回 top-k 数量。
            limit=limit,
            # 只返回后续需要的字段，减少无关数据传输。
            output_fields=["unique_id", "text"],
            # 传入检索参数。
            param=search_params,
        )
        # 返回 Milvus 原始检索结果对象。
        return res


    def sparse_search(self, query_sparse_embedding, limit):
        # sparse 检索参数：同样使用内积度量。
        search_params = {
            "metric_type": "IP",
            "params": {},
        }
        # 基于 sparse_vector 字段执行稀疏向量检索。
        res = self.col.search(
            # 稀疏查询向量同样按二维结构传入。
            [query_sparse_embedding],
            # 指定检索字段为稀疏向量字段。
            anns_field="sparse_vector",
            # 返回 top-k 数量。
            limit=limit,
            # 返回 ID 和文本字段，便于后续处理。
            output_fields=["unique_id", "text"],
            # 传入检索参数。
            param=search_params,
        )
        # 返回稀疏检索结果。
        return res


    def hybrid_search(
        self,
        query_dense_embedding,
        query_sparse_embedding,
        sparse_weight=1.0,
        dense_weight=1.0,
        limit=10,
    ):
        # 构造 dense 子检索参数。
        dense_search_params = {"metric_type": "IP", "params": {}}
        # 封装 dense 检索请求对象，供 hybrid_search 统一融合。
        dense_req = AnnSearchRequest(
            [query_dense_embedding], "dense_vector", dense_search_params, limit=limit
        )
        # 构造 sparse 子检索参数。
        sparse_search_params = {"metric_type": "IP", "params": {}}
        # 封装 sparse 检索请求对象。
        sparse_req = AnnSearchRequest(
            [query_sparse_embedding], "sparse_vector", sparse_search_params, limit=limit
        )
        # 可选加权融合器（当前注释掉，保留备用）。
        # rerank = WeightedRanker(sparse_weight, dense_weight)
        # 使用 RRF 融合策略整合 sparse/dense 两路召回结果。
        rerank = RRFRanker()
        # 执行 Milvus 混合检索，并返回融合后的 top-k 结果。
        res = self.col.hybrid_search(
            # 同时传入 sparse 与 dense 两个子检索请求。
            [sparse_req, dense_req],
            # 指定融合器。
            rerank=rerank,
            # 控制最终返回条数。
            limit=limit,
            # 返回字段仅包含唯一 ID 与文本。
            output_fields=["unique_id", "text"]
        )
        # 返回混合检索结果。
        return res


    def retrieve_topk(self, query, topk=10):
        # 记录起始时间，便于后续添加耗时统计。
        t1 = time.time()
        # 抽取query的embedding 
        # 将用户查询编码为 dense/sparse 两种向量。
        query_embeddings = embedding_handler.encode_queries([query])

        # 检索Topk
        # 调用混合检索并取第一条 query 对应的结果列表。
        hybrid_results = self.hybrid_search(
            # 传入该 query 的 dense 向量。
            query_embeddings["dense"][0],
            # 传入该 query 的 sparse 向量（保持二维结构）。
            query_embeddings["sparse"][[0]],
            # 稀疏通道权重（当前 RRF 未显式使用该参数，保留接口兼容性）。
            sparse_weight=0.7,
            # 稠密通道权重（同上，保留可切换加权融合能力）。
            dense_weight=1.0,
            # 指定返回 topk 条结果。
            limit=topk
        )[0]

        # 关联mongo数据
        # 准备承接回表后的 Document 列表。
        related_docs = []
        # 遍历混合检索返回的每一条召回结果。
        for result in hybrid_results:
            # 根据 unique_id 到 MongoDB 回查完整文本及元数据。
            search_res = mongo_collection.find_one({"unique_id": result["id"]})
            if not search_res:
                continue
            # 以下图片信息反序列化逻辑当前不启用，先保留为注释代码。
            #images_list = []
            #for image in search_res["metadata"]["images_info"]:
            #    images_list.append(ManualImages(**image))
            #search_res["metadata"]["images_info"] =  images_list 
            # 将 MongoDB 记录转换为 LangChain Document 对象。
            doc = Document(page_content=search_res["page_content"], metadata=search_res["metadata"])
            # 收集进最终返回列表。
            related_docs.append(doc)

        # 返回检索并回表后的文档列表。
        return related_docs 


if __name__ == "__main__":
    # 从测试文本文件按行读取样本文本。
    texts = [k for k in open(test_doc_path).readlines()]
    # 初始化文档容器。
    docs = []
    # 遍历每一行文本，构造带 unique_id 的 Document。
    for text in texts:
        # 对文本做 MD5，生成稳定且可复现的唯一 ID。
        unique_id = hashlib.md5(text.encode('utf-8')).hexdigest()
        # 构造最小元信息字典（仅包含 unique_id）。
        metadata = {"unique_id": unique_id}
        # 组装 LangChain Document 并追加到列表。
        docs.append(Document(page_content=text, metadata=metadata))
    # 构建检索器并写入向量库（默认 retrieve=False）。
    retriever = MilvusRetriever(docs)
    # 构造示例查询。
    query = "Model3支持的钥匙类型"
    # 执行 top-2 检索。
    results = retriever.retrieve_topk(query, 2)
    # 打印每条结果内容，便于快速观察效果。
    for res in results:
        print(res)
        # 打印分隔线，提升控制台可读性。
        print("="*100)
