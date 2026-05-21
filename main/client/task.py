# 作用：调用任务型 NLU 服务，返回意图、槽位和 function-calling 结果。

import json
import os
import requests
from utils import logger
from utils.env_loader import load_project_env

REQUEST_TIMEOUT = 8.0

load_project_env()
NLU_URL = os.getenv("NLU_URL", "")


def request_nlu(query, trace_id, enable_dm=True):
    if not NLU_URL:
        logger.error("NLU_URL is empty.")
        return {}

    payload = json.dumps(
        {"query": query, "trace_id": trace_id, "enable_dm": enable_dm},
        ensure_ascii=False,
    )
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(NLU_URL, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        res = response.json()
        logger.info(f"NLU模型的输出：{res}")
        return res
    except Exception as err:
        logger.error(f"call NLU failed:{err}")
        return {}


if __name__ == "__main__":
    while True:
        query = input("Input:")
        print(request_nlu(query, "123"))
