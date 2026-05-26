import os
import concurrent.futures
from tqdm import tqdm
from langchain_core.documents import Document
from openai import OpenAI

from kb.offline.config.env_loader import load_project_env
from kb.offline.config.settings import DEFAULT_CHAT_MODEL

load_project_env()

MAX_WORKERS = 5

LLM_CLEAN_PROMPT = """
你是一个文档格式整理助手。请对以下文本做**纯格式整理**，不要改动任何文字内容、不要归纳总结、不要调整段落顺序：

1. **删除多余空行**：连续空行合并为一段间距
2. **修复断行**：同一段落内被换行符截断的句子重新连起来
3. **清理无关符号**：去除乱码、多余空格等格式噪声
4. **保留标题层级**：原有的 ### 标题保留不动

请直接输出整理后的文本，不要添加任何额外说明：

{}
整理后的输出：
"""

llm_client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "").removeprefix("Bearer ").strip(),
    base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
)


def _chat(doc: str) -> str | None:
    try:
        completion = llm_client.chat.completions.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[{"role": "user", "content": doc}],
            top_p=0,
            temperature=0.001,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[text_cleaner] API 调用失败，跳过: {e}")
        return None


def clean(docs: list[Document]) -> list[Document]:
    clean_docs = []
    docs_mapping = {doc.metadata["unique_id"]: doc for doc in docs}
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            doc.metadata["unique_id"]: executor.submit(
                _chat, LLM_CLEAN_PROMPT.format(doc.page_content)
            )
            for doc in docs
        }

        for unique_id in tqdm(futures, desc="文本清洗"):
            future = futures[unique_id]
            try:
                result = future.result()
            except Exception as e:
                print(f"[text_cleaner] 处理 {unique_id} 时异常: {e}")
                failed += 1
                continue
            if not result:
                failed += 1
                continue
            clean_docs.append(
                Document(page_content=result, metadata=docs_mapping[unique_id].metadata)
            )

    if failed:
        print(f"[text_cleaner] 清洗完成，共 {len(clean_docs)} 条成功，{failed} 条失败跳过")
    return clean_docs
