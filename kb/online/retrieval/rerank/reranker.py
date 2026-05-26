# 作用：通过 LLM API 调用 rerank 服务，替代本地 transformers 模型加载。

import os

import requests
from langchain_core.documents import Document


class ApiReranker(object):
    """API 式重排器，通过 rerank API 对候选文档排序。"""

    def __init__(self, model_path: str, max_length: int = 4096):
        self.model = model_path
        self._api_key = os.getenv("LLM_API_KEY", "").removeprefix("Bearer ").strip()
        self._base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")

    def rank(self, query: str, candidate_docs: list[Document], topk: int = 10) -> list[Document]:
        if not candidate_docs:
            return []

        documents = [doc.page_content for doc in candidate_docs]
        url = f"{self._base_url}/rerank"

        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_n": min(topk, len(documents)),
            "return_documents": False,
        }

        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Rerank] API 调用失败，降级使用原始顺序: {e}")
            return candidate_docs[:topk]

        results = data.get("results", [])
        if not results:
            return candidate_docs[:topk]

        indexed = [(item["index"], item["relevance_score"]) for item in results]
        indexed.sort(key=lambda x: x[1], reverse=True)

        ranked = []
        for idx, _ in indexed:
            if 0 <= idx < len(candidate_docs):
                ranked.append(candidate_docs[idx])
        return ranked[:topk]
