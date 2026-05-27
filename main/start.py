import json
import os
import time
import traceback
import copy
import base64
import warnings
from typing import Any, Dict
from pathlib import Path

from flask import Flask, Response, request, jsonify, make_response, stream_with_context, send_from_directory

# 抑制第三方库的过期警告（如 jieba 的 pkg_resources）
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

# 抑制第三方库的过期警告（如 jieba 的 pkg_resources）
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")

from main.client.arbitration import request_arbitration
from main.client.task import request_task
from main.client.rag import request_rag
from main.client.reject import is_reject_passed, request_reject
from main.client.rewrite import request_rewrite
from main.client.chat import request_chat, process_chat
from main.utils import logger
from main.utils.env_loader import load_project_env
from main.utils.session_memory import add_user_query, complete_answer, get_session_turns


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


load_project_env()
DEFAULT_NLG = os.getenv("DEFAULT_NLG", "抱歉，这个问题我还在学习中")
ENABLE_DEBUG_API = os.getenv("ENABLE_DEBUG_API", "false").strip().lower() in ("1", "true", "yes", "y")

# 图片静态目录
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGE_DIR = str(BASE_DIR / "kb" / "offline" / "data" / "processed" / "images")


# 图片静态路由
@app.route("/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)


INTENT_META = {
    "REJECT": ("拒识", "400"),
    "TASK": ("任务执行", "401"),
    "RAG": ("知识库问答", "402"),
    "CHAT": ("闲聊百科", "403"),
}


@app.route("/health", methods=["GET"])
def check():
    return make_response(jsonify(health="healthy"), 200)


@app.route("/debug/session/<sender_id>", methods=["GET"])
def debug_session(sender_id: str):
    if not ENABLE_DEBUG_API:
        return make_response(jsonify(error="debug api disabled"), 403)

    include_pending_raw = request.args.get("include_pending", "true")
    include_pending = str(include_pending_raw).strip().lower() in ("1", "true", "yes", "y")

    limit_raw = request.args.get("limit", "3")
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 3
    limit = max(1, min(limit, 20))

    turns = get_session_turns(
        sender_id=sender_id,
        limit=limit,
        include_pending=include_pending,
    )
    return make_response(jsonify({
        "sender_id": sender_id,
        "include_pending": include_pending,
        "limit": limit,
        "count": len(turns),
        "turns": turns,
    }), 200)


def _encode_frame(response_payload, route, frame, seq, cost, status) -> str:
    """把参数拼成一帧 JSON（替换原先 socketio 的 send_msg）。"""
    route = (route or "").upper()
    intent, intent_id = INTENT_META.get(route, INTENT_META["REJECT"])

    if route != "TASK" or not response_payload.get("intent"):
        response_payload["intent"] = intent
        response_payload["intent_id"] = intent_id
    elif not response_payload.get("intent_id"):
        response_payload["intent_id"] = intent_id
    response_payload["route"] = route.lower()
    response_payload["frame"] = frame
    response_payload["seq"] = seq
    response_payload["cost"] = cost
    response_payload["status"] = status
    return json.dumps(response_payload, ensure_ascii=False) + "\n"


def _build_template(query, trace_id, begin) -> Dict[str, Any]:
    return {
        "query": query,
        "trace_id": trace_id,
        "intent": "",
        "intent_id": "",
        "function": "",
        "slots": {},
        "route": "",
        "cost": time.time() - begin,
    }


@app.route("/agent", methods=["POST"])
def inference():
    begin = time.time()
    req_data = request.get_json(force=True)
    query = req_data.get("query", "").strip()
    enable_dm = req_data.get("enable_dm", True)
    sender_id = req_data.get("sender_id", "test")
    trace_id = req_data.get("trace_id", "123")

    def _stream():
        nonlocal query
        template = _build_template(query, trace_id, begin)

        try:
            ori_query = query
            logger.session.trace_id = trace_id
            logger.info("Request Params: {}".format(req_data))

            # 1) 拒识
            reject_result = request_reject(ori_query, trace_id)
            if not is_reject_passed(reject_result):
                yield _encode_frame(template, "REJECT", "", 1, time.time() - begin, status=-1)
                logger.info(f"Query {ori_query} rejected by reject model.")
                return

            # 2) 写入短期记忆
            add_user_query(sender_id, ori_query, trace_id)

            # 3) 改写
            query = request_rewrite(ori_query, sender_id, trace_id)

            # 4) 仲裁
            arbitration_result = request_arbitration(query, sender_id, trace_id)
            logger.info(f"TraceID:{trace_id}, query:{query}, arbitration result: {arbitration_result}")

            # 5) 任务链路
            if arbitration_result == "task":
                response_payload = request_task(query, trace_id, enable_dm)
                nlg_content = response_payload.get("nlg", "")
                has_function = response_payload.get("function", "Unknown") not in ["Unknown", ""]
                if nlg_content:
                    # NLG 有输出时直接使用，不依赖 function 字段
                    answer = nlg_content
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="task",
                                    answer=answer, query_fallback=ori_query)
                    yield _encode_frame(response_payload, "TASK", answer, 1, time.time() - begin, status=2)
                elif has_function:
                    # 有 function 但无 NLG，回退到默认回答
                    answer = DEFAULT_NLG
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="task",
                                    answer=answer, query_fallback=ori_query)
                    yield _encode_frame(response_payload, "TASK", answer, 1, time.time() - begin, status=2)
                else:
                    yield _encode_frame(response_payload, "REJECT", DEFAULT_NLG, 1, time.time() - begin, status=-1)
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="task",
                                    answer=DEFAULT_NLG, query_fallback=ori_query)

            # 6) RAG 链路
            elif arbitration_result == "rag":
                rag_result = request_rag(query, trace_id, sender_id)
                answer = rag_result.get("answer", "")
                if answer:
                    rag_payload = _build_template(ori_query, trace_id, begin)
                    # 图片转 base64 内联到 JSON
                    related_images = rag_result.get("related_images", [])
                    for img in related_images:
                        img_path = img.get("image_path", "")
                        if img_path and os.path.exists(img_path):
                            with open(img_path, "rb") as f:
                                img_data = f.read()
                            ext = os.path.splitext(img_path)[1].lstrip(".") or "png"
                            b64 = base64.b64encode(img_data).decode()
                            img["url"] = f"data:image/{ext};base64,{b64}"
                    rag_payload["related_images"] = related_images
                    rag_payload["cite_pages"] = rag_result.get("cite_pages", [])
                    rag_payload["citations"] = rag_result.get("citations", [])
                    yield _encode_frame(rag_payload, "RAG", answer, 1, time.time() - begin, status=2)
                    complete_answer(sender_id=sender_id, trace_id=trace_id, route="rag",
                                    answer=answer, query_fallback=ori_query)
                else:
                    # RAG 无答案 → 闲聊兜底
                    yield from _chat_stream(template, query, sender_id, trace_id, begin, ori_query)

            # 7) 闲聊链路
            else:
                yield from _chat_stream(template, query, sender_id, trace_id, begin, ori_query)

        except Exception as e:
            logger.error(f'TraceID:{trace_id}, Internal Server Error!')
            logger.error(f'{e}')
            traceback.print_exc()
            yield _encode_frame(template, "REJECT", "", 1, time.time() - begin, status=-1)

    return Response(stream_with_context(_stream()), mimetype="text/plain")


def _chat_stream(template, query, sender_id, trace_id, begin, ori_query):
    """闲聊链路流式生成器，逐帧 yield。"""
    seq = 1
    payload_begin = copy.deepcopy(template)
    yield _encode_frame(payload_begin, "CHAT", "", seq, time.time() - begin, status=0)

    full_answer = ""
    chat_handler = request_chat(query, sender_id, trace_id)
    is_hit = False
    for value in process_chat(chat_handler, query, sender_id):
        payload = copy.deepcopy(template)
        yield _encode_frame(payload, "CHAT", value, seq, time.time() - begin, status=1)
        seq += 1
        full_answer += value
        is_hit = True

    if is_hit:
        yield _encode_frame(payload_begin, "CHAT", "", seq, time.time() - begin, status=2)
        complete_answer(sender_id=sender_id, trace_id=trace_id, route="chat",
                        answer=full_answer, query_fallback=ori_query)
        logger.info(f"Chat cost time: {time.time() - begin}")


if __name__ == "__main__":
    app.run(
        host='0.0.0.0',
        debug=True,
        port=os.getenv("FLASK_SERVER_PORT", 8080),
        threaded=True,
    )