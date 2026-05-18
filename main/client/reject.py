# 作用：调用拒识服务，判断用户问题是否合规可继续处理。

import json
import os

import requests
from utils import logger
from utils.env_loader import load_project_env


THRESHOLD = 0.5
REQUEST_TIMEOUT = 5.0


load_project_env()
REJECT_URL = os.getenv("REJECT_URL", "")


def request_reject(query, trace_id):
    if not REJECT_URL:
        logger.error("REJECT_URL is empty, default pass.")
        return "是"

    payload = json.dumps({"query": query, "thres": THRESHOLD, "trace_id": trace_id}, ensure_ascii=False)
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(REJECT_URL, headers=headers, data=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        text = response.json()["data"]
        logger.info(f"拒识模型的输出：{text}")
        return text
    except Exception as err:
        logger.error(f"call reject failed:{err}")
        return "是"


if __name__ == "__main__":
    while True:
        query = input("Input:")
        print(request_reject(query, "123"))
