# Ticket 03 验收记录

日期：2026-11-14。起点 `da84581`。独立 Python 服务、MySQL 8.4（`127.0.0.1:13306`）、Redis 7（`127.0.0.1:6379`）、`AsyncSqliteSaver`，Java 服务未启动。

## 范围与业务效果

已交付原接口编号 38（`GET /api/agent/{id}/sessions`）、39（`POST /api/agent/{id}/sessions`）及 64（`GET /api/stream/search`）最小持久化 MySQL 查询闭环，并在前端 Python 模式接入携带 `X-API-Key` 的 `fetch` SSE 客户端。

- **会话管理**：`POST/GET /api/agent/{id}/sessions` 校验 Agent 存在及生命周期，持久化 `chat_session`，按 `is_pinned DESC, update_time DESC, create_time DESC` 返回；新问题生成新 `threadId`，`conversationId` 跨轮复用。
- **Redis 短锁 + MySQL 会话占用**：`RunCoordinator` 使用 `dataagent:run:{agentId}:{conversationId}` owner-token 短锁（Lua 比较 token 续期/释放）与 `agent_session_runtime` 行锁/唯一占用。Redis 不可用拒绝新建；错误 token 不能释放/续期；锁过期不放行第二次执行；不同会话可并行。
- **最小 LangGraph 查询路径**：`SchemaRecallNode -> PlannerNode -> SqlGenerateNode -> SqlExecuteNode -> AnswerNode`。读取已选表与 `python_agent_schema` 快照，调用激活 `CHAT` 模型生成只读 `SELECT` SQL，经真实 MySQL 执行并序列化 `DECIMAL`/`DATE` 等类型，输出 `NODE_OUTPUT`、`SQL`、`RESULT_SET`、`FINAL_ANSWER` 与唯一终止 `complete` / `error`。
- **持久化与重入**：`AsyncSqliteSaver` 保存中断状态；`graph_effect`（`v1:sql_execute:main:0`）记录 `PREPARED -> IN_FLIGHT -> COMMITTED`，已提交效果重入直接读取 `result_ref` 而不重发 SQL；成功结果先写入 `agent_run_result`、提交 `agent_conversation_turn` 并条件释放 `active_thread_id`，再发送 `FINAL_ANSWER` 与 `complete`。SQL 连接中断/超时（`OperationalError`）保留 `IN_FLIGHT` 与占用，等待对账；确定性 SQL 错误标记 `FAILED` 并释放占用。
- **前端 fetch SSE**：`sse.ts` 实现 `SseFrameParser`（支持 CRLF/LF、分片帧、多行 `data:`、comment）与 `streamSearchFetch`（串行处理帧回调、携带 `X-API-Key`、401 在建流前报错、不自动重试）。`stores/chat.ts` 在 Python 模式下对尚未交付的 Ticket 05 消息/标题流 404 做兼容降级，不影响 Java 模式。

## 自动验证与边界

- Python 全量测试：`pytest -q` **22 passed**（50.98s），覆盖模型、Agent/API key、MySQL 元数据与绑定、会话创建/列表/重启持久化、真实 MySQL 查询 SSE、401/跨 Agent 404、Redis 不可用/锁过期/错误 token/并行会话、中断重启恢复、`graph_effect` 已提交重入不重发 SQL、错误流与占用释放。
- 类型与规范检查：`mypy app tools`（0 issues）、`ruff check app tests tools`（All checks passed!）。
- 前端单测：`vitest run` **7 files, 20 passed**（含 `app/services/graph/sse.test.ts` 3 项）。

## 已观察的页面操作（Playwright + 真实模型）

- 独立启动 Python 服务（`127.0.0.1:8065`）与 Nuxt 前端（`NUXT_PUBLIC_BACKEND=python`，`localhost:3000/chat?agentId=1`），使用已有 `Ticket02 页面验收` Agent（`apiKeyEnabled=1`）、激活的 `gpt-6.1-sol` 聊天模型及 `dataagent_ticket02_demo.sales` 数据源。
- 页面自动加载/创建 `新会话` 与预设问题；未输入 API Key 点击发送“销售总额是多少？”时，在建流前呈现 `HTTP 401: API Key 无效或缺失`。
- 在内存输入栏填入有效 API Key 并点击“验证凭据”显示“凭据有效”；开启“显示SQL结果”后再次发送“销售总额是多少？”，页面完整呈现时间线 `Schema 召回 -> 制定计划 -> SQL 生成 -> SQL 执行` 及最终回答 `销售总额暂无数据（查询结果为 NULL）。`。
- 说明：控制台存在对尚未交付的 Ticket 05 消息接口（`/api/sessions/{id}/messages`）的 404 请求，前端按预期降级处理，不影响本票查询闭环。

## 未在本票展开的后续项

- 历史消息、标题流、运行列表/详情找回留给 Ticket 05；在线审核完整 UI、启动对账与配置指纹二次校验留给 Ticket 11/12/13。
