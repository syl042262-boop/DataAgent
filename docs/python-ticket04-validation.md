# Ticket 04 验收记录

日期：2026-11-15。起点 `c6cb32b`。独立 Python 服务、MySQL 8.4（`127.0.0.1:13306`）、PostgreSQL 16（`127.0.0.1:15432`）、Redis 7（`127.0.0.1:6379`）、`AsyncSqliteSaver`，Java 服务未启动。

## 范围与业务效果

已交付原接口编号 56–60（`/api/datasource/{id}/logical-relations*`）、73–86（`/api/prompt-config/*`）、PostgreSQL 连接器与方言查询扩展，以及不含密钥的有效配置读取与指纹（`GET /api/agent/{id}/effective-config`）。

- **PostgreSQL 数据源与查询**：`datasources.py` 新增 `postgresql_connection_options`、`DIALECT_INFO` 与 `NullPool` + `engine.dispose()` 连接管理，支持 `schemaName`/`currentSchema`、`sslmode`、`connectTimeout`/`socketTimeout`，并拒绝 URL 内嵌凭据。`query_graph.py` 按数据源方言生成 SQL（PostgreSQL 双引号与大小写混合标识符）、执行 `SELECT pg_backend_pid()`、序列化 `UUID`/`NUMERIC`/`JSONB`/`TIMESTAMPTZ` 等类型，并通过 `agent_run_result` 持久化供重开会话读取；覆盖连接失败、SQL 错误与查询超时恢复。
- **提示词配置与工具兼容性**：`prompts.py` 实现 73–86 全部接口，`/api/prompt-config/types` 移除 `python-generator`。`check_prompt_compatibility` 对默认、自定义、导入与编辑配置检查 Python 工具指令，发现时保留原文、返回行列号与原因并禁止激活；运行时在 `PlannerNode` 使用 `ALLOWED_PLAN_TOOLS` 白名单校验，在 `SqlGenerateNode` 按优先级与 `displayOrder` 注入生效提示词，忽略禁用配置。
- **逻辑关系与列映射**：`logical_relations.py` 实现读取、创建、更新、软删除与批量保存，校验数据源表/列存在性并拒绝重复映射；`SchemaRecallNode` 将已选表间的逻辑关系注入 `SqlGenerateNode` 上下文，固定双表查询案例验证配置前后生成 `JOIN` SQL 与查询结果变化。
- **有效配置与指纹**：`effective_config.py` 提供不含明文密钥的 `read_effective_config` 与 `GET /api/agent/{id}/effective-config`，`stream.py` 与 `query_graph.py` 统一使用该指纹；密码轮换不改变指纹，数据源/选表/逻辑关系/生效提示词/模型变更产生新指纹。

## 已观察的前后端联调（Playwright MCP + 真实 PostgreSQL 16 + 真实模型）

- 独立启动 Python 后端（`127.0.0.1:8065`）与 Nuxt 前端（`NUXT_PUBLIC_BACKEND=python`，`localhost:3000`），Java 服务未启动。
- **数据连接与逻辑外键（`/system/data-sources?agentId=1`）**：新建 PostgreSQL 数据源 `Ticket04 PG`（`127.0.0.1:15432/dataagent_pg`），测试连接显示“连接成功”；在“逻辑外键”弹窗新增 `t_order.buyer_uid -> t_user.id`（`1:N`）；绑定为当前数据源、启用并勾选 `t_order` 与 `t_user` 保存并初始化 Schema。
- **提示词配置（`/prompt-config?agentId=1`）**：新增并保存 `Ticket04 SQL 规则`（状态为“启用”）。
- **数据问答（`/chat?agentId=1`）**：输入并验证 Agent API Key（显示“凭据有效”），新建会话发送“查询每个用户的用户名和订单总金额”，经真实 `gpt-6.1-sol` 模型与真实 PostgreSQL 16 双表联查，页面成功输出 `Bob: 88.00`、`Alice: 199.50`（注：控制台对尚未交付的 Ticket 05 `/api/sessions/*/messages`、`/runs` 及 `/sessions/stream` 存在预期 404）。

## 自动验证与边界

- Python 全量测试：`pytest -q` **28 passed**（67.58s），含 `tests/test_postgresql_http.py`（3 项，连接真实 PostgreSQL 16）、`tests/test_prompts_http.py`（2 项）及 `tests/test_logical_relations_http.py`（1 项），模型端使用可控本地 HTTP 服务。
- 类型与规范检查：`mypy app tools`（0 issues in 18 source files）、`ruff check app tests tools`（All checks passed!）。
