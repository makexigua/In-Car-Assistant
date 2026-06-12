"""
离线文档处理流水线 — 支持多格式文档。

用法:
    python -m kb.offline.pipeline                         # 使用默认 PDF
    python -m kb.offline.pipeline --file ./docs/manual.docx
    python -m kb.offline.pipeline --dir  ./docs/           # 批量解析目录

处理流程:
    解析 → 清洗 → 切分 → 索引入库 (FAISS + BM25 + MongoDB)
"""

import os
import pickle
import argparse
from pathlib import Path
from typing import Dict, List

from langchain_core.documents import Document

from kb.offline.scripts.file_processors import (
    parse_document,
    batch_parse_directory,
    SUPPORTED_EXTENSIONS,
)
from kb.offline.scripts.text_cleaner import clean
from kb.offline.scripts.doc_splitter import split
from kb.offline.scripts.index_builder import IndexBuilder
from kb.offline.config.settings import (
    raw_docs_path,
    clean_docs_path,
    split_docs_path,
    RAW_DATA_DIR,
    pdf_path,
)


def _load_or_parse_docs(source: str, force: bool = False) -> List[Document]:
    """
    加载或重新解析文档。

    如果单个文件 → 解析该文件。
    如果是目录 → 批量解析。
    如果已有 pickle 缓存且不强制刷新 → 从缓存加载。
    """
    # 从缓存加载
    if not force and os.path.exists(raw_docs_path):
        raw_docs = pickle.load(open(raw_docs_path, "rb"))
        print(f"加载缓存文档: {len(raw_docs)} 条")
        return raw_docs

    # 判断是文件还是目录
    p = Path(source)
    if p.is_dir():
        print(f"批量解析目录: {source} (支持格式: {SUPPORTED_EXTENSIONS})")
        results: Dict[str, List[Document]] = batch_parse_directory(
            source, recursive=True
        )
        raw_docs = []
        for fpath, docs in results.items():
            print(f"  → {Path(fpath).name}: {len(docs)} 条")
            raw_docs.extend(docs)
    elif p.is_file():
        print(f"解析文件: {source}")
        raw_docs = parse_document(source)
    else:
        raise FileNotFoundError(f"路径不存在: {source}")

    print(f"文档解析完成: 共 {len(raw_docs)} 条")
    return raw_docs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="离线文档处理流水线 — 解析 → 清洗 → 切分 → 索引入库"
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="要解析的文件路径（支持 pdf/docx/xlsx/pptx/txt/md）",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="批量解析目录下所有支持的文档",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="强制重新解析（忽略缓存）",
    )
    args = parser.parse_args()

    # 确定文档来源
    if args.file:
        source = args.file
    elif args.dir:
        source = args.dir
    else:
        # 默认使用 settings 中的 pdf_path
        source = pdf_path
        print(f"使用默认 PDF: {source}")

    # 1. 解析文档
    raw_docs = _load_or_parse_docs(source, force=args.force)

    # 2. 文本清洗和整理
    if not os.path.exists(clean_docs_path) or args.force:
        cleaned_docs = clean(raw_docs)
        print(f"清洗后文档数: {len(cleaned_docs)}")
        pickle.dump(cleaned_docs, open(clean_docs_path, "wb"))
    else:
        cleaned_docs = pickle.load(open(clean_docs_path, "rb"))
        print(f"加载清洗文档: {len(cleaned_docs)} 条")

    # 3. 文档切分
    if not os.path.exists(split_docs_path) or args.force:
        split_result = split(cleaned_docs)
        retrieval_docs, parent_docs = split_result
        print(
            f"检索单元（子块+小父块）: {len(retrieval_docs)} 条, "
            f"父块: {len(parent_docs)} 条"
        )
        pickle.dump(split_result, open(split_docs_path, "wb"))
    else:
        split_result = pickle.load(open(split_docs_path, "rb"))
        if isinstance(split_result, tuple):
            retrieval_docs, parent_docs = split_result
        else:
            retrieval_docs = parent_docs = split_result
        print(
            f"加载切分文档: 检索单元 {len(retrieval_docs)} 条, "
            f"父块 {len(parent_docs)} 条"
        )

    # 4. 索引入库
    builder = IndexBuilder(retrieval_docs, parent_docs)
    builder.build_all()


if __name__ == "__main__":
    main()
