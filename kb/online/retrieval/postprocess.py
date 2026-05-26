import re
import logging
from typing import Any

from langchain_core.documents import Document
from kb.offline.config.mongodb_config import MongoConfig

manual_collection = MongoConfig.get_collection("manual_text")

logger = logging.getLogger(__name__)


def merge_docs(docs1, docs2):
    """按 parent_id / unique_id 合并去重。"""
    merged_docs = []
    merged_ids = set()
    parent_replaced = 0
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
                parent_replaced += 1
        else:
            unique_id = doc.metadata.get("unique_id")
            if unique_id and unique_id not in merged_ids:
                merged_ids.add(unique_id)
                merged_docs.append(doc)
    logger.debug("[Merge] 输入 %d 条, 去重后 %d 条, 子块→父块替换 %d 个",
                 len(candidate_docs), len(merged_docs), parent_replaced)
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
    result = [item["doc"] for item in ranked]
    if result:
        logger.debug("[RRF] 输入 %d 路, 输出 %d 条, top3_scores=%s",
                     len(docs_lists), len(result),
                     [f"{item['score']:.2f}" for item in ranked[:3]])
    return result


def post_processing(response, docs):
    """
    解析 LLM 输出，提取引用编号、引用页码和相关图片。

    docs 必须与拼 context 的列表一致（context_docs），否则引用编号错位。
    """
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
    answer = answer.strip()

    related_images = []
    seen_images = set()
    pages = []
    for index in cites:
        if index < 1 or index > len(docs):
            continue
        doc = docs[index - 1]
        images = doc.metadata.get("images_info", [])
        pages.append(doc.metadata.get("page"))
        for image in images:
            if not image.get("title"):
                continue
            img_key = image.get("image_path", "")
            if img_key and img_key not in seen_images:
                seen_images.add(img_key)
                related_images.append(image)
    pages = sorted(list(set(pages)))
    return {
        "answer": answer,
        "citations": sorted(cites),
        "cite_pages": pages,
        "related_images": related_images,
    }
