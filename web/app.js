"use strict";

/*
 * 这里没有使用官方 socket.io-client 包，是为了保持前端零构建、零外部依赖。
 * 后端是 Flask-SocketIO，本文件实现了够当前项目使用的 Socket.IO polling 协议：
 * - 先用 Engine.IO 建立 polling 连接
 * - 再发送 Socket.IO 的默认命名空间连接包
 * - 发 request_nlu 事件，并监听同名事件返回
 */

const STORAGE_KEYS = {
  serverUrl: "agent_web_server_url",
  senderId: "agent_web_sender_id",
  enableDm: "agent_web_enable_dm",
};

const dom = {
  connectionStatus: document.querySelector("#connectionStatus"),
  serverUrl: document.querySelector("#serverUrl"),
  senderId: document.querySelector("#senderId"),
  enableDm: document.querySelector("#enableDm"),
  reconnectButton: document.querySelector("#reconnectButton"),
  messageList: document.querySelector("#messageList"),
  chatForm: document.querySelector("#chatForm"),
  queryInput: document.querySelector("#queryInput"),
  voiceButton: document.querySelector("#voiceButton"),
  voiceStatus: document.querySelector("#voiceStatus"),
  sendButton: document.querySelector("#sendButton"),
  clearButton: document.querySelector("#clearButton"),
};

let socketClient = null;
let activeAssistantMessageId = "";
let waitingForReply = false;
let messageSeed = 0;
let speechRecognition = null;
let isListening = false;
let speechBaseText = "";
let speechSupported = false;
const messageStore = new Map();
const THINKING_TEXT = "正在思考";
const SpeechRecognitionConstructor =
  globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition || null;

class SocketIoPollingClient {
  constructor(baseUrl) {
    this.baseUrl = normalizeBaseUrl(baseUrl);
    this.sid = "";
    this.closed = true;
    this.connected = false;
    this.handlers = new Map();
    this.postQueue = Promise.resolve();
    this.pollAbortController = null;
  }

  on(eventName, handler) {
    const handlers = this.handlers.get(eventName) || [];
    handlers.push(handler);
    this.handlers.set(eventName, handlers);
  }

  isConnected() {
    return this.connected && !this.closed;
  }

  async connect() {
    this.closed = false;

    try {
      const response = await fetch(this.buildUrl(), {
        method: "GET",
        cache: "no-store",
      });
      const payload = await readSocketResponse(response);
      this.processPayload(payload);

      // Engine.IO 握手成功后，发送 Socket.IO 默认命名空间连接包。
      await this.sendPacket("40");
      this.pollLoop();
    } catch (error) {
      this.fail(error);
    }
  }

  disconnect() {
    this.closed = true;

    if (this.pollAbortController) {
      this.pollAbortController.abort();
      this.pollAbortController = null;
    }

    if (this.sid) {
      this.sendPacket("41").catch(() => {});
    }

    this.connected = false;
    this.emitLocal("disconnect");
  }

  async emit(eventName, payload) {
    if (!this.isConnected()) {
      throw new Error("Socket.IO 连接还没有建立");
    }

    // 后端 request_nlu(req) 里会 json.loads(req)，所以这里传字符串。
    const socketPacket = `42${JSON.stringify([eventName, payload])}`;
    await this.sendPacket(socketPacket);
  }

  async pollLoop() {
    while (!this.closed) {
      try {
        this.pollAbortController = new AbortController();
        const response = await fetch(this.buildUrl(), {
          method: "GET",
          cache: "no-store",
          signal: this.pollAbortController.signal,
        });
        const payload = await readSocketResponse(response);
        this.processPayload(payload);
      } catch (error) {
        if (!this.closed) {
          this.fail(error);
        }
      }
    }
  }

  async sendPacket(packet) {
    // Engine.IO 要求同一个连接上不要并发 POST，这里用队列串起来。
    this.postQueue = this.postQueue.then(async () => {
      if (this.closed && packet !== "41") {
        return;
      }

      const response = await fetch(this.buildUrl(), {
        method: "POST",
        headers: {
          "Content-Type": "text/plain;charset=UTF-8",
        },
        body: packet,
      });
      const payload = await readSocketResponse(response);
      this.processPayload(payload);
    });

    return this.postQueue;
  }

  buildUrl() {
    const base = new URL(this.baseUrl);
    const socketPath = normalizeSocketPath(base.pathname);
    const url = new URL(`${socketPath}/socket.io/`, `${base.protocol}//${base.host}`);

    url.searchParams.set("EIO", "4");
    url.searchParams.set("transport", "polling");
    url.searchParams.set("t", `${Date.now()}${Math.random().toString(16).slice(2)}`);

    if (this.sid) {
      url.searchParams.set("sid", this.sid);
    }

    return url.toString();
  }

  processPayload(payload) {
    if (!payload || payload === "ok") {
      return;
    }

    // Engine.IO v4 的 polling 响应里，多个包会用 ASCII 记录分隔符隔开。
    const packets = payload.split("\x1e").filter(Boolean);
    packets.forEach((packet) => this.processEnginePacket(packet));
  }

  processEnginePacket(packet) {
    const engineType = packet.charAt(0);
    const body = packet.slice(1);

    if (engineType === "0") {
      const handshake = JSON.parse(body);
      this.sid = handshake.sid;
      return;
    }

    if (engineType === "1") {
      this.connected = false;
      this.emitLocal("disconnect");
      return;
    }

    if (engineType === "2") {
      // 服务端 ping，客户端必须 pong，否则后端会认为前端掉线。
      this.sendPacket("3").catch((error) => this.emitLocal("error", error));
      return;
    }

    if (engineType === "3" || engineType === "6") {
      return;
    }

    if (engineType === "4") {
      this.processSocketPacket(body);
    }
  }

  processSocketPacket(packet) {
    const socketType = packet.charAt(0);
    const body = packet.slice(1);

    if (socketType === "0") {
      this.connected = true;
      this.emitLocal("connect");
      return;
    }

    if (socketType === "1") {
      this.connected = false;
      this.emitLocal("disconnect");
      return;
    }

    if (socketType === "2") {
      const jsonStart = body.indexOf("[");
      if (jsonStart === -1) {
        return;
      }

      const args = JSON.parse(body.slice(jsonStart));
      const [eventName, ...eventArgs] = args;
      this.emitLocal(eventName, ...eventArgs);
      return;
    }

    if (socketType === "4") {
      this.emitLocal("error", new Error(body || "Socket.IO 返回错误"));
    }
  }

  emitLocal(eventName, ...args) {
    const handlers = this.handlers.get(eventName) || [];
    handlers.forEach((handler) => handler(...args));
  }

  fail(error) {
    this.closed = true;
    this.connected = false;

    if (this.pollAbortController) {
      this.pollAbortController.abort();
      this.pollAbortController = null;
    }

    this.emitLocal("error", error);
    this.emitLocal("disconnect");
  }
}

function normalizeSocketPath(pathname) {
  const path = pathname.replace(/\/+$/, "");
  return path === "/" ? "" : path;
}

function normalizeBaseUrl(value) {
  return value.trim().replace(/\/+$/, "");
}

async function readSocketResponse(response) {
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return response.text();
}

function getAutoServerUrl() {
  // 同域部署时最省心：页面在哪个域名打开，就连哪个域名的后端。
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "";
}

function getActiveServerUrl() {
  const configuredUrl = normalizeBaseUrl(dom.serverUrl.value);
  return configuredUrl || getAutoServerUrl();
}

function createDefaultSenderId() {
  const randomId = globalThis.crypto?.randomUUID?.() || Date.now().toString(36);
  return `web-${randomId}`;
}

function createTraceId() {
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function initSettings() {
  dom.serverUrl.value = localStorage.getItem(STORAGE_KEYS.serverUrl) || "";

  const storedSenderId = localStorage.getItem(STORAGE_KEYS.senderId);
  const senderId = storedSenderId || createDefaultSenderId();
  localStorage.setItem(STORAGE_KEYS.senderId, senderId);
  dom.senderId.value = senderId;

  const storedEnableDm = localStorage.getItem(STORAGE_KEYS.enableDm);
  dom.enableDm.checked = storedEnableDm === null ? true : storedEnableDm === "true";
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

  dom.serverUrl.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEYS.serverUrl, normalizeBaseUrl(dom.serverUrl.value));
    connectToBackend();
  });

  dom.senderId.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEYS.senderId, dom.senderId.value.trim() || createDefaultSenderId());
    dom.senderId.value = localStorage.getItem(STORAGE_KEYS.senderId);
  });

  dom.enableDm.addEventListener("change", () => {
    localStorage.setItem(STORAGE_KEYS.enableDm, String(dom.enableDm.checked));
  });

  dom.reconnectButton.addEventListener("click", () => {
    connectToBackend();
  });

  dom.clearButton.addEventListener("click", () => {
    clearMessages();
  });
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

    // 语音识别会不断刷新中间结果，这里用“开始录音前的文本 + 当前识别文本”覆盖输入框。
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
  if (!speechSupported || !speechRecognition || waitingForReply) {
    return;
  }

  if (isListening) {
    speechRecognition.stop();
    return;
  }

  try {
    speechBaseText = dom.queryInput.value.trim();
    speechRecognition.start();
  } catch (error) {
    // start() 在浏览器认为识别器已启动时会抛异常，给用户一个能看懂的提示。
    setVoiceStatus("语音识别暂时无法启动，请稍后再试。");
  }
}

function collectSpeechTranscript(results) {
  let transcript = "";

  // SpeechRecognitionResultList 在少数浏览器里不是标准数组，所以用下标遍历更稳。
  for (let index = 0; index < results.length; index += 1) {
    const result = results[index];

    if (result[0]?.transcript) {
      transcript += result[0].transcript;
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

function connectToBackend() {
  const serverUrl = getActiveServerUrl();

  if (socketClient) {
    socketClient.disconnect();
    socketClient = null;
  }

  if (!serverUrl) {
    setConnectionStatus("offline", "未配置");
    appendSystemMessage("当前页面不是通过域名打开的，请填写后端地址后再重连。");
    return;
  }

  setConnectionStatus("connecting", "连接中");
  socketClient = new SocketIoPollingClient(serverUrl);

  socketClient.on("connect", () => {
    setConnectionStatus("online", "已连接");
  });

  socketClient.on("disconnect", () => {
    setConnectionStatus("offline", "已断开");
  });

  socketClient.on("error", (error) => {
    setConnectionStatus("offline", "连接失败");
    appendSystemMessage(`连接后端失败：${error.message}`);
  });

  socketClient.on("request_nlu", (payload) => {
    handleNluFrame(payload);
  });

  socketClient.connect();
}

function setConnectionStatus(status, text) {
  dom.connectionStatus.textContent = text;
  dom.connectionStatus.className = `status-pill is-${status}`;
}

async function sendQuery() {
  const query = dom.queryInput.value.trim();

  if (!query || waitingForReply) {
    return;
  }

  if (isListening && speechRecognition) {
    speechRecognition.stop();
  }

  if (!socketClient || !socketClient.isConnected()) {
    appendSystemMessage("后端还没有连上，请检查地址后点重连。");
    connectToBackend();
    return;
  }

  appendMessage("user", query);
  activeAssistantMessageId = appendMessage("assistant", THINKING_TEXT, { loading: true });
  waitingForReply = true;
  setComposerBusy(true);

  dom.queryInput.value = "";
  autoResizeTextarea();

  const payload = {
    query,
    sender_id: dom.senderId.value.trim() || createDefaultSenderId(),
    trace_id: createTraceId(),
    enable_dm: dom.enableDm.checked,
  };

  try {
    await socketClient.emit("request_nlu", JSON.stringify(payload));
  } catch (error) {
    finishAssistantMessage("发送失败，请稍后再试。", { isError: true });
    appendSystemMessage(error.message);
  }
}

function handleNluFrame(payload) {
  const frame = parseFrame(payload);

  if (!activeAssistantMessageId) {
    activeAssistantMessageId = appendMessage("assistant", "", { loading: true });
    waitingForReply = true;
  }

  const status = Number(frame.status);

  if (status === 0) {
    updateMessage(activeAssistantMessageId, "", { loading: true, replace: true });
    return;
  }

  if (status === 1) {
    updateStreamingMessage(activeAssistantMessageId, frame.frame || "", true);
    return;
  }

  if (status === 2) {
    updateStreamingMessage(activeAssistantMessageId, frame.frame || "", false);
    addFrameMeta(activeAssistantMessageId, frame);
    releaseComposer();
    return;
  }

  if (status === -1) {
    const fallback = frame.frame || frame.nlg || "这个问题暂时没法处理，可以换个说法再试。";
    updateMessage(activeAssistantMessageId, fallback, { replace: true, loading: false });
    addFrameMeta(activeAssistantMessageId, frame);
    releaseComposer();
    return;
  }

  // task 分支一般没有 status 字段，会直接返回结构化 NLU 结果。
  const text = summarizeTaskFrame(frame);
  updateMessage(activeAssistantMessageId, text, { replace: true, loading: false });
  addFrameMeta(activeAssistantMessageId, frame);
  releaseComposer();
}

function parseFrame(payload) {
  if (typeof payload === "string") {
    try {
      return JSON.parse(payload);
    } catch {
      return { frame: payload, status: 2 };
    }
  }

  return payload || {};
}

function summarizeTaskFrame(frame) {
  if (frame.nlg) {
    return frame.nlg;
  }

  const intent = frame.intent || "未知意图";
  const functionName = frame.function || frame.func || "未命中功能";
  const slots = formatSlots(frame.slots);

  if (slots) {
    return `已识别为「${intent}」，对应功能是「${functionName}」。\n槽位：${slots}`;
  }

  return `已识别为「${intent}」，对应功能是「${functionName}」。`;
}

function formatSlots(slots) {
  if (!slots || typeof slots !== "object" || Array.isArray(slots)) {
    return "";
  }

  return Object.entries(slots)
    .map(([key, value]) => `${key}=${value}`)
    .join("，");
}

function appendMessage(role, text, options = {}) {
  const id = `message-${++messageSeed}`;
  const message = document.createElement("article");
  message.className = `message ${role}`;
  message.dataset.messageId = id;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "你" : role === "system" ? "系统" : "助手";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  if (options.loading) {
    bubble.classList.add("is-loading");
  }

  message.append(label, bubble);
  dom.messageList.append(message);
  messageStore.set(id, { message, bubble, text });
  scrollToBottom();

  return id;
}

function appendSystemMessage(text) {
  appendMessage("system", text);
}

function updateMessage(id, text, options = {}) {
  const record = messageStore.get(id);
  if (!record) {
    return;
  }

  if (options.append) {
    record.text += text;
  } else if (options.replace) {
    record.text = text;
  } else {
    record.text = text || record.text;
  }

  record.bubble.textContent = record.text || "";
  record.bubble.classList.toggle("is-loading", Boolean(options.loading));
  scrollToBottom();
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
  if (!record) {
    return;
  }

  const oldMeta = record.bubble.querySelector(".meta-row");
  const oldDebug = record.bubble.querySelector(".debug-block");
  oldMeta?.remove();
  oldDebug?.remove();

  const metaItems = [
    frame.intent ? `意图：${frame.intent}` : "",
    frame.function || frame.func ? `功能：${frame.function || frame.func}` : "",
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

function releaseComposer() {
  activeAssistantMessageId = "";
  waitingForReply = false;
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
  appendMessage("assistant", "你好，我是车载 Agent 助手。");
}

function autoResizeTextarea() {
  dom.queryInput.style.height = "auto";
  dom.queryInput.style.height = `${Math.min(dom.queryInput.scrollHeight, 140)}px`;
}

function scrollToBottom() {
  dom.messageList.scrollTop = dom.messageList.scrollHeight;
}

initSettings();
bindEvents();
initSpeechRecognition();
clearMessages();
connectToBackend();
