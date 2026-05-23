from pathlib import Path
import os

# 在线目录（当前文件位于 kb/online/src 下）
ONLINE_DIR = Path(__file__).resolve().parents[1]
# kb 根目录
KB_DIR = ONLINE_DIR.parent
base_dir = str(ONLINE_DIR) + "/"

# 在线检索读取的是离线产出的数据目录，可通过环境变量覆盖。
OFFLINE_DIR = Path(os.getenv("KB_OFFLINE_DIR", str(KB_DIR / "offline")))
DATA_DIR = Path(os.getenv("KB_DATA_DIR", str(OFFLINE_DIR / "data")))
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PROCESSED_DOCS_DIR = PROCESSED_DATA_DIR / "docs"
PROCESSED_IMAGES_DIR = PROCESSED_DATA_DIR / "images"
PROCESSED_INDEX_DIR = PROCESSED_DATA_DIR / "index"


def _ensure_kb_data_dirs() -> None:
    """
    启动时保证关键目录存在，避免首次运行时因为目录缺失直接报错。
    """
    for path in (
        RAW_DATA_DIR,
        PROCESSED_DOCS_DIR,
        PROCESSED_IMAGES_DIR,
        PROCESSED_INDEX_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


_ensure_kb_data_dirs()

# 数据路径
stopwords_path = str(RAW_DATA_DIR / "stopwords.txt")
image_save_dir = str(PROCESSED_IMAGES_DIR)

# 索引路径
bm25_pickle_path = str(PROCESSED_INDEX_DIR / "bm25retriever.pkl")
milvus_db_path = str(PROCESSED_INDEX_DIR / "milvus.db")

# 模型路径（可通过 KB_MODELS_DIR 覆盖）
models_dir = Path(os.getenv("KB_MODELS_DIR", str(KB_DIR / "models")))
bge_m3_model_path = str(models_dir / "BAAI" / "bge-m3")
bge_reranker_model_path = str(models_dir / "BAAI" / "bge-reranker-v2-m3")
