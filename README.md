# 车载三路决策Agent：Task/RAG/Chat

## 文件结构
```text
.
├── main/      # 主链路：请求入口与全链路编排
├── task/      # 任务型链路：意图、槽位、function calling、MCP
├── kb/        # 知识库链路：RAG 相关代码与数据
├── web/       # 前端页面：简洁问答助手界面
├── .env       # 本地运行配置（API Key / 服务地址）
├── .env.example
└── AGENTS.md  # 项目速览与维护约定
```

## 短期记忆机制

短期记忆统一放在 Redis 的一个 key 里：`voice:session:{sender_id}`。  
每个 `sender_id` 对应独立会话，value 是最近 3 轮对话数组，每轮包含：
- `query`：用户原始输入
- `answer`：本轮最终回答（task / rag / chat 产物）
- `route`：本轮走的链路（`task` / `faq` / `chat`）
- `trace_id`：请求唯一标识
- `created_at` / `updated_at` / `expires_at`：时间字段

执行规则：
1. 新请求先走拒识。  
   如果拒识不通过：直接返回非法提示，不写入短期记忆。
2. 拒识通过后，先写入一条占位记录：`query + trace_id`，`answer` 暂时为空。
3. 当 task/rag/chat 任一链路执行完成后，再按 `trace_id` 回填 `answer + route`。  
   这样可以避免并发请求时写错轮次。
4. 只保留最近 3 轮。  
   每次写入会自动裁剪最老轮次。
5. 每轮单独过期 60 秒。  
   超过 60 秒的轮次会在读取时清理；key 本身也设置 60 秒 TTL，所以最后一轮后 60 秒无新请求，整段会话自动清空。
6. 改写阶段只读取 Redis 里“未过期且 answer 不为空”的轮次。  
   也就是只用已完成的有效上下文，不用半成品数据。

一句话总结：这是一个“单 key、短窗口、按 trace_id 回填”的会话记忆机制，既能保证多轮改写连续性，又把状态复杂度控制在最小范围。
