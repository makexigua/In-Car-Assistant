import os
import json
import re
from openai import OpenAI
from langchain_core.documents import Document
from kb.offline.config.env_loader import load_project_env


load_project_env()

LLM_CHAT_PROMPT = """
### 信息
{context}

### 任务
你是特斯拉电动汽车Model 3车型的用户手册问答系统，你具备{{信息}}中的知识。
请回答问题"{query}"，答案需要精准、语句通顺，并严格按照以下格式输出

{{答案}}。【{{页码1}}, {{页码2}}, ...】

例如：
- 请按方向盘左侧的调节杆来调整高度。【12】
- 可以通过中控屏幕设置定时充电。【25, 26】

要求：
1. 【句子整理】如果原文缺少标点断句、句式过长难以阅读，请主动加标点、拆分长句，确保回答通顺易读。
2. 【页码标注】每条信息开头的【X】即为该内容对应的页码。请根据实际参考内容填写对应页码，而不是标注信息编号。不要输出"参考来源"之类的额外说明文字。
3. 如果无法从中得到答案，请说 "无答案" ，不允许在答案中添加编造成分。
"""


RAG_LLM_TIMEOUT = float(os.getenv("RAG_LLM_TIMEOUT", "60"))

llm_client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "").removeprefix("Bearer ").strip(),
    base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
    timeout=RAG_LLM_TIMEOUT,
)


def request_chat(query, context, stream=False):

    prompt = LLM_CHAT_PROMPT.format(context=context, query=query)

    completion = llm_client.chat.completions.create(
        model=os.getenv("DEFAULT_CHAT_MODEL", ""),
        messages=[
            {"role": "system", "content": "你是一个有用的人工智能助手."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=4096,
        frequency_penalty=2.0,
        temperature=0.001,
        top_p=0.95,
        stream=stream,
        extra_body={
            "top_k": 1,
            "chat_template_kwargs": {"enable_thinking": False}
        }
    )
    if not stream:
        result = completion.choices[0].message.content
    else:
        result = completion

    return result
