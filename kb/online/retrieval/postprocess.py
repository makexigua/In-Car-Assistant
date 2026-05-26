import re
from typing import Any

from langchain_core.documents import Document
from kb.offline.config.mongodb_config import MongoConfig

manual_collection = MongoConfig.get_collection("manual_text")


def merge_docs(docs1, docs2):
    """按 parent_id / unique_id 合并去重。"""
    merged_docs = []
    merged_ids = set()
    candidate_docs = docs1 + docs2
    for doc in candidate_docs:
        parent_id = doc.metadata.get("parent_id")
        if parent_id:
            parent_mg = manual_collection.find_one({"unique_id": parent_id})
            if not parent_mg:
                continue
            unique_id = parent_mg["unique_id"]
            if unique_id and unique_id not in merged_ids:
                merged_ids.add(unique_id)
                parent_doc = Document(page_content=parent_mg["page_content"], metadata=parent_mg["metadata"])
                merged_docs.append(parent_doc)
        else:
            unique_id = doc.metadata.get("unique_id")
            if unique_id and unique_id not in merged_ids:
                merged_ids.add(unique_id)
                merged_docs.append(doc)
    return merged_docs


def rrf_rank(docs_lists: list[list[Document]], k: int = 60) -> list[Document]:
    """
    Reciprocal Rank Fusion：融合多路召回结果。

    公式：score = sum(1 / (k + rank))
    rank 从 0 开始计数。
    """
    scores: dict[str, dict[str, Any]] = {}

    for docs in docs_lists:
        for rank, doc in enumerate(docs):
            unique_id = doc.metadata.get("unique_id")
            if not unique_id:
                continue
            if unique_id not in scores:
                scores[unique_id] = {"score": 0.0, "doc": doc}
            scores[unique_id]["score"] += 1.0 / (k + rank + 1)

    ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in ranked]


def post_processing(response, docs):
    all_cites = re.findall("[【](.*?)[】]", response)
    cites = []
    for cite in all_cites:
        cite = re.sub("[{} 【】]", "", cite)
        cite = cite.replace(",", "，")
        cite = [int(k) for k in cite.split("，") if k.isdigit()]
        cites.extend(cite)
    cites = list(set(cites))
    answer = re.sub("[【](.*?)[】]", "", response)
    answer = re.sub("[{}【】]", "", answer)

    related_images = []
    pages = []
    for index in cites:
        if index > len(docs):
            continue
        images = docs[index - 1].metadata["images_info"]
        pages.append(docs[index - 1].metadata["page"])
        for image in images:
            if image["title"]:
                related_images.append(image)
    pages = sorted(list(set(pages)))
    return {
        "answer": answer,
        "cite_pages": pages,
        "related_images": related_images
    }
