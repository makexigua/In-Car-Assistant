"""
自定义文本分割器 — 将分隔符留在句尾而非下一行开头。

LangChain 原版 RecursiveCharacterTextSplitter 在分割时，
分隔符（句号、换行等）会被留在下一块开头，导致分块边界不自然。
本模块修正此行为，让分隔符始终归属前一块。
"""

import re
from typing import List, Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter


class TailRecursiveCharacterTextSplitter(RecursiveCharacterTextSplitter):
    """将分隔符留在句尾的自定义分割器。

    用法与 RecursiveCharacterTextSplitter 完全一致，
    只是在分割完成后将原本在下一块开头的分隔符移至上一块末尾。
    """

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        # 父类标准分割（内部已处理递归降级 separator）
        chunks = super()._split_text(text, separators)
        return self._rehang_separators(chunks, separators)

    # ----------------------------------------------------------------
    # 静态工具
    # ----------------------------------------------------------------

    @staticmethod
    def _rehang_separators(
        chunks: List[str],
        separators: List[str],
    ) -> List[str]:
        """将下一块开头出现的分隔符＂挂回＂上一块末尾。"""
        if len(chunks) <= 1:
            return chunks

        # 分隔符按长度降序排列，确保长分隔符优先匹配（如 "\n\n" 在 "\n" 之前）
        ordered = sorted(
            [s for s in separators if s],
            key=len,
            reverse=True,
        )

        result = [chunks[0]]
        for chunk in chunks[1:]:
            # 贪婪移动：如果当前块以某个分隔符开头，就将它裁下接到前一块
            changed = True
            while changed:
                changed = False
                for sep in ordered:
                    while chunk.startswith(sep):
                        result[-1] += sep
                        chunk = chunk[len(sep) :]
                        changed = True
            result.append(chunk)

        return result
