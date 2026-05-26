import json
import hashlib
import fitz
from tqdm import tqdm
from langchain_core.documents import Document
from typing_extensions import List

from kb.offline.config import settings
from kb.offline.config.models import ManualImages
from kb.offline.scripts import image_handler


# 全局配置
_min_filter_pages = 4
_max_filter_pages = 247
_page_clip = 50
file_path = settings.pdf_path


def load_pdf() -> list[Document]:
    pdf = fitz.open(file_path)
    raw_docs = []

    for idx, page_num in enumerate(tqdm(range(len(pdf)))):
        # 过滤封面和目录
        if idx < _min_filter_pages or idx > _max_filter_pages:
            continue

        page = pdf.load_page(page_num)
        crop = fitz.Rect(0, 0, page.rect.width, page.rect.height - _page_clip)
        text = page.get_text(clip=crop)
        images = page.get_images(full=True)

        manual_images_list: List[ManualImages] = []
        for img_index, img in enumerate(images):
            manual_image = image_handler.handle_image(img, img_index, page)
            if manual_image:
                manual_images_list.append(json.loads(manual_image.json()))

        if text.strip():
            unique_id = hashlib.md5(text.encode("utf-8")).hexdigest()
            metadata = {
                "unique_id": unique_id,
                "source": file_path,
                "page": page_num + 1,
                "images_info": manual_images_list,
            }

            raw_docs.append(Document(page_content=text, metadata=metadata))

    return raw_docs
