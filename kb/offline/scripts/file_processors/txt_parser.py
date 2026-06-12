"""
纯文本解析器 — 读取 .txt 文件。

支持多种编码自动检测（UTF-8 / GBK / GB2312）。
"""

import hashlib
import os
from typing import List, Optional

from langchain_core.documents import Document
from tqdm import tqdm

from kb.offline.scripts.file_processors.base_parser import BaseParser


# 探测编码时的备选列表
_FALLBACK_ENCODINGS = ["utf-8", "gbk", "gb2312", "utf-16", "latin-1"]


class TxtParser(BaseParser):
    """纯文本 (.txt) 格式解析器。"""

    def supported_extensions(self) -> List[str]:
        return [".txt"]

    def parse(
        self,
        file_path: str,
        encoding: Optional[str] = None,
        chunk_by_blank_line: bool = True,
        **kwargs,
    ) -> List[Document]:
        """
        解析 TXT 文件。

        Args:
            file_path: .txt 文件路径
            encoding: 指定编码（默认自动探测）
            chunk_by_blank_line: 是否按空行分隔成多个 Document

        Returns:
            List[Document]: 解析结果
        """
        text = self._read_file(file_path, encoding)

        if not text.strip():
            return []

        if chunk_by_blank_line:
            # 按连续空行切分段落
            import re
            paragraphs = re.split(r"\n\s*\n", text)
            paragraphs = [p.strip() for p in paragraphs if p.strip()]
        else:
            paragraphs = [text.strip()]

        raw_docs = []
        for para in tqdm(paragraphs, desc="解析 TXT"):
            unique_id = hashlib.md5(para.encode("utf-8")).hexdigest()
            metadata = {
                "unique_id": unique_id,
                "source": file_path,
                "format": "txt",
            }
            raw_docs.append(Document(page_content=para, metadata=metadata))

        print(f"[TxtParser] 解析完成: {file_path} → {len(raw_docs)} 个段落")
        return raw_docs

    def _read_file(self, file_path: str, encoding: Optional[str] = None) -> str:
        """读取文本文件，自动探测编码。"""
        if encoding is not None:
            # 指定编码
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()

        # 自动探测编码
        for enc in _FALLBACK_ENCODINGS:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue

        raise ValueError(
            f"无法解码文件: {file_path}，"
            f"尝试编码: {_FALLBACK_ENCODINGS}"
        )


# ---- 便利函数 ----
def load_txt(file_path: str, **kwargs) -> List[Document]:
    """便利函数，可直接调用。"""
    return TxtParser().parse(file_path, **kwargs)
