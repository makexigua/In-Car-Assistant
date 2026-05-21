# 作用：调用进程内 task pipeline，完成任务意图识别、MCP 调用和 NLG 输出（不再走本地 NLU HTTP 服务）。

import os
import sys
from pathlib import Path

from utils import logger
from utils.env_loader import load_project_env

load_project_env()

# 让 main 入口也能稳定导入根目录下的 task 模块。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from task.pipeline import run_task_pipeline


def request_nlu(query, trace_id, enable_dm=True):
    if enable_dm is None:
        enable_dm = True

    # 兼容旧调用：如果 task 侧缺模型配置，给出明确日志。
    if not os.getenv("LLM_BASE_URL", "") or not os.getenv("LLM_API_KEY", ""):
        logger.error("LLM_BASE_URL or LLM_API_KEY is empty.")
        return {}

    try:
        res = run_task_pipeline(query=query, trace_id=trace_id, enable_dm=enable_dm)
        logger.info(f"NLU模型的输出：{res}")
        return res
    except Exception as err:
        logger.error(f"run task pipeline failed: {err}")
        return {}


if __name__ == "__main__":
    while True:
        query = input("Input:")
        print(request_nlu(query, "123"))
