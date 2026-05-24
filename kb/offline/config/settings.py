from pathlib import Path
import os

from config.env_loader import load_project_env

load_project_env()

# 离线目录（当前文件位于 kb/offline/config 下）
CONFIG_DIR = Path(__file__).resolve().parent
OFFLINE_DIR = CONFIG_DIR.parent
# kb 根目录
KB_DIR = OFFLINE_DIR.parent
base_dir = str(OFFLINE_DIR) + "/"

# 离线数据目录：原始资料与处理产物都在这里。
DATA_DIR = OFFLINE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PROCESSED_DOCS_DIR = PROCESSED_DATA_DIR / "docs"
PROCESSED_IMAGES_DIR = PROCESSED_DATA_DIR / "images"
PROCESSED_INDEX_DIR = PROCESSED_DATA_DIR / "index"

# 微调相关目录：统一归档到 data/finetune。
FINETUNE_DIR = DATA_DIR / "finetune"
FINETUNE_DATASETS_DIR = FINETUNE_DIR / "datasets"
FINETUNE_MODELS_DIR = FINETUNE_DIR / "models"


def _ensure_kb_data_dirs() -> None:
    """
    启动时保证关键目录存在，避免首次运行时因为目录缺失直接报错。
    """
    for path in (
        RAW_DATA_DIR,
        PROCESSED_DOCS_DIR,
        PROCESSED_IMAGES_DIR,
        PROCESSED_INDEX_DIR,
        FINETUNE_DATASETS_DIR,
        FINETUNE_MODELS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


_ensure_kb_data_dirs()

# 数据路径
pdf_path = str(RAW_DATA_DIR / "Tesla_Manual.pdf")
stopwords_path = str(RAW_DATA_DIR / "stopwords.txt")
image_save_dir = str(PROCESSED_IMAGES_DIR)
raw_docs_path = str(PROCESSED_DOCS_DIR / "raw_docs.pkl")
clean_docs_path = str(PROCESSED_DOCS_DIR / "clean_docs.pkl")
split_docs_path = str(PROCESSED_DOCS_DIR / "split_docs.pkl")

# 索引路径
bm25_pickle_path = str(PROCESSED_INDEX_DIR / "bm25retriever.pkl")
milvus_db_path = str(PROCESSED_INDEX_DIR / "milvus.db")


SEMANTIC_MODEL = os.getenv("SEMANTIC_MODEL", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")
RERANK_MODEL = os.getenv("RERANK_MODEL","")
