## 项目速览（给下次加载用）

### 维护约定
- 新增配置优先写入根目录 `.env` 和 `.env.example`

### 目录约定
- `main/`：主链路编排层（入口服务、拒识/改写/仲裁调度、task/faq/chat 路由）
- `main/skills/`：主链路 skill 配置与执行器（reject/rewrite/arbitration/chat）
- `task/`：任务型链路（意图召回、function calling、槽位抽取、DM/MCP）
- `kb/`：知识库链路（RAG 数据、检索、重排、知识问答相关脚本）
  - `kb/offline/data/`：全部数据文件（原始资料、处理产物、QA 数据集、微调数据）
  - `kb/offline/scripts/`：离线数据处理与入库脚本（PDF 解析、图片提取、语义切块、索引入库）
  - `kb/offline/src/`：离线支撑库（常量、客户端封装、Pydantic 模型）
  - `kb/online/`：在线检索与 RAG 服务
- `web/`：前端静态页面（简洁问答助手界面，默认按当前页面域名连接后端，带浏览器原生语音输入入口）

### 当前主流程
1. 用户请求进入 `main/start.py`
2. 先走拒识（非法问题直接返回）
3. 再走改写（结合历史做指代消解）
4. 走仲裁分三路：`task` / `faq` / `chat`
5. `task` 调 `task` 服务，`faq` 调 `RAG_URL`，`chat` 走闲聊流式返回

### 启动关系
- `main` 依赖 `task/pipeline.py`
- 拒识服务、意图召回服务、RAG 服务是外部服务，通过 URL 对接
- 项目统一启动脚本在根目录：`server.sh`
- `server.sh` 优先使用根目录 `.venv/bin/python`
- `server.sh` 会自动补 `NO_PROXY=127.0.0.1,localhost,::1`，避免本地调用被代理影响
- `web/` 不依赖 npm 构建；部署时可由 Nginx 等静态服务托管，和后端同域时无需手动填写后端地址

### 重构状态（2026-05）
- `main`：已清理未使用 client（`correlation.py`、`nlg.py`）与运行日志目录
- `task`：已修复配置文件路径定位、MCP 脚本路径定位，去掉死代码与无用导入
- `kb`：已改为相对路径常量，修复 FAISS 加载变量错误，移除历史日志目录
- 已删除 `kb/data` 下未引用的测试数据文件（`test*.json`）


