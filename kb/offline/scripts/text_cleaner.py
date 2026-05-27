"""
纯规则文本清洗 — 毫秒级完成，替代原来的 LLM 逐页清洗。

之前每条都调 LLM 做"删空行、修断行、去乱码"这种规则活，
244 页预估 3.7 小时。现在用正则，秒级完成。
"""

import re
from langchain_core.documents import Document


def _rule_clean(text: str) -> str:
    """纯规则整理文本，不做任何语义修改。"""
    # 1. 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. 删除孤立的空白行（只含空格/Tab 的行视为空行）
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)

    # 3. 连续空行合并为一段间距（最多保留两个空行）
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. 修复断行：非中文标点结尾的行尾换行 → 空格
    #    （同一段落被换行符截断的句子连回来）
    text = re.sub(r"(?<![。！？；：」」』】》》）)])[\n]", " ", text)

    # 5. 修复断行后产生的多余空格
    text = re.sub(r" {2,}", " ", text)

    # 6. 清理每行首尾空白
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # 7. 删除开头和结尾的空白行
    text = text.strip()

    return text


def clean(docs: list[Document]) -> list[Document]:
    """用纯规则清洗文档文本，无需 LLM。"""
    clean_docs = []
    for doc in docs:
        cleaned = _rule_clean(doc.page_content)
        clean_docs.append(Document(page_content=cleaned, metadata=doc.metadata))
    print(f"[text_cleaner] 规则清洗完成，共 {len(clean_docs)} 条")
    return clean_docs
