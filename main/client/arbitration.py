# -*- coding: utf-8 -*-
# --------------------------------------------
# 项目名称: LLM任务型对话Agent
# 版权所有  ©2025丁师兄大模型
# 生成时间: 2025-05
# --------------------------------------------

import time
import json
import os
import requests
import prompts
from utils import logger
from utils.redis_tool import RedisClient
from utils.env_loader import load_project_env


TIMEOUT = 2.0
MAX_HIS = 6
TTL = 60
CHUNK_SIZE = 1024
MAX_TOKEN = 2048
REDIS_KEY = "voice:arbitration_history:"
_redis_client = RedisClient() 


load_project_env()
API_KEY = os.getenv("LLM_API_KEY", os.getenv("API_KEY", ""))
DOUBAO_URL = os.getenv("LLM_BASE_URL", os.getenv("BASE_URL", ""))
ARBITRATION_MODEL = os.getenv("ARBITRATION_MODEL", os.getenv("DEFAULT_CHAT_MODEL", "ep-20250122160643-vj459"))
SYSTEM_PROMPT = prompts.ARBITRAION_SYSTEM_PROMPT


def request_arbitration(query, sender_id):
    headers = {
        "Content-Type": "application/json",
        "Authorization": API_KEY
    }
    message = [{"role": "system", "content": SYSTEM_PROMPT}]

    try:
        start_time = time.time()
        history = _redis_client.get(REDIS_KEY + sender_id)
        if history:
            history = json.loads(history)
        else:
            history = []
        # history = []
        history.append({"role": "user", "content": query})

        message.extend(history)

        body = dict(
            model=ARBITRATION_MODEL,
            messages=message,
            max_tokens=MAX_TOKEN,
            temperature=0,
            stream=True
        )
        response = requests.post(
            DOUBAO_URL,
            headers=headers,
            json=body,
            stream=True,
            timeout=TIMEOUT
        )
        text = "A"
        for r in response.iter_lines(
                chunk_size=CHUNK_SIZE, decode_unicode=False, delimiter=b'\n'):
            r = r.decode("utf-8")
            if not r:
                continue
            r = r.lstrip("data: ")
            if r == "[DONE]":
                break
            r = json.loads(r.lstrip("data: "))
            text = r["choices"][0]["delta"]["content"]
            if not text:
                continue
            break
        logger.info(
            f"Arbitration history: {history}, query:{query}, result:{text}, cost time:{time.time() - start_time}")
        if text not in ["A", "B", "C", "D"]:
            text = "A"
        history.append({"role": "assistant", "content": text})
        history = history[-MAX_HIS:]
        history_str = json.dumps(history, ensure_ascii=False)
        _redis_client.set(REDIS_KEY + sender_id, history_str, ex=TTL)
        if text in ["C", "D"]:
            text = "chat"
        elif text == "B":
            text = "faq"
        else:
            text = "task"

        return text

    except Exception as e:
        logger.info(f"Arbitration API error: {e}")
        return "task"


if __name__ == '__main__':
    while True:
        query = input("输入:")
        res = request_arbitration(query, "131")
        print(res)
