import copy
import json
import os
import time
import traceback
from typing import Any, Dict, Tuple

from flask import Flask, jsonify, make_response
from flask_socketio import SocketIO, emit

import prompts
from client.arbitration import request_arbitration
from client.nlu import request_nlu
from client.rag import request_rag
from client.reject import request_reject
from client.rewrite import request_rewrite
from client.stream_chat import process_chat, request_chat
from utils import logger
from utils.env_loader import load_project_env
from utils.redis_tool import RedisClient


socketio = SocketIO(cors_allowed_origins='*', async_mode='threading')
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
socketio.init_app(app)


load_project_env()
TTL = 40
REDIS_KEY = "voice:last_service:{}"
redis_client = RedisClient() 

# 输出意图映射。这里单独抽出来，后面要扩展新域不会改一堆 if/else。
INTENT_META = {
    "CHAT": ("闲聊百科", "439"),
    "REJECT": ("拒识", "440"),
    "FAQ": ("知识库问答", "441"),
}


@app.route("/health", methods=["GET"])
def check():
    response = make_response(
        jsonify(health="healthy"),
        200,
        {'content-type': 'application/json'}
    )
    return response


@socketio.on('connect')
def connected_msg():
    manager = socketio.server.manager
    connections_count = len(manager.rooms['/']) - 1
    logger.info(f'当前连接数: {connections_count}')
    logger.info('client connected.')


@socketio.on('disconnect')
def disconnect_msg():
    logger.info('client disconnected.')


def build_nlu_template(query: str, trace_id: str, begin_ts: float) -> Dict[str, Any]:
    """
    统一返回模板，避免每条分支自己拼导致字段不一致。
    """
    return {
        "query": query,
        "tarce_id": trace_id,
        "intent": "",
        "intent_id": "",
        "function": "",
        "slots": {},
        "cost": time.time() - begin_ts
    }


def parse_last_info(sender_id: str) -> Tuple[str, str, str, str]:
    """
    读取并解析上一轮会话缓存。
    格式：domain#query#reject#answer
    """
    raw = redis_client.get(REDIS_KEY.format(sender_id))
    if not raw:
        return "", "", "", ""

    # answer 里可能包含 #，所以最多切 3 次，最后一个字段整体当 answer。
    items = raw.split("#", 3)
    if len(items) != 4:
        return "", "", "", ""
    return items[0], items[1], items[2], items[3]


def is_reject_passed(reject_result: Any) -> bool:
    """
    拒识结果兼容处理。
    老服务可能返回 0/1，也可能返回 是/否，所以统一在入口做归一。
    """
    value = str(reject_result).strip().lower()
    pass_values = {"1", "是", "true", "yes", "y", "pass", "合法"}
    reject_values = {"0", "否", "false", "no", "n", "reject", "非法"}
    if value in pass_values:
        return True
    if value in reject_values:
        return False
    # 保守策略：未知值默认放行，避免误杀正常用户查询
    return True


def send_msg(nlu_result, func, frame, seq, cost, status):
    intent, intent_id = INTENT_META.get(func, INTENT_META["REJECT"])

    nlu_result["intent"] = intent
    nlu_result["intent_id"] = intent_id
    nlu_result["func"] = func
    nlu_result["frame"] = frame
    nlu_result["seq"] = seq
    nlu_result["cost"] = cost
    nlu_result["status"] = status

    emit(
        "request_nlu",
        json.dumps(nlu_result, ensure_ascii=False),
        broadcast=False
    )


def send_faq(nlu_result: Dict[str, Any], answer: str, begin: float) -> None:
    """
    FAQ 非流式场景：走单帧输出，客户端处理更简单。
    """
    send_msg(nlu_result, "FAQ", answer, 1, time.time() - begin, status=2)


def handle_chat(nlu_result, query, sender_id, begin):

    # 开始帧
    seq = 1
    nlu_result_begin = copy.deepcopy(nlu_result)
    send_msg(nlu_result_begin, "CHAT", "", seq, time.time() - begin, status=0)

    # 中间帧
    full_answer = ""
    chat_handler = request_chat(query, sender_id)
    for value in process_chat(chat_handler, query, sender_id):
        nlu_result_chat = copy.deepcopy(nlu_result)
        send_msg(nlu_result_chat, "CHAT", value, seq, time.time() - begin, status=1)
        seq += 1
        full_answer += value
        logger.info(f"Chat Frame:{seq},content:{value}")

    # 结束帧
    if seq > 1:
        send_msg(nlu_result_begin, "CHAT", "", seq, time.time() - begin, status=2)
        logger.info(f"Chat cost time: {time.time() - begin}")
        return True, full_answer
    else:
        logger.info(f"Chat cost time: {time.time() - begin}")
        return False, full_answer



@socketio.on('request_nlu')
def inference(req):
    begin = time.time()
    json_info = json.loads(req)
    query = json_info.get("query")
    enable_dm = json_info.get("enable_dm")
    sender_id = json_info.get("sender_id", "test")
    trace_id = json_info.get("trace_id", "123")

    nlu_template = build_nlu_template(query, trace_id, begin)
    try:
        ori_query = (query or "").strip()
        logger.session.trace_id = trace_id
        logger.info("Request Params: {}".format(json_info))

        # 1) 拒识优先：先判非法，再做后续重模型调用。
        reject_result = request_reject(ori_query, trace_id)
        if not is_reject_passed(reject_result):
            send_msg(nlu_template, "REJECT", "", 1, time.time() - begin, status=-1)
            redis_client.set(REDIS_KEY.format(sender_id), f"REJECT#{ori_query}#0#", ex=TTL)
            logger.info(f"Query {ori_query} rejected by reject model.")
            return

        # 2) 改写：使用上一轮回复做指代消解。
        _, _, _, last_answer = parse_last_info(sender_id)
        query = request_rewrite(ori_query, last_answer, sender_id)

        # 3) 仲裁：按 task/faq/chat 三类分流。
        arbitration_result = request_arbitration(query, sender_id)

        logger.info(
            f"TraceID:{trace_id}, query:{query}, arbitration result: {arbitration_result}, cost time: {time.time() - begin}")

        # 4) 任务型对话链路
        if arbitration_result == "task":
            nlu_result = request_nlu(query, trace_id, enable_dm)
            if nlu_result.get("function", "") not in ["Unknown"]:
                # 如果有 nlg，就把它记入缓存，改写时能更好理解“它/这个”。
                answer_for_next_round = nlu_result.get("nlg", "")
                redis_client.set(REDIS_KEY.format(sender_id), f"SKILL#{query}#1#{answer_for_next_round}", ex=TTL)
                emit(
                    "request_nlu",
                    json.dumps(
                        nlu_result,
                        ensure_ascii=False
                    ),
                    broadcast=False
                )
            else:
                send_msg(nlu_result, "REJECT", prompts.DEFAULT_NLG, 1, time.time() - begin, status=-1)
                logger.info(f"Query {query} has been rejected.")

        # 5) 知识库问答链路
        elif arbitration_result == "faq":
            rag_result = request_rag(query, trace_id, sender_id)
            answer = rag_result.get("answer", "")
            if answer:
                nlu_faq = build_nlu_template(ori_query, trace_id, begin)
                send_faq(nlu_faq, answer, begin)
                redis_client.set(REDIS_KEY.format(sender_id), f"FAQ#{query}#1#{answer}", ex=TTL)
            else:
                # FAQ 为空则回退闲聊兜底，保证用户有回复。
                is_hit_chat, full_answer = handle_chat(nlu_template, query, sender_id, begin)
                if is_hit_chat:
                    redis_client.set(REDIS_KEY.format(sender_id), f"CHAT#{query}#{reject_result}#{full_answer}", ex=TTL)

        # 6) 闲聊兜底链路
        else:
            is_hit_chat, full_answer = handle_chat(nlu_template, query, sender_id, begin)
            if is_hit_chat:
                redis_client.set(REDIS_KEY.format(sender_id), f"CHAT#{query}#1#{full_answer}", ex=TTL)

    except Exception as e:
        logger.error(
            'TraceID:{}, Internal Server Error!'.format(trace_id))
        logger.error('{}'.format(e))
        traceback.print_exc()
        send_msg(nlu_template, "REJECT", "", 1, time.time() - begin, status=-1)

if __name__ == "__main__":
    socketio.run(
        app,
        allow_unsafe_werkzeug=True,
        host='0.0.0.0',
        port=os.getenv("FLASK_SERVER_PORT", 8080)
    )
