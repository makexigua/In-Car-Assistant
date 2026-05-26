# 车载 Agent 助手 — 项目速览

## 项目定位

车载智能助手，针对特斯拉 Model 3，支持：
- **知识问答 (RAG)** — 基于 RAG 检索用户手册，回答用车问题
- **任务执行 (TASK)** — 通过意图识别 + function calling 执行车载操作（开关空调、座椅加热等）
- **闲聊 (CHAT)** — 开放域自由对话兜底

---

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | 纯 HTML + 原生 JS，零 npm/构建依赖 |
| 后端框架 | Flask + HTTP Streaming（newline-delimited JSON） |
| 大模型 | LLM API 调用（兼容 OpenAI 协议） |
| 向量检索 | FAISS (dense) + BM25 (sparse) + BGE-M3 ReRanker |
| 会话缓存 | Redis（短期记忆，60s 过期，最大 3 轮） |
| 任务执行 | MCP 协议 + 本地 Python 函数 |
| 环境配置 | `.env` + `python-dotenv` |

---

## 目录结构

```
车载agent/
├── web/                        # 前端（纯静态，无构建）
│   ├── index.html              # 主页面
│   ├── styles.css              # 样式
│   └── app.js                  # 核心逻辑（HTTP Stream + fetch ReadableStream）
│
├── main/                       # 后端主链路（Flask 入口 + 流程编排）
│   ├── start.py                # 服务入口（Flask + HTTP Streaming，端口 8080）
│   │
│   ├── client/                 # 各模块调用封装
│   │   ├── reject.py           # 拒识 → 判断问题是否合法
│   │   ├── rewrite.py          # 改写 → 结合历史做指代消解
│   │   ├── arbitration.py      # 仲裁 → 分流 task/rag/chat
│   │   ├── rag.py              # RAG → 调用 kb/online RAG 链路
│   │   ├── task.py             # TASK → 调用 task/pipeline 链路
│   │   └── chat.py             # CHAT → 调用聊天 skill + 流式切帧
│   │
│   ├── skills/                 # LLM 技能（Markdown Prompt + 运行时配置）
│   │   ├── runtime.py          # 技能加载&调用引擎（解析 Markdown frontmatter、组装请求）
│   │   └── config/
│   │       ├── reject.md       # 拒识 prompt
│   │       ├── rewrite.md      # 改写 prompt
│   │       ├── arbitration.md  # 仲裁 prompt
│   │       └── chat.md         # 闲聊 prompt
│   │
│   └── utils/
│       ├── session_memory.py   # Redis 短期记忆读写（query/answer/route/trace_id）
│       ├── redis_tool.py       # Redis 客户端封装
│       ├── logger.py           # 日志工具
│       └── env_loader.py       # 环境变量加载
│
├── task/                       # 任务型对话链路
│   ├── pipeline.py             # pipeline 编排：召回→识别→执行→NLG
│   ├── intent/                 # 意图模块
│   │   ├── recall.py           # 工具召回（基于 embedding 相似度）
│   │   └── recognize.py        # 意图识别 + 槽位抽取（LLM Function Calling）
│   ├── execute/                # 工具执行
│   │   ├── local_executor.py   # 本地函数执行器
│   │   ├── mcp_executor.py     # MCP 协议执行器
│   │   ├── mcp_client.py       # MCP 客户端
│   │   ├── function_registry.py# 函数注册与发现
│   │   ├── slot_normalizer.py  # 槽位归一化
│   │   └── nlg.py              # 自然语言生成
│   ├── llm_client.py           # LLM API 客户端
│   └── settings.py             # 常量配置（RECALL_TOP_K, DEFAULT_NLG 等）
│
├── kb/                         # 知识库（RAG 全链路）
│   ├── offline/                # 离线处理流程
│   │   ├── pipeline.py         # 离线 ETL 入口：PDF→清洗→切分→索引
│   │   ├── config/
│   │   │   ├── settings.py     # 路径配置、模型名
│   │   │   ├── models.py       # Pydantic 数据模型（ManualImages, ManualInfo）
│   │   │   ├── mongodb_config.py # MongoDB 连接配置
│   │   │   └── env_loader.py   # 环境变量加载
│   │   ├── scripts/
│   │   │   ├── pdf_parser.py   # PDF 解析（PyMuPDF → text + images）
│   │   │   ├── image_handler.py# 图片提取 + 标题关联
│   │   │   ├── text_cleaner.py # LLM 文本清洗（20线程并发）
│   │   │   ├── semantic_splitter.py # 语义切分（标题/空行/LLM 三级降级）
│   │   │   ├── doc_splitter.py # 文档分块（语义分组→递归切分，256/50）
│   │   │   └── index_builder.py# 索引构建（MongoDB + BM25 + FAISS）
│   │   └── data/               # 数据文件
│   │       ├── raw/            # 原始文件（Tesla_Manual.pdf, stopwords.txt）
│   │       ├── processed/      # 处理产物（docs, images, index）
│   │       └── datasets/       # QA 数据集
│   │
│   └── online/                 # 在线检索
│       ├── pipeline.py         # RAG 主入口：双路召回→RRF→Rerank→LLM
│       ├── config/
│       │   └── llm_client.py   # LLM 问答 Prompt + API 调用
│       └── retrieval/
│           ├── recall/
│           │   ├── bm25_retriever.py   # BM25 词法召回
│           │   ├── faiss_retriever.py  # FAISS 向量召回
│           │   └── milvus_retriever.py # Milvus 召回（当前未启用）
│           ├── rerank/
│           │   └── bge_m3_reranker.py  # BGE-M3 重排序
│           └── postprocess.py  # 合并去重、RRF 融合排序
│
├── readme/                     # 策略文档
│   └── kb策略总结.md
│
├── .env                        # 环境变量（不提交）
├── .env.example                # 环境变量模板
├── server.sh                   # 启动脚本
├── requirements.txt            # Python 依赖
└── pyproject.toml              # 项目元数据
```

---

## 核心请求处理流程

```
用户输入 → web/app.js → POST /agent (HTTP Stream) → main/start.py
                                                        │
                                                    ┌───┴───┐
                                                    │ 拒识   │ ← LLM: 判断是否合法
                                                    │ reject │
                                                    └───┬───┘
                                                        │ 非法 → status=-1 返回
                                                    ┌───┴───┐
                                                    │ 改写   │ ← LLM: 指代消解
                                                    │ rewrite│    ("打开它"→"打开空调")
                                                    └───┬───┘
                                                    ┌───┴───┐
                                                    │ 仲裁   │ ← LLM: 路由分流
                                                    │ arbit. │
                                                    └───┬───┘
                                                        │
                     ┌──────────────────────────────────┼──────────────────────┐
                     ▼                                  ▼                      ▼
               ┌──────────┐                     ┌──────────────┐      ┌──────────────┐
               │  TASK    │                     │  RAG          │      │  CHAT        │
               │ 任务执行  │                     │ 知识库问答    │      │ 闲聊         │
               │          │                     │              │      │              │
               │ intent   │                     │ FAISS 召回   │      │ chat skill   │
               │ recall   │                     │ BM25 召回    │      │ (流式输出)    │
               │ func     │                     │ RRF 融合     │      │              │
               │ calling  │                     │ Rerank top5  │      │              │
               │ MCP/本地  │                     │ LLM 问答     │      │              │
               │ NLG 生成  │                     │              │      │              │
               └────┬─────┘                     └──────┬───────┘      └──────┬───────┘
                    │                                  │                     │
                    └──────────────────────────────────┼─────────────────────┘
                                                       ▼
                                          HTTP Streaming (NDJSON)
                                          POST /agent 流式返回每行一个 JSON
                                                       │
                                          fetch ReadableStream ← 前端 app.js
                                                        │
                                                   展示气泡 + meta 标签
```

**状态码约定（前后端帧协议）**：
- `status=0`：开始处理（清空气泡，显示 loading）
- `status=1`：流式中间帧（追加文本）
- `status=2`：结束帧（最终文本）
- `status=-1`：拒绝/错误

---

## 关键文件快速定位

| 入口 | 文件 | 说明 |
|------|------|------|
| 服务启动 | [main/start.py](main/start.py) | Flask 入口，`POST /agent` 流式处理 |
| 前端页面 | [web/index.html](web/index.html) | 问答界面，语音输入按钮 |
| 前端逻辑 | [web/app.js](web/app.js) | HTTP Stream + fetch ReadableStream 客户端，UI 渲染 |
| 技能调度 | [main/skills/runtime.py](main/skills/runtime.py) | LLM skill 加载/调用引擎（核心复用模块） |
| 任务链路 | [task/pipeline.py](task/pipeline.py) | intent → execute → NLG 编排 |
| RAG 在线 | [kb/online/pipeline.py](kb/online/pipeline.py) | 双路召回 + 重排 + LLM 问答 |
| RAG 离线 | [kb/offline/pipeline.py](kb/offline/pipeline.py) | PDF 解析 → 清洗 → 切分 → 索引 |
| 会话记忆 | [main/utils/session_memory.py](main/utils/session_memory.py) | Redis 读写，3轮60s过期 |
| 工具注册 | [task/execute/function_registry.py](task/execute/function_registry.py) | 函数注册与发现中心 |
| 启动脚本 | [server.sh](server.sh) | 统一启动入口 |

---

## 通信方式

- **协议**: HTTP Streaming（newline-delimited JSON）
- **前端**: `fetch` + `ReadableStream`，逐行解析 JSON
- **后端**: `Flask` + `stream_with_context`，生成器逐行 yield JSON
- **音频输入**: 浏览器原生 `SpeechRecognition` API（需 HTTPS）

前端零 npm 依赖，纯手写 HTML + JS，文件丢到 Nginx 或直接打开就能跑。调试方便，`curl` 即可查看完整流式返回。

---

## 配置与运行

### 环境变量（.env）

```
# LLM
LLM_BASE_URL=https://api.xxx/v1
LLM_API_KEY=sk-xxx
DEFAULT_CHAT_MODEL=gpt-4o-mini
REJECT_MODEL=           # 可选，缺省走 DEFAULT_CHAT_MODEL
REWRITE_MODEL=           # 同上
ARBITRATION_MODEL=       # 同上
CHAT_MODEL=              # 同上

# Embedding 模型（RAG 用）
EMBEDDING_MODEL=text-embedding-v3
SEMANTIC_MODEL=
RERANK_MODEL=           # 本地 BGE-M3 模型路径

# MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB_NAME=car_agent

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Server
FLASK_SERVER_PORT=8080
ENABLE_DEBUG_API=false   # true 时开放 /debug/session/{id}

# RAG 参数
FAISS_TOPK=20
BM25_TOPK=20
RRF_TOPK=20
RERANK_TOPK=5
```

### 启动

```bash
python main/start.py
# 前端访问 http://localhost:8080
```

### 调试单模块

```bash
# 直接运行单个模块测试（很多模块有 __main__ 入口）
python kb/online/pipeline.py     # RAG 问答测试
python main/client/arbitration.py  # 仲裁逻辑测试
python main/client/reject.py       # 拒识测试
python task/pipeline.py            # 任务链路测试

# 查看会话记忆（需 ENABLE_DEBUG_API=true）
curl http://localhost:8080/debug/session/{sender_id}
```

---

## 重要设计决策

| 决策 | 原因 |
|------|------|
| 前端手写 HTTP Streaming 而非 WebSocket | 协议简单，curl 可调试，nginx 原生支持，无状态易扩展 |
| 选 Flask 而非 FastAPI | LLM 调用是同步等待，async 无收益；`stream_with_context` 足以满足流式需求 |
| Skill 用 Markdown 文件 | prompt 和运行参数分离（详见 [runtime.py](main/skills/runtime.py)） |
| RAG 的双路召回 | FAISS (语义) + BM25 (词法) 互补，RRF 融合、Rerank 精排 |
| Chunk 策略 | 语义切分（标题→空行→LLM）→ 递归切分（256/50 tokens）两层结构 |
| Redis 短期记忆 | 60s 自动过期，避免记忆堆积；用于改写 + 仲裁 + 闲聊三模块 |
| 帧协议（status 0/1/2/-1） | 统一流式/非流式输出格式，前端渲染逻辑一致 |
| RAG 空答案兜底 | RAG 无命中时自动降级到 CHAT 链路，保证用户始终有回复 |
| 改写回退保护 | 改写结果与原句字词重叠 < 25% 时用原句，防止 LLM 过度改写 |

---

## 常见开发操作

```bash
# 重新构建知识库索引（PDF 有更新时）
python kb/offline/pipeline.py

# 查看当前环境变量配置
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.environ.get('LLM_BASE_URL'))"

# 测试单条 query 走完整链路（newline-delimited JSON 流式返回）
curl -X POST http://localhost:8080/agent -H "Content-Type: application/json" -d '{"query":"怎么开空调","sender_id":"test","trace_id":"t1"}'

# 清空 Redis 会话
redis-cli KEYS "voice:session:*" | xargs redis-cli DEL
```
