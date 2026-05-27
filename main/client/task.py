# 作用：调用进程内 task pipeline，完成任务意图识别、MCP 调用和 NLG 输出（不再走本地任务 HTTP 服务）。

import os
from typing import Optional

from main.utils import logger
from main.utils.env_loader import load_project_env
from task.pipeline import run_task_pipeline

load_project_env()


def request_task(query, trace_id, enable_dm=True, function_scope: Optional[str] = None):
    if enable_dm is None:
        enable_dm = True

    if not os.getenv("LLM_BASE_URL", "") or not os.getenv("LLM_API_KEY", ""):
        logger.error("LLM_BASE_URL or LLM_API_KEY is empty.")
        return {}

    try:
        res = run_task_pipeline(
            query=query,
            trace_id=trace_id,
            enable_dm=enable_dm,
            function_scope=function_scope or "all",
        )
        logger.info(f"task链路的输出：{res}")
        return res
    except Exception as err:
        logger.error(f"run task pipeline failed: {err}")
        return {}


if __name__ == "__main__":
    while True:
        query = input("Input:")
        print(request_task(query, "123"))
