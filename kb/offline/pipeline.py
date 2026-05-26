import os
import pickle
from pathlib import Path

from kb.offline.scripts.pdf_parser import load_pdf
from kb.offline.scripts.text_cleaner import clean
from kb.offline.scripts.doc_splitter import split
from kb.offline.scripts.index_builder import IndexBuilder
from kb.offline.config.settings import raw_docs_path, clean_docs_path, split_docs_path


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
        cleaned_docs = clean(raw_docs)
        print("清洗后文档page数:", len(cleaned_docs))
        pickle.dump(cleaned_docs, open(clean_docs_path, "wb"))
    else:
        cleaned_docs = pickle.load(open(clean_docs_path, "rb"))
        print("加载清洗文档page数:", len(cleaned_docs))

    # 文档切分
    if not os.path.exists(split_docs_path):
        split_result = split(cleaned_docs)
        retrieval_docs, parent_docs = split_result
        print(f"检索单元（子块+小父块）: {len(retrieval_docs)} 条，父块: {len(parent_docs)} 条")
        pickle.dump(split_result, open(split_docs_path, "wb"))
    else:
        split_result = pickle.load(open(split_docs_path, "rb"))
        # 兼容旧格式（单列表 → 新旧都当检索+父块用）
        if isinstance(split_result, tuple):
            retrieval_docs, parent_docs = split_result
        else:
            retrieval_docs = parent_docs = split_result
        print(f"加载切分文档，检索单元: {len(retrieval_docs)} 条，父块: {len(parent_docs)} 条")

    # 索引入库
    builder = IndexBuilder(retrieval_docs, parent_docs)
    builder.build_all()


if __name__ == "__main__":
    main()
