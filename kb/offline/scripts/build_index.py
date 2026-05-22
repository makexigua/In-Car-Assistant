import os
import pickle
import sys
from pathlib import Path

# 离线脚本需要两套模块：
# 1) offline src（文档解析、清洗）
# 2) online retrieval（召回/向量库封装）
OFFLINE_DIR = Path(__file__).resolve().parents[1]
KB_DIR = OFFLINE_DIR.parent
ONLINE_DIR = KB_DIR / "online"

if str(OFFLINE_DIR) not in sys.path:
    sys.path.insert(0, str(OFFLINE_DIR))
if str(ONLINE_DIR) not in sys.path:
    sys.path.insert(0, str(ONLINE_DIR))

from src.parser.pdf_parse import load_pdf, texts_split
from retrieval.recall.bm25_retriever import BM25
from retrieval.recall.milvus_retriever import MilvusRetriever
from src.constant import raw_docs_path, clean_docs_path, split_docs_path
from src.client.llm_clean_client import request_llm_clean


def main() -> None:
    # 解析 PDF
    if not os.path.exists(raw_docs_path):
        raw_docs = load_pdf()
        print("文档page数:", len(raw_docs))
        pickle.dump(raw_docs, open(raw_docs_path, "wb"))
    else:
        raw_docs = pickle.load(open(raw_docs_path, "rb"))
        print("加载文档page数:", len(raw_docs))

    # 文本清洗和整理
    if not os.path.exists(clean_docs_path):
        clean_docs = request_llm_clean(raw_docs)
        print("清洗后文档page数:", len(clean_docs))
        pickle.dump(clean_docs, open(clean_docs_path, "wb"))
    else:
        clean_docs = pickle.load(open(clean_docs_path, "rb"))
        print("加载清洗文档page数:", len(clean_docs))

    # 文档切分
    if not os.path.exists(split_docs_path):
        split_docs = texts_split(clean_docs)
        print("解析后文档总数:", len(split_docs))
        pickle.dump(split_docs, open(split_docs_path, "wb"))
    else:
        split_docs = pickle.load(open(split_docs_path, "rb"))
        print("加载解析文档总数:", len(split_docs))

    # 索引入库
    bm25_retriever = BM25(split_docs)
    candidate_docs = bm25_retriever.retrieve_topk("介绍一下离车后自动上锁功能", topk=3)
    print("BM25召回样例:")
    print(candidate_docs)
    print("=" * 100)

    milvus_retriever = MilvusRetriever(split_docs)
    candidate_docs = milvus_retriever.retrieve_topk("介绍一下离车后自动上锁功能", topk=3)
    print("BGE-M3召回样例:")
    print(candidate_docs)


if __name__ == "__main__":
    main()
