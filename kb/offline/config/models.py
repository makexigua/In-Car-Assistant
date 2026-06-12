from typing import Optional

from pydantic import BaseModel, Field


class DocImages(BaseModel):
    """文档中的图片信息（通用，不限于 PDF）。"""
    page: Optional[int] = Field(ge=1, description="页码从1开始")
    image_path: Optional[str] = Field(min_length=1, description="图片存储路径")
    title: Optional[str] = Field(
        description="标题内容，多个区块用换行符连接"
    )


class DocInfo(BaseModel):
    """通用文档分片信息。"""
    unique_id: str = Field(description="唯一标识符")
    metadata: dict = Field(description="存储文档的meta信息")
    page_content: Optional[str] = Field(description="文档分片的内容")


# 向后兼容别名
ManualImages = DocImages
ManualInfo = DocInfo
