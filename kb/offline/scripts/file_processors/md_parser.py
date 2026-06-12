"""
Markdown 解析器 — 解析 .md 文件。

保留 Markdown 标题结构，按标题层级自动切分文档块。
"""

import hashlib
import re
from typing import List, Optional

from langchain_core.documents import Document
from tqdm import tqdm

from kb.offline.scripts.file_processors.base_parser import BaseParser


class MdParser(BaseParser):
    """Markdown (.md) 格式解析器。"""

    def supported_extensions(self) -> List[str]:
        return [".md", ".markdown"]

    def parse(
        self,
        file_path: str,
        encoding: str = "utf-8",
        split_by_heading: bool = True,
        **kwargs,
    ) -> List[Document]:
        """
        解析 Markdown 文件。

        Args:
            file_path: .md 文件路径
            encoding: 文件编码
            split_by_heading: 是否按标题 (## / ###) 切分文档块

        Returns:
            List[Document]: 解析结果
        """
        with open(file_path, "r", encoding=encoding) as f:
            text = f.read()

        if not text.strip():
            return []

        if split_by_heading:
            sections = self._split_by_headings(text)
        else:
            sections = [("", text.strip())]

        raw_docs = []
        for heading, content in tqdm(sections, desc="解析 Markdown"):
            if not content.strip():
                continue

            full_content = f"# {heading}\n{content}" if heading else content
            unique_id = hashlib.md5(full_content.encode("utf-8")).hexdigest()
            metadata = {
                "unique_id": unique_id,
                "source": file_path,
                "format": "markdown",
                "heading": heading or "",
            }
            raw_docs.append(
                Document(page_content=full_content, metadata=metadata)
            )

        print(f"[MdParser] 解析完成: {file_path} → {len(raw_docs)} 个章节")
        return raw_docs

    def _split_by_headings(self, text: str) -> List[tuple]:
        """
        按 Markdown 标题 (## ~ ######) 切分文本。

        Returns:
            List[tuple]: [(heading, content), ...]
        """
        # 匹配 ## ~ ###### 级别的标题（跳过 # 一级标题）
        pattern = re.compile(
            r"^(#{2,6})\s+(.+?)$", re.MULTILINE
        )

        sections = []
        last_pos = 0
        last_heading = ""

        for match in pattern.finditer(text):
            # 上一个 section
            if match.start() > last_pos:
                content = text[last_pos:match.start()].strip()
                if content or last_heading:
                    sections.append((last_heading, content))

            last_heading = match.group(2).strip()
            last_pos = match.start()

        # 最后一段
        remaining = text[last_pos:].strip()
        if remaining:
            sections.append((last_heading, remaining))

        # 如果没有任何标题匹配，整篇作为一个 section
        if not sections and text.strip():
            sections.append(("", text.strip()))

        return sections


# ---- 便利函数 ----
def load_md(file_path: str, **kwargs) -> List[Document]:
    """便利函数，可直接调用。"""
    return MdParser().parse(file_path, **kwargs)
