# Ticket 09：实施及验收记录（已完成）

本记录保留实施阶段证据，最终状态以文末验收结论为准。代码审查固定起点为 `42fc913`。前后端浏览器联调在实现、测试、双轴审查和提交完成后执行，现已完成。

## 外部向量存储

已实现 `DATAAGENT_VECTOR_BACKEND=local|elasticsearch|milvus`，外部目标由 `VECTOR_URL`、`VECTOR_NAMESPACE` 指定；可选 `VECTOR_TOKEN` 以 Bearer 头发送。禁止 URL 携带凭据、query 或 fragment。凭据不进入有效配置指纹、持久化目标清单或响应错误。

外部存储使用当前激活 embedding 重新计算向量，不复制 Java 向量。集合名包含 embedding/目标空间的哈希及维度。MySQL 的所有者、内容版本、索引版本、启用状态、活动模型和语义选表仍是召回依据，过滤在 topK 前生效。只有远端发布和本地 manifest 写入均成功，MySQL 才发布 COMPLETED。外部故障不回退本地检索。

每次外部召回校验已发布版本的分块数量；丢失集合或部分分块时，受影响记录标记 FAILED，返回脱敏错误。管理页重试或 `POST /api/agent/{id}/knowledge/rebuild` 可以重建。知识删除先清远端，失败保留目标以便重试；Agent 删除使用持久化 cleanup job 重试。切换目标前须清理旧目标，或保留其可访问性；当前新目标的 token 不发送到历史目标，旧目标需要鉴权时应恢复旧配置完成清理后再切换。

### 实际环境

- Elasticsearch 9.5.6：隔离容器 `dataagent-ticket09-es`，本机 19200，独立命名卷。
- Milvus 2.6.17：隔离容器 `dataagent-ticket09-milvus`，本机 19531，嵌入式 etcd/本地存储，独立命名卷。
- 未改动原有的旧 Milvus 容器。

已在真实 ES/Milvus 的公开适配接口及知识 HTTP 接口验证：三类知识写入、跨 Agent 过滤、版本替换、删除、后端重新打开、丢失集合后的明确失败及重建、部分重建后其余记录仍 FAILED、文档分块缺失检测。模型 HTTP 边界使用可控 embedding 输出，管理库使用真实 MySQL。

另以专用测试 namespace 写入三类数据后，分别实际 `docker restart` 两个隔离容器，服务就绪后召回全部数据、发布新版本并清理，均通过。此项与后端重新创建客户端的测试分别记录，不能互相替代。

本轮双轴增量审查发现并修复：历史目标凭据误用、ES HTTP 200 部分失败误判、远端数据缺失被集合存在掩盖、同步清理阻塞事件循环。最终全量审查及最终测试仍待完成。

## 迁移数据来源

用户确认 Java 项目直接来自 GitHub，未配置 Java Agent API key；允许使用仓库自带 SQL/示例数据建立副本，并沿用 Python 的模型凭据做真实调用。迁移验收将注明此来源，不宣称验证过真实生产存量。密钥编码使用临时访问凭据另外验证。

初始待办（现已完成，详见后续证据）：公开迁移 CLI、13 张表及内部/saver 分账、ID/绑定/选表/凭据/文件/历史/记忆政策验收、98 项映射复核、真实模型综合场景、配置与取消/恢复/删除组合场景、启动与切回 Java 指南、最终双轴审查和浏览器联调。

## 首轮迁移 CLI 证据

`python -m app.migration` 已通过 6 项 CLI + HTTP 测试（legacy 与 bcrypt 两种密钥各 3 项）：仓库 Java SQL 建立独立副本；预检；业务导入；重复导入；ID/历史 PYTHON 展示/文件/鉴权/无旧运行；中途字段不兼容导致业务全部回滚并可重试；已删除 Agent 后的旧目标库即使业务表清空仍因生命周期墓碑拒绝复用。

源连接只执行只读一致性快照，源/目标实际 server UUID 和 schema 对比防止别名绕过。导入不复制内部运行和 Java checkpoint，Python 模型记忆策略为 REBUILD_FROM_NEW_SUCCESSFUL_TURNS。首轮命令/前置条件和限制已写入 PYTHON/README.md，文件引用、真实连接和模型验证已在后续阶段完成。

## 两阶段 embedding 迁移

新增停服维护命令 `python -m app.vector_operations --model-id ID`，在线热切换守卫保持不变。SQLite chunks 主键加入 space，并以 SQLite 事务兼容原表。完整新空间先暂存，不修改 MySQL 已发布状态且不删除旧向量；全部写入后核验模型/内容版本，同 MySQL 事务发布索引状态和默认模型。存在非终态或未完成 cleanup 时拒绝维护。

本阶段 10 项迁移测试通过，另以 local、真实 ES、真实 Milvus 各验证“第一条成功、第二条 embedding HTTP 503”的部分失败：旧空间与 COMPLETED 状态保持，服务重新打开后仍召回两条；重复维护命令完成新空间切换。两轴审查指出的非隔离重建已修复并复核。模型在这些回归中为可控 HTTP 输出，真实供应商迁入知识验证仍待执行。

知识文件、头像和历史报告的内容寻址转换已通过 HTTP 读取回归；消息正文及嵌套 JSON metadata 同步改写。文件预检以不可变 bytes 保存，摘要和实际复制采用同一内容。

## 真实迁入数据与供应商验证

本机验收批次 dc3964ae0572 使用仓库 Java schema.sql/data.sql 创建只读源副本，另建独立 MySQL 商品业务库及 local/ES/Milvus 三个 Python 管理库；没有启动 Java，也没有修改原 Java 数据库。仅将 Python 已配置的模型凭据显式复制到源副本，用于验证凭据及模型配置经迁移后的实际调用。

三套目标均保留 13 表计数：Agent 4、数据源 2、业务知识 5、语义模型 6、知识 8、逻辑关系 0、绑定 4、选表 2、预设问题 0、会话 0、消息 0、Prompt 0、模型 3。知识中的一份本地政策文件也实际复制。CHAT gpt-6.1-sol 和 EMBEDDING BAAI/bge-m3 探测均通过。三套都用真实 BAAI/bge-m3 重新计算向量，Agent 1 按绑定选表召回 14 条，包含 business/semantic/document；重新打开后记录集合一致。

管理库另有 17 张内部/版本表：agent_cleanup_job、agent_conversation_turn、agent_lifecycle、agent_operation_audit、agent_run、agent_run_result、agent_session_runtime、chat_message_key、graph_effect、python_agent_schema、python_data_import、python_datasource_options、python_knowledge_state、python_local_file、python_model_type_lock、python_recall_config、python_schema_migration。saver 单列 checkpoints.sqlite 的 checkpoints/writes，知识缓存单列 knowledge.sqlite 的 chunks/external_targets。Java JDBC memory 和 MysqlSaver 框架表不复制；本示例没有实际框架数据，CLI 测试另加入虚构 Java checkpoint 表证明其被排除。

HTTP/SSE 真实查询：MySQL 已完成订单金额 11142.00；PostgreSQL t_user/t_order 联表聚合 Alice 199.50、Bob 88.00。两条运行均 SUCCESS，服务重新打开后通过结果详情找回同一快照。真实审核、报告和追问综合运行正在补充。

机器运行报告和 SSE 轨迹保存在被忽略的 PYTHON/data/acceptance/ticket09_dc3964ae0572/，其中 target.env 含本机连接凭据，不能提交。仓库只记录不含凭据的结论与来源，不能把示例复制当成真实生产存量迁移证明。

### 全套及总审进展

总审前后端全套 92 项通过（含 DOC，无跳过），ruff、mypy 35 模块及独立进程 saver 通过。前端 20 项单元测试通过；修正前序服务导入/类型问题并在项目内固定 vue-tsc 3.2.4 后，Nuxt 全局类型检查通过，冻结 pnpm 锁文件安装已验证。此结论替代前面记录的类型检查遗留失败状态。

真实模型 HTTP 审核链已通过：初始版本 1，后端重新打开后恢复原卡片，拒绝重规划至版本 2；再次重新打开、拒绝过期版本 1，再接受版本 2，生成可下载报告；同会话追问成功；结果重启找回和稳定 messageKey 重复补存不产生重复消息。轨迹在 real-review-report.json 及对应 SSE 文件。

98 映射已有 92 个在全套成功测试中记录到 2xx 公共 HTTP 调用；余下六个入口新增三项实际往返测试，均已通过：文档更新及版本/重启、业务知识列表、单个语义删除、Prompt 列表/类型归属过滤、空闲批量清会话及晚到消息拒绝/新会话。正在最后汇总完整 98 项调用记录。调用记录本身仍需结合测试断言及兼容矩阵，不把路由存在当作副作用证明。

总审发现并修复了迁入展示消息文件引用的清理遗漏：正文和嵌套 metadata 参与候选与存活引用检查；暂存报告以持久化文件效果记录保护；引用写入和删除串行化。新增共享历史/最后引用删除及迁入历史报告删除的公共 HTTP 回归已通过。最终复审及包含此修复的全套复跑在浏览器联调前完成。

### Java 文件前缀兼容

迁移默认识别 Java 的 /uploads、控制器形式 /api/upload/uploads，以及 Python /api/upload/files。若 Java 自定义 url-prefix，传 --source-url-prefix /custom-prefix。source-files 指向 Java uploads 根目录，保留 data-agent 等存储路径前缀；转换后统一为 Python 内容寻址链接。四种 key/文件前缀组合的导入、重复执行、历史/头像/文件 HTTP 读取、删除清理均通过；本轮迁移测试共 19 项通过。

### 联调前检查结论

包含文件引用修复的全套 96 项通过、4 条依赖库提示（SQLAlchemy tuples 弃用和样例 Excel 默认样式），无失败或跳过；后续 Java 前缀增量 19 项通过，ruff/mypy 35 模块通过。实际 98/98 原映射在通过测试中均有 2xx HTTP 调用，并附测试及错误状态，详见 python-ticket09-http-acceptance.md。前端 20 unit tests、npm run typecheck、冻结 pnpm 安装及文档生成通过。双轴总审已闭环，详见 python-ticket08-09-review.md。浏览器联调将在这些提交后开始，ticket 最终完成状态留待联调验收。

## 最终验收结论

Ticket 08、09 已完成。严格按用户要求：实现和测试、双轴代码审查、修复复核及 Git 提交完成后，才进行最后浏览器前后端联调。最终后端 **102 passed**，耗时 539.66 秒，无失败、无跳过；4 条非失败提示来自 SQLAlchemy tuples 弃用与样例 Excel 默认样式。ruff 全部通过，mypy app/tools 35 模块通过，独立进程 saver 中断恢复通过。前端 20 项单元测试、全局 npm run typecheck、冻结 pnpm 锁文件安装和文档生成通过。98/98 原接口在通过测试中有实际 2xx 调用，逐接口与错误状态见 [运行证据](python-ticket09-http-acceptance.md)。

Standards 初始 P3 文档问题、Spec 初始 P2 历史文件引用清理问题均已修复并各自复核，当前两轴未解决发现均为 0。Java 默认文件前缀兼容另经只读复核，无路径安全阻塞。审查范围及结论见 [双轴报告](python-ticket08-09-review.md)。

### 最后浏览器前后端联调

使用 Python 模式 Nuxt 3001、Python 8065、真实模型 gpt-6.1-sol/BAAI/bge-m3、真实 MySQL/PostgreSQL 与隔离 ES/Milvus。

| 场景 | 结果 |
|---|---|
| 待审核后实际停止并重启后端、刷新页面 | 原计划恢复，同 threadId 34518625-3e4c-4dc8-b3a0-934b82bede4e |
| 页面拒绝计划 | 同运行 planRevision 从 1 到 2，显示新计划 |
| 再次实际重启后端和刷新，再接受 | 版本 2 完成，页面显示 GMV 11,142.00 元并生成报告 |
| 当前密钥与刷新 | 旧 key 轮换后验证失败，新 key 有效；刷新密码框为空，重新输入后历史恢复 |
| 页面追问 | 沿用 completed 口径，完成订单数量 6 笔及 HTML 报告 |
| 页面待审核取消 | 取消按钮后持久状态 CANCELLED，active-run=null，卡片消失 |
| 页面删除 | 新建临时空闲会话，经确认删除后从列表消失 |
| PostgreSQL 页面查询 | 联表结果 Alice 199.50、Bob 88.00，HTML 表格正常 |
| Elasticsearch 页面链路 | 有效配置 backend=elasticsearch，真实知识召回后 SQL/报告完成，GMV 11,142.00 元 |
| Milvus 页面链路 | 有效配置 backend=milvus，真实知识召回后 SQL/报告完成，GMV 11,142.00 元 |
| 最终环境恢复 | 8065 恢复原 .env 的 Python 管理库；3001 仍为 Python 预览，Agent 3 页面重开无 console error |

截图：[重启前审核](python-baseline/assets/ticket09-review-before-restart.png)、[重规划](python-baseline/assets/ticket09-review-replanned.png)、[报告](python-baseline/assets/ticket09-browser-report.png)、[追问](python-baseline/assets/ticket09-browser-followup.png)、[PostgreSQL](python-baseline/assets/ticket09-browser-postgres.png)、[Elasticsearch](python-baseline/assets/ticket09-browser-elasticsearch.png)、[Milvus](python-baseline/assets/ticket09-browser-milvus.png)。

联调时 typecheck 重建 .nuxt 曾让开发 manifest 暂时 404；重启 Nuxt 后复查无错误。正常鉴权失败测试中的 401 为预期结果。以上不把测试适配器的受控输出当作真实模型证明，真实供应商与浏览器链路已单列。

### 数据与运行范围

用户未配置 Java 生产数据或 key，因此迁移来源为仓库 SQL 的独立示例副本，并显式复用 Python 已配模型凭据；legacy/bcrypt 使用独立临时测试值。没有对生产存量或未知密文兼容作承诺。

本机隔离验收库、ES/Milvus 命名卷及 data/acceptance 中的报告保留用于复查，凭据和转储均在忽略范围。运行只支持单 worker、本地文件以及 MySQL/PostgreSQL，不新增 OSS 或其他业务数据源。
