import time
import sys
from pathlib import Path

# 让脚本在“仓库根目录执行”和“kb/online目录执行”两种场景都能找到 src/retrieval 包。
ONLINE_DIR = Path(__file__).resolve().parents[1]
if str(ONLINE_DIR) not in sys.path:
    sys.path.insert(0, str(ONLINE_DIR))

from retrieval.recall.bm25_retriever import BM25
from retrieval.recall.milvus_retriever import MilvusRetriever
from src.client.llm_api_client import request_chat
from retrieval.rerank.bge_m3_reranker import BGEM3ReRanker
from src.constant import bge_reranker_model_path
from retrieval.postprocess import merge_docs, post_processing

# warmstart
bm25_retriever = BM25(docs=None, retrieve=True)
milvus_retriever = MilvusRetriever(docs=None, retrieve=True) 
bge_m3_reranker = BGEM3ReRanker(model_path=bge_reranker_model_path)
milvus_retriever.retrieve_topk("这是一条测试数据", topk=3)


while True:
    query = input("输入—>")

    # 检索
    # BM25召回
    t1 = time.time()
    bm25_docs = bm25_retriever.retrieve_topk(query, topk=10)
    print("BM25召回样例:")
    print(bm25_docs)
    print("="*100)
    t2 = time.time()


    # BGE-M3稠密+稀疏召回+RRF初排
    milvus_docs = milvus_retriever.retrieve_topk(query, topk=10)
    print("BGE-M3召回样例:")
    print(milvus_docs)
    print("="*100)
    t3 = time.time()


    # 去重
    merged_docs = merge_docs(bm25_docs, milvus_docs)
    print(merged_docs)
    print("="*100)


    # 精排 
    ranked_docs = bge_m3_reranker.rank(query, merged_docs, topk=5)
    print(ranked_docs)
    print("="*100)


    # 答案
    context = "\n".join(["【" + str(idx+1) + "】" + doc.page_content for idx, doc in enumerate(ranked_docs)])
    res_handler = request_chat(query, context, stream=True)
    response = ""
    for r in res_handler:
        uttr = r.choices[0].delta.content
        response += uttr 
        print(uttr, end='')
    print("\n" + "="*100)

    # 后处理
    answer = post_processing(response, ranked_docs)
    print("\n答案—>", answer)
