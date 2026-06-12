"""
解析器基类 — 所有文件格式解析器统一继承此接口。

每个解析器子类需要实现:
    - supported_extensions(): 返回支持的扩展名列表
    - parse(): 解析文件并返回 Document 列表
"""

from abc import ABC, abstractmethod
from typing import List

from langchain_core.documents import Document


class BaseParser(ABC):
    """所有文件解析器的抽象基类。"""

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        返回此解析器支持的文件扩展名列表（含点号）。

        Returns:
            List[str]: 如 ['.pdf'], ['.docx'], ['.xlsx', '.xls']
        """
        ...

    @abstractmethod
    def parse(self, file_path: str, **kwargs) -> List[Document]:
        """
        解析文件并返回 Document 列表。

        Args:
            file_path: 文件路径
            **kwargs: 解析器特定的扩展参数

        Returns:
            List[Document]: 解析后的文档列表

        Raises:
            ValueError: 文件格式或内容有问题时抛出
        """
        ...

    def __str__(self) -> str:
        exts = ", ".join(self.supported_extensions())
        return f"{self.__class__.__name__}({exts})"
