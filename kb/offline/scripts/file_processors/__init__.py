"""
文件处理器包 — 支持多格式文档解析。

统一入口函数:
    parse_document(file_path, **kwargs) -> List[Document]
    batch_parse_directory(dir_path, **kwargs) -> Dict[str, List[Document]]

支持的格式通过 SUPPORTED_EXTENSIONS 查看。
"""

from typing import Dict, List, Optional

from langchain_core.documents import Document

from kb.offline.scripts.file_processors.base_parser import BaseParser
from kb.offline.scripts.file_processors.pdf_parser import PDFParser
from kb.offline.scripts.file_processors.docx_parser import DOCXParser
from kb.offline.scripts.file_processors.xlsx_parser import XLSXParser
from kb.offline.scripts.file_processors.ppt_parser import PPTParser
from kb.offline.scripts.file_processors.txt_parser import TxtParser
from kb.offline.scripts.file_processors.md_parser import MdParser

# 所有已注册的解析器（按扩展名映射）
_REGISTERED_PARSERS: Dict[str, BaseParser] = {}

def _register(parser: BaseParser) -> None:
    for ext in parser.supported_extensions():
        _REGISTERED_PARSERS[ext.lower()] = parser

# 注册所有内置解析器
_register(PDFParser())
_register(DOCXParser())
_register(XLSXParser())
_register(PPTParser())
_register(TxtParser())
_register(MdParser())

SUPPORTED_EXTENSIONS = sorted(_REGISTERED_PARSERS.keys())


def get_parser(file_path: str) -> Optional[BaseParser]:
    """根据文件扩展名自动选择对应的解析器。"""
    import os
    ext = os.path.splitext(file_path)[1].lower()
    return _REGISTERED_PARSERS.get(ext)


def parse_document(file_path: str, **kwargs) -> List[Document]:
    """
    解析单个文档，自动识别格式。

    Args:
        file_path: 文件路径
        **kwargs: 传递给具体解析器的额外参数

    Returns:
        List[Document]: 解析后的文档列表（通常每页/每sheet/每页一张）

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的格式或解析失败
    """
    import os

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    parser = get_parser(file_path)
    if parser is None:
        raise ValueError(
            f"不支持的文件格式: {file_path}，"
            f"当前支持的格式: {SUPPORTED_EXTENSIONS}"
        )

    return parser.parse(file_path, **kwargs)


def batch_parse_directory(
    dir_path: str,
    recursive: bool = False,
    **kwargs,
) -> Dict[str, List[Document]]:
    """
    批量解析目录下所有支持格式的文件。

    Args:
        dir_path: 目录路径
        recursive: 是否递归遍历子目录
        **kwargs: 传递给 parse_document 的额外参数

    Returns:
        Dict[str, List[Document]]: {文件名: [Document, ...]} 的映射
    """
    import os
    from pathlib import Path

    base = Path(dir_path)
    if not base.exists():
        raise FileNotFoundError(f"目录不存在: {dir_path}")
    if not base.is_dir():
        raise NotADirectoryError(f"路径不是目录: {dir_path}")

    pattern = "**/*" if recursive else "*"
    results = {}
    for fpath in sorted(base.glob(pattern)):
        if not fpath.is_file():
            continue
        ext = fpath.suffix.lower()
        if ext not in _REGISTERED_PARSERS:
            continue
        try:
            docs = parse_document(str(fpath), **kwargs)
            results[str(fpath)] = docs
        except Exception as e:
            print(f"[警告] 解析失败 {fpath}: {e}")
            continue

    return results


# 为方便导入，将常用解析器类暴露在包顶层
__all__ = [
    "BaseParser",
    "PDFParser",
    "DOCXParser",
    "XLSXParser",
    "PPTParser",
    "TxtParser",
    "MdParser",
    "parse_document",
    "batch_parse_directory",
    "get_parser",
    "SUPPORTED_EXTENSIONS",
]
