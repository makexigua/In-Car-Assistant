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
_max_parent_size = 512
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
    length_function=lambda text: len(encoding.encode(text)),   # 按token计数
)


def split(raw_docs: list[Document]) -> list[Document]:
    """语义感知切分：先语义分组生成父 doc，再句子级切分子 doc。"""
    all_split_docs = []

    for doc in tqdm(raw_docs, desc="文档切分"):
        # 语义切分生成父 doc
        grouped_chunks = semantic_split(doc.page_content, group_size=10)

        parent_docs = []
        for group in grouped_chunks:
            parent_id = hashlib.md5(group.encode("utf-8")).hexdigest()
            parent_metadata = copy.deepcopy(doc.metadata)
            parent_metadata["unique_id"] = parent_id
            parent_doc = Document(page_content=group, metadata=parent_metadata)
            parent_docs.append(parent_doc)
            if len(group) < _max_parent_size:
                all_split_docs.append(parent_doc)

        # 子 doc 切分
        for chunk in parent_docs:
            split_docs = text_splitter.create_documents(
                [chunk.page_content], metadatas=[chunk.metadata]
            )
            for child_doc in split_docs:
                if child_doc.page_content == chunk.page_content:
                    continue
                child_id = hashlib.md5(child_doc.page_content.encode("utf-8")).hexdigest()
                child_metadata = copy.deepcopy(chunk.metadata)
                child_metadata["unique_id"] = child_id
                child_metadata["parent_id"] = chunk.metadata["unique_id"]
                reid_child_doc = Document(
                    page_content=child_doc.page_content, metadata=child_metadata
                )
                all_split_docs.append(reid_child_doc)

    return all_split_docs
