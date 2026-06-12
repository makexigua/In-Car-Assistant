"""
PDF 解析器 — 基于 PyMuPDF (fitz)。

从 PDF 中提取文本+图片，返回 Document 列表。
"""

import hashlib
from typing import List, Optional

import fitz
from langchain_core.documents import Document
from tqdm import tqdm

from kb.offline.config import settings
from kb.offline.scripts.file_processors.base_parser import BaseParser
from kb.offline.scripts.file_processors.image_handler import handle_page_images


class PDFParser(BaseParser):
    """PDF 格式解析器。"""

    # 默认过滤配置
    _min_filter_pages: int = 4
    _max_filter_pages: int = 247
    _page_clip: int = 50  # 底部裁切像素数，去掉页脚

    def supported_extensions(self) -> List[str]:
        return [".pdf"]

    def parse(
        self,
        file_path: str,
        min_page: Optional[int] = None,
        max_page: Optional[int] = None,
        page_clip: Optional[int] = None,
        extract_images: bool = True,
        **kwargs,
    ) -> List[Document]:
        """
        解析 PDF 文件。

        Args:
            file_path: PDF 文件路径
            min_page: 起始页（0-index，覆盖默认 _min_filter_pages）
            max_page: 结束页（0-index，覆盖默认 _max_filter_pages）
            page_clip: 底部裁切像素数
            extract_images: 是否提取图片

        Returns:
            List[Document]: 每页一个 Document
        """
        min_page = min_page if min_page is not None else self._min_filter_pages
        max_page = max_page if max_page is not None else self._max_filter_pages
        clip = page_clip if page_clip is not None else self._page_clip

        pdf = fitz.open(file_path)
        raw_docs: List[Document] = []

        for idx, page_num in enumerate(tqdm(range(len(pdf)), desc="解析 PDF")):
            if idx < min_page or idx > max_page:
                continue

            page = pdf.load_page(page_num)
            crop = fitz.Rect(0, 0, page.rect.width, page.rect.height - clip)
            text = page.get_text(clip=crop)

            # 提取图片
            images_info = []
            if extract_images:
                images = page.get_images(full=True)
                images_info = handle_page_images(images, page)

            if text.strip():
                unique_id = hashlib.md5(text.encode("utf-8")).hexdigest()
                metadata = {
                    "unique_id": unique_id,
                    "source": file_path,
                    "page": page_num + 1,
                    "images_info": images_info,
                }
                raw_docs.append(Document(page_content=text, metadata=metadata))

        pdf.close()
        return raw_docs


# ---- 兼容旧版入口（已删除原 scripts/pdf_parser.py，保留此函数供直接调用） ----
legacy_pdf_path = settings.pdf_path


def load_pdf(
    file_path: Optional[str] = None,
    min_page: Optional[int] = None,
    max_page: Optional[int] = None,
) -> List[Document]:
    """
    兼容旧的 load_pdf() 函数签名。

    如果未来旧版调用全部迁移后可以删除此函数。
    """
    parser = PDFParser()
    return parser.parse(
        file_path or legacy_pdf_path,
        min_page=min_page,
        max_page=max_page,
    )
