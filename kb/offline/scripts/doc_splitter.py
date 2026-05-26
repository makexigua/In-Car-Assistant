import copy
import hashlib
import tiktoken
from tqdm import tqdm
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from kb.offline.scripts.semantic_splitter import semantic_split


# 全局配置
_chunk_size = 256
_chunk_overlap = 50
encoding = tiktoken.get_encoding("cl100k_base")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=_chunk_size,
    chunk_overlap=_chunk_overlap,
    separators=[
        "\n\n",
        "。",
        "！",
        "？",
        "；",
        "\n",
        " "
    ],
    length_function=lambda text: len(encoding.encode(text)),
)


def split(raw_docs: list[Document]) -> tuple[list[Document], list[Document]]:
    """
    语义感知切分。

    Returns:
        retrieval_docs: 子块 + 小父块 → 用于 FAISS/BM25 检索
        parent_docs:    所有父块 → 用于 MongoDB 文档存储（供子块回查）
    """
    retrieval_docs = []
    parent_docs = []

    for doc in tqdm(raw_docs, desc="文档切分"):
        grouped_chunks = semantic_split(doc.page_content, group_size=10)

        doc_parents = []
        for group in grouped_chunks:
            parent_id = hashlib.md5(group.encode("utf-8")).hexdigest()
            parent_metadata = copy.deepcopy(doc.metadata)
            parent_metadata["unique_id"] = parent_id
            parent_doc = Document(page_content=group, metadata=parent_metadata)
            doc_parents.append(parent_doc)
            parent_docs.append(parent_doc)

        # 子块切分 + 识别小父块
        for chunk in doc_parents:
            split_docs = text_splitter.create_documents(
                [chunk.page_content], metadatas=[chunk.metadata]
            )
            is_small_parent = True
            for child_doc in split_docs:
                if child_doc.page_content == chunk.page_content:
                    continue
                is_small_parent = False
                child_id = hashlib.md5(child_doc.page_content.encode("utf-8")).hexdigest()
                child_metadata = copy.deepcopy(chunk.metadata)
                child_metadata["unique_id"] = child_id
                child_metadata["parent_id"] = chunk.metadata["unique_id"]
                reid_child_doc = Document(
                    page_content=child_doc.page_content, metadata=child_metadata
                )
                retrieval_docs.append(reid_child_doc)

            if is_small_parent:
                # 小父块同时作为检索单元
                retrieval_docs.append(chunk)

    return retrieval_docs, parent_docs
