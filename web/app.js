"use strict";

/*
 * 前端与后端通过 HTTP Streaming 通信：
 * - POST /agent 发送请求，后端用 newline-delimited JSON 流式返回帧
 * - 每行一个 JSON 对象，由 handleAgentFrame 逐帧处理
 */

const STORAGE_KEYS = {};

const dom = {
  connectionStatus: document.querySelector("#connectionStatus"),
  reconnectButton: document.querySelector("#reconnectButton"),
  messageList: document.querySelector("#messageList"),
  chatForm: document.querySelector("#chatForm"),
  queryInput: document.querySelector("#queryInput"),
  voiceButton: document.querySelector("#voiceButton"),
  voiceStatus: document.querySelector("#voiceStatus"),
  sendButton: document.querySelector("#sendButton"),
  cancelButton: document.querySelector("#cancelButton"),
  clearButton: document.querySelector("#clearButton"),
};

let activeAssistantMessageId = "";
let currentTraceId = "";
let waitingForReply = false;
let messageSeed = 0;
let speechRecognition = null;
let isListening = false;
let speechBaseText = "";
let speechSupported = false;
const messageStore = new Map();
const THINKING_TEXT = "正在思考";
const PAGE_OPEN_TS = Date.now();
const SESSION_SENDER_ID = `web-${PAGE_OPEN_TS}`;
const SpeechRecognitionConstructor =
  globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition || null;

function createDefaultSenderId() {
  return SESSION_SENDER_ID;
}

function createTraceId() {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function setConnectionStatus(status, text) {
  dom.connectionStatus.textContent = text;
  dom.connectionStatus.className = `status-pill is-${status}`;
}

function bindEvents() {
  dom.chatForm.addEventListener("submit", (event) => {
    event.preventDefault();
    sendQuery();
  });

  dom.queryInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendQuery();
    }
  });

  dom.queryInput.addEventListener("input", () => {
    autoResizeTextarea();
  });

  dom.voiceButton.addEventListener("click", () => {
    toggleVoiceInput();
  });

  dom.reconnectButton.addEventListener("click", () => {
    checkConnection();
  });

  dom.cancelButton.addEventListener("click", () => {
    cancelQuery();
  });

  dom.clearButton.addEventListener("click", () => {
    clearMessages();
  });
}

async function checkConnection() {
  setConnectionStatus("connecting", "检测中");
  try {
    const res = await fetch("/health");
    if (res.ok) {
      setConnectionStatus("online", "已连接");
    } else {
      setConnectionStatus("offline", "异常");
    }
  } catch {
    setConnectionStatus("offline", "不可达");
  }
}

async function sendQuery() {
  const query = dom.queryInput.value.trim();

  if (!query || waitingForReply) {
    return;
  }

  if (isListening && speechRecognition) {
    speechRecognition.stop();
  }

  appendMessage("user", query);
  activeAssistantMessageId = appendMessage("assistant", THINKING_TEXT, { loading: true });
  waitingForReply = true;
  setComposerBusy(true);

  dom.queryInput.value = "";
  autoResizeTextarea();

  const traceId = createTraceId();
  currentTraceId = traceId;
  dom.cancelButton.style.display = "";

  const payload = {
    query,
    sender_id: createDefaultSenderId(),
    trace_id: traceId,
    enable_dm: true,
  };

  try {
    const response = await fetch("/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        // 流异常结束：没有收到结束/错误帧，释放 composer 避免 UI 卡死
        if (waitingForReply) {
          finishAssistantMessage("连接异常中断，请重新发送。", { isError: true });
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          handleAgentFrame(JSON.parse(trimmed));
        } catch (parseError) {
          console.warn("帧解析失败:", parseError, trimmed);
        }
      }
    }
  } catch (error) {
    finishAssistantMessage("发送失败，请稍后再试。", { isError: true });
    appendSystemMessage(error.message);
  }
}

async function cancelQuery() {
  if (!currentTraceId) return;
  try {
    await fetch(`/cancel/${currentTraceId}`, { method: "POST" });
  } catch { /* 忽略网络错误 */ }
  finishAssistantMessage("已中断", { isError: true });
}

function handleAgentFrame(payload) {
  const frame = payload;

  if (!activeAssistantMessageId) {
    activeAssistantMessageId = appendMessage("assistant", "", { loading: true });
    waitingForReply = true;
  }

  const status = Number(frame.status);
  const hasStatus = Number.isFinite(status);

  if (!hasStatus) {
    const text = frame.frame || frame.nlg || summarizeTaskFrame(frame);
    updateMessage(activeAssistantMessageId, text, { replace: true, loading: false });
    addFrameMeta(activeAssistantMessageId, frame);
    releaseComposer();
    return;
  }

  if (status === 0) {
    // 开始帧：更新 loading 状态
    updateMessage(activeAssistantMessageId, "", { replace: false, loading: true });
  } else if (status === 1) {
    // 中间帧：追加内容或替换 loading
    const text = frame.frame || "";
    updateStreamingMessage(activeAssistantMessageId, text, false);
  } else if (status === 2) {
    // 结束帧
    const text = frame.frame || "";
    updateMessage(activeAssistantMessageId, text, { replace: false, loading: false });
    // 渲染关联图片
    if (frame.related_images && frame.related_images.length) {
      renderImages(activeAssistantMessageId, frame.related_images, frame.cite_pages);
    }
    addFrameMeta(activeAssistantMessageId, frame);
    releaseComposer();
  } else if (status === 3) {
    // 心跳帧：后端仍在处理中，保持 loading 状态，避免浏览器/代理超时断开
    const record = messageStore.get(activeAssistantMessageId);
    if (record) {
      record.bubble.classList.add("is-loading");
    }
  } else if (status === -1) {
    // 错误/拒识
    const text = frame.frame || "";
    finishAssistantMessage(text, { isError: true });
  }
}

function summarizeTaskFrame(frame) {
  const intent = frame.intent || "";
  const route = frame.route || "";
  const func = frame.function || "";
  const parts = [route, intent, func].filter(Boolean);
  return parts.length ? `[${parts.join("/")}]` : "";
}

function renderImages(messageId, images, citePages) {
  const record = messageStore.get(messageId);
  if (!record) return;

  // 移除旧的图片容器
  const oldContainer = record.bubble.querySelector(".image-gallery");
  oldContainer?.remove();

  const container = document.createElement("div");
  container.className = "image-gallery";

  const header = document.createElement("div");
  header.className = "image-gallery-header";
  const pageHint = citePages?.length ? `（第 ${citePages.join("、")} 页）` : "";
  header.textContent = `相关图片${pageHint}`;
  container.append(header);

  const grid = document.createElement("div");
  grid.className = "image-gallery-grid";

  for (const img of images) {
    const figure = document.createElement("figure");
    figure.className = "image-item";

    const imgEl = document.createElement("img");
    imgEl.src = img.url || img.image_path;
    imgEl.alt = img.title || "";
    imgEl.loading = "lazy";
    imgEl.addEventListener("click", () => window.open(img.url, "_blank"));

    const figcaption = document.createElement("figcaption");
    figcaption.textContent = img.title || "";

    figure.append(imgEl, figcaption);
    grid.append(figure);
  }

  container.append(grid);
  record.bubble.append(container);
  scrollToBottom();
}

function releaseComposer() {
  activeAssistantMessageId = "";
  currentTraceId = "";
  waitingForReply = false;
  dom.cancelButton.style.display = "none";
  setComposerBusy(false);
}

function setComposerBusy(isBusy) {
  dom.sendButton.disabled = isBusy;
  dom.queryInput.disabled = isBusy;
  dom.voiceButton.disabled = isBusy || !speechSupported;
}

function clearMessages() {
  dom.messageList.innerHTML = "";
  messageStore.clear();
  activeAssistantMessageId = "";
  waitingForReply = false;
  setComposerBusy(false);
  appendMessage("assistant", "您好，我是Model 3智能助手，有什么可以帮您？");
}

function autoResizeTextarea() {
  dom.queryInput.style.height = "auto";
  dom.queryInput.style.height = `${Math.min(dom.queryInput.scrollHeight, 140)}px`;
}

function scrollToBottom() {
  dom.messageList.scrollTop = dom.messageList.scrollHeight;
}

function updateStreamingMessage(id, text, keepLoading) {
  const record = messageStore.get(id);
  const shouldReplace = !record || record.text === THINKING_TEXT;

  updateMessage(id, text, {
    append: !shouldReplace,
    replace: shouldReplace,
    loading: keepLoading,
  });
}

function addFrameMeta(id, frame) {
  const record = messageStore.get(id);
  if (!record) return;

  const oldMeta = record.bubble.querySelector(".meta-row");
  const oldDebug = record.bubble.querySelector(".debug-block");
  oldMeta?.remove();
  oldDebug?.remove();

  const metaItems = [
    frame.route ? `路由：${frame.route}` : "",
    frame.intent ? `意图：${frame.intent}` : "",
    frame.function ? `功能：${frame.function}` : "",
    Number.isFinite(Number(frame.cost)) ? `耗时：${Number(frame.cost).toFixed(2)}s` : "",
  ].filter(Boolean);

  if (metaItems.length) {
    const metaRow = document.createElement("div");
    metaRow.className = "meta-row";
    metaItems.forEach((item) => {
      const chip = document.createElement("span");
      chip.className = "meta-chip";
      chip.textContent = item;
      metaRow.append(chip);
    });
    record.bubble.append(metaRow);
  }

  const debug = document.createElement("details");
  debug.className = "debug-block";

  const summary = document.createElement("summary");
  summary.textContent = "查看原始返回";

  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(frame, null, 2);

  debug.append(summary, pre);
  record.bubble.append(debug);
  scrollToBottom();
}

function finishAssistantMessage(text, options = {}) {
  updateMessage(activeAssistantMessageId, text, {
    replace: true,
    loading: false,
  });

  if (options.isError) {
    const record = messageStore.get(activeAssistantMessageId);
    record?.bubble.classList.add("is-error");
  }

  releaseComposer();
}

function appendSystemMessage(text) {
  appendMessage("system", text);
}

function appendMessage(role, text, options = {}) {
  const id = `msg-${++messageSeed}`;
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.id = id;

  const labelMap = { user: "你", assistant: "助手", system: "系统" };
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = labelMap[role] || role;
  article.append(label);

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (options.loading) bubble.classList.add("is-loading");
  bubble.textContent = text;
  article.append(bubble);

  dom.messageList.append(article);
  messageStore.set(id, { element: article, bubble, text: text });

  scrollToBottom();
  return id;
}

function updateMessage(id, text, options = {}) {
  const record = messageStore.get(id);
  if (!record) return;

  const newText = options.append ? record.text + text : options.replace ? text : text || record.text;
  record.text = newText;
  record.bubble.textContent = newText;

  record.bubble.classList.toggle("is-loading", !!options.loading);

  scrollToBottom();
}

function parseFrame(payload) {
  if (typeof payload === "string") {
    try {
      return JSON.parse(payload);
    } catch {
      return { frame: payload };
    }
  }
  return payload;
}

function initSpeechRecognition() {
  speechSupported = Boolean(SpeechRecognitionConstructor) && window.isSecureContext;

  if (!speechSupported) {
    dom.voiceButton.disabled = true;
    dom.voiceButton.title = window.isSecureContext
      ? "当前浏览器不支持语音识别"
      : "语音输入需要 HTTPS 或本地安全环境";
    setVoiceStatus("");
    return;
  }

  speechRecognition = new SpeechRecognitionConstructor();
  speechRecognition.lang = "zh-CN";
  speechRecognition.continuous = false;
  speechRecognition.interimResults = true;
  speechRecognition.maxAlternatives = 1;

  speechRecognition.addEventListener("start", () => {
    isListening = true;
    setVoiceButtonState(true);
    setVoiceStatus("正在听，请说话。");
  });

  speechRecognition.addEventListener("result", (event) => {
    const transcript = collectSpeechTranscript(event.results);
    dom.queryInput.value = [speechBaseText, transcript].filter(Boolean).join(" ");
    autoResizeTextarea();
  });

  speechRecognition.addEventListener("end", () => {
    isListening = false;
    setVoiceButtonState(false);
    setVoiceStatus(dom.queryInput.value.trim() ? "已填入输入框，可以发送。" : "");
    dom.queryInput.focus();
  });

  speechRecognition.addEventListener("error", (event) => {
    isListening = false;
    setVoiceButtonState(false);
    setVoiceStatus(getSpeechErrorText(event.error));
  });

  setVoiceButtonState(false);
}

function toggleVoiceInput() {
  if (!speechSupported || !speechRecognition || waitingForReply) return;

  if (isListening) {
    speechRecognition.stop();
    return;
  }

  try {
    speechBaseText = dom.queryInput.value.trim();
    speechRecognition.start();
  } catch {
    setVoiceStatus("语音识别暂时无法启动，请稍后再试。");
  }
}

function collectSpeechTranscript(results) {
  let transcript = "";
  for (let index = 0; index < results.length; index += 1) {
    if (results[index][0]?.transcript) {
      transcript += results[index][0].transcript;
    }
  }
  return transcript.trim();
}

function getSpeechErrorText(errorCode) {
  const errorMap = {
    "audio-capture": "没有找到麦克风，请检查设备。",
    "not-allowed": "浏览器没有麦克风权限，请允许后再试。",
    "no-speech": "没有听到声音，请再试一次。",
    network: "语音识别服务暂时不可用。",
    aborted: "",
  };
  return errorMap[errorCode] || "语音识别失败，请再试一次。";
}

function setVoiceButtonState(listening) {
  dom.voiceButton.classList.toggle("is-listening", listening);
  dom.voiceButton.setAttribute("aria-label", listening ? "停止语音输入" : "开始语音输入");
  dom.voiceButton.title = listening ? "停止语音输入" : "语音输入";
}

function setVoiceStatus(text) {
  dom.voiceStatus.textContent = text;
}

// 初始化
bindEvents();
initSpeechRecognition();
clearMessages();
setConnectionStatus("online", "就绪");
