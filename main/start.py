import json
import os
import time
import traceback
from typing import Any, Dict

from flask import Flask, jsonify, make_response, request
from flask_socketio import SocketIO, emit

from main.client.arbitration import request_arbitration
from main.client.task import request_task
from main.client.rag import request_rag
from main.client.reject import is_reject_passed, request_reject
from main.client.rewrite import request_rewrite
from main.client.chat import handle_chat_stream
from main.utils import logger
from main.utils.env_loader import load_project_env
from main.utils.session_memory import add_user_query, complete_answer, get_session_turns


socketio = SocketIO(cors_allowed_origins='*', async_mode='threading')
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
socketio.init_app(app)


load_project_env()
DEFAULT_NLG = os.getenv("DEFAULT_NLG", "抱歉，这个问题我还在学习中")
ENABLE_DEBUG_API = os.getenv("ENABLE_DEBUG_API", "false").strip().lower() in ("1", "true", "yes", "y")


INTENT_META = {
    "REJECT": ("拒识", "400"),
    "TASK": ("任务执行", "401"),
    "FAQ": ("知识库问答", "402"),
    "CHAT": ("闲聊百科", "403"),
}


@app.route("/health", methods=["GET"])
def check():
    response = make_response(
        jsonify(health="healthy"),
        200,
        {'content-type': 'application/json'}
    )
    return response


@app.route("/debug/session/<sender_id>", methods=["GET"])
def debug_session(sender_id: str):
    """
    只读调试接口：查看某个 sender_id 的短期记忆内容。
    默认关闭，需在 .env 里设置 ENABLE_DEBUG_API=true 才能访问。
    """
    if not ENABLE_DEBUG_API:
        return make_response(
            jsonify(error="debug api disabled"),
            403,
            {'content-type': 'application/json'}
        )

    include_pending_raw = request.args.get("include_pending", "true")
    include_pending = str(include_pending_raw).strip().lower() in ("1", "true", "yes", "y")

    limit_raw = request.args.get("limit", "3")
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 3
    # 避免一次性拉太多，调试接口最多返回 20 条。
    limit = max(1, min(limit, 20))

    turns = get_session_turns(
        sender_id=sender_id,
        limit=limit,
        include_pending=include_pending,
    )
    response = {
        "sender_id": sender_id,
        "include_pending": include_pending,
        "limit": limit,
        "count": len(turns),
        "turns": turns,
    }
    return make_response(
        jsonify(response),
        200,
        {'content-type': 'application/json'}
    )


@socketio.on('connect')
def connected_msg():
    manager = socketio.server.manager
    connections_count = len(manager.rooms['/']) - 1
    logger.info(f'当前连接数: {connections_count}')
    logger.info('client connected.')


@socketio.on('disconnect')
def disconnect_msg():
    logger.info('client disconnected.')


def build_response_template(query: str, trace_id: str, begin_ts: float) -> Dict[str, Any]:
    """
    统一返回模板，避免每条分支自己拼导致字段不一致。
    """
    return {
        "query": query,
        "trace_id": trace_id,
        "intent": "",
        "intent_id": "",
        "function": "",
        "slots": {},
        "route": "",
        "cost": time.time() - begin_ts
    }


# frame:这一帧的文本内容  seq：帧序号,方便前端按顺序拼接。
def send_msg(response_payload, route, frame, seq, cost, status):
    route = (route or "").upper()
    intent, intent_id = INTENT_META.get(route, INTENT_META["REJECT"])

    # 如果不是 TASK，直接覆盖 intent/intent_id
    if route != "TASK" or not response_payload.get("intent"):
        response_payload["intent"] = intent
        response_payload["intent_id"] = intent_id
    # 如果是 TASK，优先保留 task pipeline 给出的细粒度 intent，只在缺失时补 intent_id
    elif not response_payload.get("intent_id"):
        response_payload["intent_id"] = intent_id
    response_payload["route"] = route.lower()
    response_payload["frame"] = frame
    response_payload["seq"] = seq
    response_payload["cost"] = cost
    response_payload["status"] = status
    emit(
        "request_agent",
        json.dumps(response_payload, ensure_ascii=False),
        broadcast=False
    )


def send_faq(response_payload: Dict[str, Any], answer: str, begin: float) -> None:
    # FAQ 非流式场景：走单帧输出，客户端处理更简单。
    send_msg(response_payload, "FAQ", answer, 1, time.time() - begin, status=2)


@socketio.on('request_agent')
def inference(req):
    begin = time.time()
    json_info = json.loads(req)
    query = json_info.get("query")
    enable_dm = json_info.get("enable_dm")
    sender_id = json_info.get("sender_id", "test")
    trace_id = json_info.get("trace_id", "123")

    response_template = build_response_template(query, trace_id, begin)
    try:
        ori_query = (query or "").strip()
        logger.session.trace_id = trace_id
        logger.info("Request Params: {}".format(json_info))

        # 1) 拒识优先：先判非法，再做后续重模型调用。
        reject_result = request_reject(ori_query, trace_id)
        if not is_reject_passed(reject_result):
            send_msg(response_template, "REJECT", "", 1, time.time() - begin, status=-1)
            logger.info(f"Query {ori_query} rejected by reject model.")
            return

        # 2) 拒识通过后先把本轮 query 写入短期记忆，answer 稍后回填。
        add_user_query(sender_id, ori_query, trace_id)

        # 3) 改写：只结合 Redis 中还没过期的历史轮次做指代消解。
        query = request_rewrite(ori_query, sender_id, trace_id)

        # 4) 仲裁：按 task/faq/chat 三类分流。
        arbitration_result = request_arbitration(query, sender_id, trace_id)

        logger.info(
            f"TraceID:{trace_id}, query:{query}, arbitration result: {arbitration_result}, cost time: {time.time() - begin}")

        # 5) 任务型对话链路
        if arbitration_result == "task":
            response_payload = request_task(query, trace_id, enable_dm)
            if response_payload.get("function", "Unknown") not in ["Unknown", ""]:
                answer_for_next_round = response_payload.get("nlg", "") or DEFAULT_NLG
                complete_answer(
                    sender_id=sender_id,
                    trace_id=trace_id,
                    route="task",
                    answer=answer_for_next_round,
                    query_fallback=ori_query,
                ) 
                send_msg(
                    response_payload,
                    "TASK",
                    answer_for_next_round,
                    1,
                    time.time() - begin,
                    status=2,
                )
            else:
                send_msg(response_payload, "REJECT", DEFAULT_NLG, 1, time.time() - begin, status=-1)
                logger.info(f"Query {query} has been rejected.")
                complete_answer(
                    sender_id=sender_id,
                    trace_id=trace_id,
                    route="task",
                    answer=DEFAULT_NLG,
                    query_fallback=ori_query,
                )

        # 6) 知识库问答链路
        elif arbitration_result == "faq":
            rag_result = request_rag(query, trace_id, sender_id)
            answer = rag_result.get("answer", "")
            if answer:
                faq_payload = build_response_template(ori_query, trace_id, begin)
                send_faq(faq_payload, answer, begin)
                complete_answer(
                    sender_id=sender_id,
                    trace_id=trace_id,
                    route="faq",
                    answer=answer,
                    query_fallback=ori_query,
                )
            else:
                # FAQ 为空则回退闲聊兜底，保证用户有回复。
                is_hit_chat, full_answer = handle_chat_stream(
                    response_template,
                    query,
                    sender_id,
                    trace_id,
                    begin,
                    send_msg,
                )
                if is_hit_chat:
                    complete_answer(
                        sender_id=sender_id,
                        trace_id=trace_id,
                        route="chat",
                        answer=full_answer,
                        query_fallback=ori_query,
                    )

        # 7) 闲聊兜底链路
        else:
            is_hit_chat, full_answer = handle_chat_stream(
                response_template,
                query,
                sender_id,
                trace_id,
                begin,
                send_msg,
            )
            if is_hit_chat:
                complete_answer(
                    sender_id=sender_id,
                    trace_id=trace_id,
                    route="chat",
                    answer=full_answer,
                    query_fallback=ori_query,
                )

    except Exception as e:
        logger.error(
            'TraceID:{}, Internal Server Error!'.format(trace_id))
        logger.error('{}'.format(e))
        traceback.print_exc()
        send_msg(response_template, "REJECT", "", 1, time.time() - begin, status=-1)

if __name__ == "__main__":
    socketio.run(
        app,
        allow_unsafe_werkzeug=True,
        host='0.0.0.0',
        port=os.getenv("FLASK_SERVER_PORT", 8080)
    )
