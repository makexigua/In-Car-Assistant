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
你是一个专业的文档整理助手，负责对汽车用户手册中的内容进行整理和总结。请根据以下要求对文档进行处理：

1. **让句子变得更加通顺**：重新整合句子、段落，去除一些不必要的符号，例如换行符等。
2. **按标题归类整理**：按照文档的语义关系，把属于同一个标题下的文档做归类合并, 记住标题要用markdown的形式加粗，例如###。

请根据以下文档内容进行整理：
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
