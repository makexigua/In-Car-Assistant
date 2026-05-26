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
        split_docs_result = split(cleaned_docs)
        print("解析后文档总数:", len(split_docs_result))
        pickle.dump(split_docs_result, open(split_docs_path, "wb"))
    else:
        split_docs_result = pickle.load(open(split_docs_path, "rb"))
        print("加载解析文档总数:", len(split_docs_result))

    # 索引入库
    builder = IndexBuilder(split_docs_result)
    builder.build_all()


if __name__ == "__main__":
    main()
