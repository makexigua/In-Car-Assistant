import time
import sys
from pathlib import Path

ONLINE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ONLINE_DIR.parents[1]

if str(ONLINE_DIR) not in sys.path:
    sys.path.insert(0, str(ONLINE_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from retrieval.recall.bm25_retriever import BM25
from retrieval.recall.milvus_retriever import MilvusRetriever
from config.llm_client import request_chat
from retrieval.rerank.bge_m3_reranker import BGEM3ReRanker
from kb.offline.config.settings import RERANK_MODEL
from retrieval.postprocess import merge_docs, post_processing

# warmstart
bm25_retriever = BM25(docs=None, retrieve=True)
milvus_retriever = MilvusRetriever(docs=None, retrieve=True)
bge_m3_reranker = BGEM3ReRanker(model_path=RERANK_MODEL)
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
