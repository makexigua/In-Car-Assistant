# 作用：集中维护 task 链路的路径、模型配置和默认参数，避免散落在多个文件里。

import os
from pathlib import Path

from main.utils.env_loader import load_project_env


load_project_env()

TASK_DIR = Path(__file__).resolve().parent
CLASS_FILE = TASK_DIR / "config" / "class.txt"
SLOT_INTENT_FILE = TASK_DIR / "config" / "slot_intent.json"
AMP_SERVER_PATH = str(TASK_DIR / "mcp_core" / "amp_server.py")
MUSIC_SERVER_PATH = str(TASK_DIR / "mcp_core" / "music_server.py")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
FUNCTION_CALL_MODEL = os.getenv("FUNCTION_CALL_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
NLG_MODEL = os.getenv("NLG_MODEL", os.getenv("DEFAULT_CHAT_MODEL", ""))
REQUEST_TIMEOUT = float(os.getenv("TASK_LLM_TIMEOUT", "12"))
RECALL_TOP_K = int(os.getenv("TASK_RECALL_TOP_K", "5"))
DEFAULT_NLG = os.getenv("DEFAULT_NLG", "抱歉，这个问题我还在学习中")
