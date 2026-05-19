# 车载 Agent 重构版

## 文件结构
```text
.
├── main/      # 主链路：请求入口与全链路编排
├── task/      # 任务型链路：意图、槽位、function calling、MCP
├── kb/        # 知识库链路：RAG 相关代码与数据
├── web/       # 前端页面：简洁问答助手界面
├── server.sh  # 项目统一启动脚本（root）
├── .env       # 本地运行配置（API Key / 服务地址）
├── .env.example
└── AGENTS.md  # 项目速览与维护约定
```

### main（主链路）
- `start.py`：主入口（拒识 -> 改写 -> 仲裁 -> task/faq/chat）
- `client/`：各子服务 API 调用封装（reject、rewrite、arbitration、nlu、rag、chat）
- `prompts.py`：提示词配置
- `utils/`：日志、redis、env 加载
- 备注：`main/client/correlation.py`、`main/client/nlg.py` 已清理（主链路不再使用）

### task（任务型链路）
- `function_call/chatnlu_infer.py`：任务型 NLU 服务入口
- `function_call/function.py`：function calling 工具定义
- `function_call/slot_process.py`：槽位后处理
- `function_call/dm/`：天气/地图/音乐等 DM 执行逻辑
- `mcp_core/`：MCP 客户端与工具服务
- `config/`：任务型映射配置（意图/槽位映射）
- 本轮重构：修复了配置路径定位、MCP 服务脚本路径定位和无用代码

### kb（知识库链路）
- `src/`：RAG 核心代码（解析、检索、重排、客户端）
- `data/`：索引与语料数据
- `build_index.py` / `infer.py`：索引构建与推理脚本
- 本轮重构：修复了硬编码绝对路径和 FAISS 加载变量错误（`save_path`）

## 使用方法

### 1. 配置环境变量
先复制配置模板并填写：
```bash
cp .env.example .env
```

重点变量：
- `LLM_API_KEY` / `LLM_BASE_URL` / `DEFAULT_CHAT_MODEL`
- `ARBITRATION_API_KEY` / `ARBITRATION_BASE_URL`（可选，不填则回退到 LLM 配置）
- `REWRITE_API_KEY` / `REWRITE_BASE_URL`（可选，不填则回退到 LLM 配置）
- `CHAT_API_KEY` / `CHAT_BASE_URL` / `CHAT_MODEL`（可选，不填则回退到 BOT_ 或 LLM_ 配置）
- `REJECT_BASE_URL` / `REJECT_API_KEY` / `REJECT_URL`（拒识服务）
- 拒识调用规则：`REJECT_BASE_URL + REJECT_API_KEY` 都不为空走外接模型；否则走 `REJECT_URL` 本地模型
- `INTENT_URL`（意图召回服务）
- `NLU_URL`（任务型 NLU 服务，通常是本地 `task` 服务）
- `RAG_URL`（知识库问答服务）
- `ENTRY_URL`（主入口地址）

### 2. 准备 Python 环境
先在根目录创建虚拟环境：
```bash
python3 -m venv .venv
```

说明：
- `server.sh` 会优先使用 `.venv/bin/python`
- 当前脚本会自动复用用户目录已安装依赖（`python3 -m site --user-site`），所以不强制你现场装包
- 如果你后续要做完整部署，再按需安装 `main/requirements.txt` 和 `kb/requirements.txt`

### 3. 启动服务
在项目根目录执行：
```bash
bash server.sh
```

这个脚本会：
1. 启动 `task/function_call/chatnlu_infer.py`
2. 启动 `main/start.py`

注意：
- `REJECT_URL`、`INTENT_URL`、`RAG_URL` 指向的外部服务需要你提前启动好
- 若这些外部服务未启动，对应分支会失败或走兜底

### 4. 调用入口
主入口默认是 socket 事件 `request_nlu`，健康检查：
```bash
GET /health
```

### 5. 使用前端页面
前端代码在 `web/` 目录下，是零构建静态页面：
- `web/index.html`：页面结构
- `web/styles.css`：界面样式
- `web/app.js`：Socket.IO polling 通信、消息渲染与语音输入

部署时建议让前端和 `main/start.py` 入口服务走同一个域名。这样前端会自动使用当前页面域名连接后端，不需要把服务器地址写死到代码里。

如果前端和后端分开部署，在页面顶部的“后端地址”里填写后端入口服务域名即可；该配置只会保存在当前浏览器本地。

前端输入框旁边提供语音输入按钮。当前版本使用浏览器原生语音识别能力，识别出的文字会先填入输入框，再复用原有 `request_nlu` 文本链路发送给后端。正式部署时建议使用 HTTPS，否则浏览器可能不允许网页访问麦克风。

## 说明
- 当前目录已清理测试代码与 benchmark 脚本，保留生产链路与必要配置。
- 若你调整了目录结构或链路逻辑，请同步更新 `AGENTS.md` 和本 README。
