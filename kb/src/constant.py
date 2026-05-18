from pathlib import Path
import os

# 基于当前文件自动定位 kb 根目录，避免硬编码机器路径。
KB_DIR = Path(__file__).resolve().parents[1]
base_dir = str(KB_DIR) + "/"

# 数据路径
pdf_path = str(KB_DIR / "data" / "Tesla_Manual.pdf")
test_doc_path = str(KB_DIR / "data" / "test_docs.txt")
stopwords_path = str(KB_DIR / "data" / "stopwords.txt")
image_save_dir = str(KB_DIR / "data" / "saved_images")
raw_docs_path = str(KB_DIR / "data" / "processed_docs" / "raw_docs.pkl")
clean_docs_path = str(KB_DIR / "data" / "processed_docs" / "clean_docs.pkl")
split_docs_path = str(KB_DIR / "data" / "processed_docs" / "split_docs.pkl")

# 索引路径
bm25_pickle_path = str(KB_DIR / "data" / "saved_index" / "bm25retriever.pkl")
tfidf_pickle_path = str(KB_DIR / "data" / "saved_index" / "tfidfretriever.pkl")
milvus_db_path = str(KB_DIR / "data" / "saved_index" / "milvus.db")
faiss_db_path = str(KB_DIR / "data" / "saved_index" / "faiss.db")
faiss_qwen_db_path = str(KB_DIR / "data" / "saved_index" / "faiss_qwen.db")

# 模型路径（可通过 KB_MODELS_DIR 覆盖）
models_dir = Path(os.getenv("KB_MODELS_DIR", str(KB_DIR / "models")))
m3e_small_model_path = str(models_dir / "AI-ModelScope" / "m3e-small")
bge_m3_model_path = str(models_dir / "BAAI" / "bge-m3")
bce_model_path = str(models_dir / "maidalun" / "bce-embedding-base_v1")
qwen3_embedding_model_path = str(models_dir / "Qwen3-Embedding-0.6B")
qwen3_reranker_model_path = str(models_dir / "Qwen3-Reranker-0.6B")
qwen3_4b_reranker_model_path = str(models_dir / "Qwen3-Reranker-4B")
bge_reranker_model_path = str(models_dir / "BAAI" / "bge-reranker-v2-m3")
bge_reranker_tuned_model_path = os.getenv(
    "KB_TUNED_RERANKER_PATH",
    str(models_dir / "bge-reranker-tuned")
)
bge_reranker_minicpm_path = str(models_dir / "bge-reranker-v2-minicpm-layerwise")
text2vec_model_path = str(models_dir / "text2vec-base-chinese")
qwen3_8b_tune_model_name = os.getenv("RAG_LOCAL_MODEL_NAME", "LLaMA-Factory-main/output/qwen3_lora_sft_int4")
