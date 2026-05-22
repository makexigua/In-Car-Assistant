import random
import json
import requests
import os
import pickle

from src.constant import clean_docs_path

# 默认走本机语义切块服务，可通过环境变量覆盖。
URL = os.getenv("SEMANTIC_CHUNK_URL", "http://127.0.0.1:6000/v1/semantic-chunks")


def request_semantic_chunk(sentences, group_size):
    headers = {
        "Content-Type":"application/json"
    }
    payload = json.dumps({
        "sentences": sentences,
        "group_size": group_size
    })
    try:
        response = requests.post(
            URL,
            headers=headers,
            data=payload
        )
        res = response.json()
        text = res["chunks"]
    except Exception as e:
        print(f"call semantic chunk failed:{e}")
        text = sentences
    return text


if __name__ == '__main__':
    data = pickle.load(open(clean_docs_path, "rb"))
    index = random.sample(range(len(data)), 10)
    for idx in index:
        doc = data[idx].page_content
        res = request_semantic_chunk(doc, 10)
        print("="*100)
        for r in res:
            print(r)
            print("="*100)
