# Python 后端平行复刻设计

日期：2026-11-14。状态：讨论结论已确认；根据六项审核意见修订，仅编写设计及任务文档，尚未实现 Python 服务。

## 1. 目标与边界

目标是通过复刻现有项目学习 LangGraph。保留 `JAVA/` 源码及其运行方式，在根目录未来新增 `PYTHON/`，实现可独立运行的 FastAPI + LangGraph 后端。允许切换前端或网关入口；Python 服务不依赖运行中的 Java 服务。

“1:1”指接口和业务行为兼容，不要求类逐一对应、模型回答逐字相同，或直接复用 Java 的序列化状态。最终范围覆盖现有管理业务及 AI 编排，并有以下已确认例外：

| 范围 | 决策 |
| --- | --- |
| 业务数据源 | 仅 MySQL、PostgreSQL；不适配 SQL Server、Oracle、Hive、H2、达梦 |
| Python 分析 | 移除 PythonGenerate、PythonExecute、PythonAnalyze 三个节点和相关工具、路由、状态 |
| 报告 | 保留，直接使用 SQL 结果及上下文 |
| 文件存储 | 仅本地；不适配 OSS |
| 向量检索 | 保留本地、Elasticsearch、Milvus；先本地，后扩展 |
| 旧数据 | 业务表结构保持兼容，可复制业务数据；不共享写库 |
| 旧执行状态 | 不导入 Java checkpoint，不恢复 Java 的在途任务 |
| 部署 | 首版单 worker；不引入多进程事件总线，不自动续跑重启前所有任务 |

完整接口基线见 [接口清单](python-backend-api-inventory.md)，实施顺序见 [任务清单](python-backend-tasks.md)。数据库类型枚举及校验仅开放 MySQL、PostgreSQL；其余类型应明确返回不支持，不能伪装成功。

## 2. 源码依据

源码路径均相对仓库根目录；下列文件所在 Java 包前缀为 `JAVA/data-agent-management/src/main/java/com/alibaba/cloud/ai/dataagent/`。

| 依据 | 用途 |
| --- | --- |
| `controller/` | 14 个 Controller、98 个显式 HTTP 方法映射；不计框架隐式路由 |
| `config/DataAgentConfiguration.java` | 节点、条件边、状态策略及人工反馈中断点 |
| `service/graph/GraphServiceImpl.java` | 图执行、会话、恢复、取消和事件输出 |
| `workflow/node/ReportGeneratorNode.java` | 已直接读取 SQL 执行结果，无需依赖 Python 分析 |
| `workflow/node/PlanExecutorNode.java`、`workflow/dispatcher/` | 工具白名单、计划校验、重试与反馈分支 |
| `config/WebFluxSecurityConfiguration.java`、`security/` | Agent API key 校验及原有鉴权范围 |
| `JAVA/data-agent-management/src/main/resources/sql/schema.sql`、`sql/h2/schema-h2.sql`（同 resources 目录）及 `mapper/` | 联合核对业务表、约束和实际读写；当前两套脚本均有 13 张业务表 |
| `JAVA/data-agent-management/src/main/resources/application.yml` | 管理库、checkpoint、文件及向量默认配置 |
| `JAVA/data-agent-frontend-nuxt/app/services/graph/index.ts` | 图请求参数、SSE 字段及终止处理 |
| `JAVA/data-agent-frontend-nuxt/app/stores/chat.ts` | threadId 复用及人工反馈提交 |
| `service/chat/SessionEventPublisher.java` | 标题更新事件与心跳 |

Java 源码目前是工作区中的事实基线。接口清单保存源码摘要，后续源码改变时应重新核对，不将本次清单当作永久不变的契约。

## 3. 模块与目录

采用模块化单服务。FastAPI 处理 HTTP、参数、鉴权及连接生命周期；应用服务处理普通业务；LangGraph 负责 AI 编排，普通 CRUD 不包装成图节点。

```text
PYTHON/                         # 计划目录；本次不创建实现
  pyproject.toml
  app/
    main.py                     # 应用及资源生命周期
    api/                        # 兼容路由、请求响应 DTO、SSE 编码
    services/                   # 配置、Agent、会话、知识、运行任务
    repositories/               # 业务表访问
    workflow/
      state.py                  # 状态定义及合并策略
      graph.py                  # 图与条件路由
      nodes/                    # 按原有业务职责组织
      events.py                 # 图内事件 → 现有前端事件
    infrastructure/
      models/                   # 动态模型配置、聊天及 embedding 调用
      connectors/               # MySQL、PostgreSQL
      vectorstores/             # 本地、Elasticsearch、Milvus
      checkpoints/              # LangGraph 持久化适配
      files/                    # 本地文件
    resources/prompts/          # 迁移原提示词
  migrations/                   # Python 管理的业务库迁移
  tests/                        # 契约、图场景及必要集成验证
```

依赖版本、ORM、数据库驱动及 checkpoint saver 的具体选择，在实施阶段核对官方兼容性后锁定。本设计不假定特定版本已支持特定 saver，也不为图持久化强制绑定管理库的实现。

## 4. 图编排映射

保留原有节点职责与主要分支。下表中的 Python 名称为建议内部名；对外 `nodeName` 使用原项目实际常量值，由事件适配器映射，不直接暴露内部函数名。

| Java 节点类 | Python 内部节点 | 保留行为 |
| --- | --- | --- |
| IntentRecognitionNode | intent_recognition | 意图分类及非分析请求提前结束 |
| EvidenceRecallNode | evidence_recall | 知识召回 |
| QueryEnhanceNode | query_enhance | 问题增强，条件结束 |
| SchemaRecallNode | schema_recall | Schema 召回，条件结束 |
| TableRelationNode | table_relation | 关系补充及重试 |
| FeasibilityAssessmentNode | feasibility_assessment | 可行性判断及提前结束 |
| PlannerNode | planner | 生成、修复计划；删除 Python 工具说明 |
| PlanExecutorNode | plan_executor | 计划校验、任务调度、修复次数控制 |
| SqlGenerateNode | sql_generate | 生成、修复 SQL 及失败终止 |
| SemanticConsistencyNode | semantic_consistency | 不一致回 SQL 生成，一致进入执行 |
| SqlExecuteNode | sql_execute | 执行结果返回调度，错误回 SQL 修复 |
| ReportGeneratorNode | report_generator | 读取 SQL 结果，流式生成报告后结束 |
| HumanFeedbackNode | human_feedback | 接受回执行，拒绝回规划，保留次数限制 |
| PythonGenerate/Execute/AnalyzeNode | 删除 | 不生成新事件；历史 PYTHON 文本仍允许读取 |

主干是 `意图 → 知识 → 增强 → Schema → 关系 → 可行性 → 规划 → 调度`。调度可进入 SQL 链、报告、人工审核或计划修复。SQL 链为 `生成 → 语义检查 → 执行 → 调度`，包含原有失败分支；不能把所有失败统一处理为无限重试。`nl2sqlOnly` 的分支行为按原实现单独验收。

节点返回结构化状态增量。状态按输入、召回证据、Schema、计划、SQL 结果、反馈、重试计数、最终输出分区；逐项对照 Java 状态键，明确替换或累积策略。大结果集、文件与连接对象不直接塞进 checkpoint：保存可序列化数据或持久化引用，引用内容必须支持恢复时读取。

图事件与图状态分离，LLM 文本分片、节点输出、最终回答和中断信号通过统一适配层进入 SSE，避免把所有 LangGraph 内部事件直接发送到前端。

### 删除 Python 后的能力出口

可行性检查与规划器只能选择现有 SQL 查询及报告能力。对必须依赖被删除执行能力、且当前 SQL 无法可靠完成的任务，返回明确的能力限制说明并结束，不编造分析或预测结果。是否支持以实际数据源 SQL 能力判断，不把所有统计任务一律判为不支持。

规划器生成未知工具时，允许在既定计划修复预算内重新规划；仍然包含不支持工具则结束，不能无限循环。能力不足属于业务结果：输出 `FINAL_ANSWER`（说明缺少的能力和可支持的查询替代方案），再发 `complete`，不进入报告生成以虚构结论。执行异常仍走 `error`。

默认提示词和导入、编辑、启用的自定义提示词均纳入迁移检查。发现 Python 工具指令时给出问题位置并禁止激活该配置，保留原文供修订；运行时工具白名单仍强制校验，不能依赖关键词扫描保证正确性。验收包含一个经测试确定必须依赖外部 Python 预测库的案例，确认有限步数内说明限制且没有伪造结果。

## 5. 接口及事件兼容

普通接口逐项兼容方法、路径、参数位置、别名、默认值、必填性、响应包裹、状态码、分页、空值、日期和错误结构。不能让 FastAPI 默认校验错误自动代替原接口契约。上传需兼容 multipart 字段，下载需核对 MIME、文件名及响应头。

### 图执行 SSE

- `GET /api/stream/search`：保留 `agentId`、`conversationId`、`threadId`、`query`、`humanFeedback`、`humanFeedbackContent`、`rejectedPlan`、`nl2sqlOnly`。
- 普通 `message` 数据字段：`agentId, threadId, eventType, stepId, attempt, nodeName, textType, text, error, complete`。
- `eventType` 保留 `NODE_OUTPUT`、`FINAL_ANSWER`、`HUMAN_FEEDBACK_REQUIRED`。
- `textType` 保留 `JSON, SQL, HTML, MARK_DOWN, RESULT_SET, TEXT`；历史 `PYTHON` 只保留读兼容。
- 保留显式 `event: complete` 和 `event: error`；错误内容兼容前端读取 JSON 的 `text`。不能仅靠关闭连接表示成功。
- 空文本的状态事件不能被过滤；`stepId` 区分节点执行，`attempt` 区分同名节点重复运行，验收时检查事件顺序及终止事件唯一性。
- `POST /api/stream/stop` 保留 conversationId 及可选 threadId；原成功响应为 204。支持按任务或会话取消，断连也触发对应运行取消。

### 标题更新 SSE

保留 `GET /api/agent/{agentId}/sessions/stream`，发送 `event: title-updated` 和 `{type: "title-updated", sessionId, title}`；保留约两秒的 heartbeat comment，避免将心跳误作业务消息。

鉴权凭据沿用 X-API-Key 或 Bearer，不另建用户或租户体系。已核实原前端 EventSource 没有传 key，Java 仅保护 search；Python 模式明确改用带凭据头的 fetch SSE，补齐 search、stop、标题 SSE、审核摘要及结果查询的当前 key 和资源归属校验。stop 增加必填 agentId 是显式兼容差异；Java 源码保持原样。具体鉴权矩阵、401/404 规则、内存凭据输入及禁止自动重试执行 GET 见 spec。API key 编码及数据库密文须在导入时验证。

### 刷新页面后找回审核任务（兼容扩展）

保留原 98 个 HTTP 映射，额外增加 Python 接口 `GET /api/sessions/{sessionId}/active-run`。前端进入会话时，在加载历史之后调用；没有占用返回 200 与 `null`，有占用返回以下运行摘要：

```json
{
  "agentId": "1", "conversationId": "session-id", "threadId": "run-id",
  "status": "WAITING_FEEDBACK", "planRevision": 2,
  "plan": {}, "resumeRequest": {
    "query": "原始问题", "humanFeedback": true, "nl2sqlOnly": false
  }, "recoverable": true
}
```

`plan` 使用现有计划业务结构，`resumeRequest` 不含密钥；上述字段来自持久化运行记录，不能依赖前端内存或重新调用模型生成计划。接口按所属 Agent 的 API key 鉴权并验证会话归属，防止跨 Agent 找回或恢复。

前端恢复 `lastRequest`（含摘要中的 Agent、会话、threadId）、计划及审核状态，复用现有反馈提交路径；增加可选查询参数 `feedbackRevision`，适配后的前端每次反馈必须携带版本。HUMAN_FEEDBACK_REQUIRED 必须增加 planRevision 和完整 plan，与 threadId 绑定同一持久化审核版本；新卡片与刷新恢复均保存这一组数据，不能点击批准时查询最新版再套用到旧卡片。版本不匹配拒绝恢复；无版本旧客户端只允许首次审核、无重规划的兼容情况，后续要求刷新升级客户端。

仅 `WAITING_FEEDBACK` 且持久化中断可用时显示审核按钮。`RUNNING`、`RESUMING`、`CANCELLING`、`RECOVERY_REQUIRED` 显示占用状态，禁止新问题；不补发完整 token 流。停止可取消待审核任务。Python 前端还需凭据传递、最终结果找回及只读状态轮询，使用 Java 后端时不启用这些扩展，不修改 Java 源码。

## 6. 持久化与任务生命周期

### 6.1 数据库迁移基线

管理库使用独立 MySQL 数据库。当前 MySQL `schema.sql` 和 H2 `schema-h2.sql` 均有以下 13 张业务表；MySQL 脚本的 `agent_datasource_tables` 在第 232 行使用小写 `create table`，不能用区分大小写的统计得出缺表结论。审核提出的迁移核对要求保留，但不修改 Java SQL 去补一张已存在的表。

| 业务表 | 迁移核对重点 |
| --- | --- |
| agent | Agent 配置、发布状态、API key 字段 |
| business_knowledge | 业务知识及召回配置 |
| semantic_model | 语义模型及启用配置 |
| agent_knowledge | 知识文件及索引状态 |
| datasource | 连接参数及凭据编码 |
| logical_relation | 逻辑关系及列映射 |
| agent_datasource | Agent 与数据源绑定 |
| agent_datasource_tables | 选表记录；绑定 ID＋表名唯一约束，外键及级联规则 |
| agent_preset_question | 预设问题 |
| chat_session | 会话归属、状态、置顶及标题 |
| chat_message | 展示历史及 metadata |
| user_prompt_config | 提示词、启用、优先级及顺序 |
| model_config | 模型 provider、类型及激活配置 |

迁移以 MySQL 字段为主体，对照 H2、实体和 Mapper 列出字段、索引、外键、默认值及初始化数据差异，明确处理方言，不直接拼接两份脚本。必须在空库验证 Agent 绑定与选表、解绑级联，并在复制数据上检查约束。MySQL 管理库与查询的 MySQL/PostgreSQL 业务数据源属于不同连接配置，不能混用。

Spring AI JDBC chat memory 表、Java saver 自动建表单列盘点，不算入上述 13 张业务表。Python 不直接读取这些框架序列化表，模型记忆需转换导入或明确重建；checkpoint 不导入。Python 另建以下内部表，由自己的迁移管理，不能宣称只迁移 13 张表就可运行：

| 计划表 | 关键数据与约束 |
| --- | --- |
| agent_run | 唯一 threadId、Agent/会话、原请求快照、状态、planRevision、计划、配置快照、最终结果引用、checkpoint 引用、状态 version、执行 owner、错误与时间 |
| agent_session_runtime | `(agent_id, conversation_id)` 主键及 active_thread_id；每会话唯一持久化占用 |
| agent_conversation_turn | `(agent_id, conversation_id, thread_id)` 唯一；问题、当前计划版本、记忆提交状态及顺序 |
| graph_effect | `(thread_id, effect_key)` 唯一；副作用阶段、持久化结果引用与提交状态 |
| agent_run_result | 唯一 threadId；最终回答、报告/数据引用、结局、结果版本和稳定消息键 |

checkpoint saver 自身所需表单列迁移与版本，不与运行表或副作用表混为一谈。

### 6.2 运行标识与审核恢复

LangGraph checkpoint 使用独立表或独立存储命名空间，不覆盖 Java saver 表。checkpoint 按图运行标识保存；`conversationId` 是聊天会话，`threadId` 是一次可恢复图运行。新问题产生新运行，人工反馈复用原 threadId；读取及恢复需校验 Agent 与会话归属。

人工审核使用持久化 `interrupt` 及恢复机制：先完成持久化，再发布 `HUMAN_FEEDBACK_REQUIRED` 并正常结束当前流。再次请求根据反馈恢复同一图运行，不能重跑全部前置节点。接受继续调度，拒绝携带意见回到规划。中断前后的节点副作用要考虑重入，不能因恢复重复执行 SQL、重复写历史消息。

运行记录保存原请求、计划与版本，恢复摘要接口负责刷新页面后的找回。不能仅测试“浏览器不刷新、服务重启”。运行状态包括 `CREATED → RUNNING → WAITING_FEEDBACK → RESUMING → RUNNING`，以及终态 `COMPLETED / FAILED / CANCELLED`；取消经过 `CANCELLING`，不确定的恢复经过 `RECOVERY_REQUIRED`。待审核和上述中间状态均占用会话。

### 6.3 会话并发、Redis 与状态转换

采用审核建议的 Redis 短锁＋MySQL 持久化运行状态；首版仍单 worker，不引入 Redis 事件总线。锁粒度是 `agentId + conversationId`，不是 threadId。同一会话只允许一个未结束运行，待审核也算未结束；新问题拒绝，不自动替换旧任务。不同会话可并行。

1. 新问题：获取短锁后，在 MySQL 事务中锁定会话占用行，确认没有 active_thread_id，创建运行并占用会话，提交后释放短锁。并发初始化依赖占用表主键及事务约束防重。
2. 待审核：先持久化 checkpoint，再按版本条件更新运行、计划与 WAITING_FEEDBACK 状态；保留占用，释放所有短锁，不在用户思考期间续租 Redis 锁。
3. 反馈：取得同一会话锁，检查归属、threadId、planRevision、checkpoint，条件更新 `WAITING_FEEDBACK → RESUMING`。只有成功更新的请求可续跑。进入执行时推进 RUNNING；重复或过期反馈不启动新执行。
4. 完成或取消：先确认实际执行停止、记忆与结果提交完成，再在 MySQL 事务中写终态，并仅当 active_thread_id 仍指向自己时清空占用。待审核取消不重新执行图。

Redis 获取锁采用 `SET key token NX PX ttl`，释放或续期用 Lua 比较 owner token 后删除或更新 TTL；不得直接 DEL。锁失效或续期失败后停止发起新的状态变更，重新获取并读取数据库版本。Redis 不可用时拒绝新的创建/恢复，不静默退化为无锁执行；已有运行保留持久化占用。

Redis、MySQL、checkpoint 不能组成一个原子事务。MySQL 行锁、version 条件更新及唯一约束是最终防线；即便锁过期，旧请求也必须校验状态、版本与 owner。锁过期、心跳过期都不能作为任务已停止的证据；不自动夺取仍可能在执行的任务。

服务启动先对运行记录、效果记录与 checkpoint 做对账，再接收对应会话的新任务：确认旧执行停止且版本一致的持久化中断恢复为 WAITING_FEEDBACK；有已提交结束结果则补写终态；其他情况进入 RECOVERY_REQUIRED 并继续占用。提供本机 CLI inspect 与 resolve-failed：查看原因及数据库查询标识，在确认旧 worker/任务和数据库执行均已停止后，按预期 version 失败收尾、持久化失败结果、丢弃暂存记忆并释放自身占用。证据不足拒绝操作，锁过期不算停止证据；不确定 SQL 不重发，不提供人工强制续跑。操作幂等且记录操作者、原因及证据，具体条件见 spec。RESUMING 期间崩溃同样对账。

普通 JSON 请求的占用冲突返回 409、Redis 暂不可用返回 503；图 SSE 为保留现有事件协议，鉴权和参数校验后，以 `error` 事件的 `text` 给出会话忙、过期反馈或暂不可用原因并终止，不再发成功 complete。身份错误在建流前返回 HTTP 错误。这是新增并发规则的显式兼容补充。

### 6.4 展示历史、模型记忆与 checkpoint 的归属

| 数据 | 保存内容 | 唯一写入归属 |
| --- | --- | --- |
| chat_message | 用户文本、时间线、最终回答及展示 metadata | 保留前端调用消息保存接口；图节点不重复插入展示消息 |
| agent_conversation_turn | 会话级用户问题＋当前有效规划结果，按轮次组织 | 后端记忆服务；按 threadId 更新，不从展示 HTML 拼上下文 |
| LangGraph checkpoint | 单次运行的状态、分支、计数及中断位置 | saver；不是跨轮聊天记忆，也不是展示消息库 |
| agent_run | 请求、执行状态、待审核计划、版本、配置快照及归属 | 运行服务；为前端重建审核状态提供依据 |
| agent_run_result | 最终回答、报告/数据引用、结果版本、结局与稳定消息键 | 后端结果服务；不依赖浏览器保存展示历史 |

Java 的 MultiTurnContextManager 以“用户问题＋规划结果”构造上下文。Python 保留内容语义及原有长度/窗口配置，按 Agent＋conversationId 读取跨轮记忆，新 threadId 不会丢失上下文。当前轮计划存为可恢复的暂存记录，拒绝时替换同一轮的计划版本，不把旧计划和新计划重复追加；成功完成才提交给后续轮次，取消、失败或能力不足丢弃本轮暂存，保留以前成功轮次。这是明确的提交时机约定，避免失败计划污染追问。

消息保存接口增加可选 metadata 幂等键，由适配后的前端对同一次逻辑保存生成稳定键，重试复用；后端以会话＋幂等键返回原消息。旧客户端不携带键时保持旧保存行为，不承诺去重。审核摘要仅重建审核卡片，不把历史消息重新保存一遍；无前端在线时运行状态与记忆仍由后端可靠保存。

最终结果相关消息键以服务器快照分配的 threadId＋结果种类＋序号为准，在线保存和断线补存必须复用。新增只读运行列表 `GET /api/sessions/{sessionId}/runs` 和详情 `GET /api/sessions/{sessionId}/runs/{threadId}`，即使 active-run 已为 null 且浏览器没有保存 threadId，仍可分页发现终态并查询完整最终结果。结果文件先持久化，最终快照、记忆结局、终态和占用释放再提交，最后发布最终回答/complete。前端进入会话、保存失败或流异常后补查，按稳定键合并；进行中的运行只读轮询，不自动重试执行。结果未删除前保留，不等同完整 token 回放。

### 6.5 持久化前置与节点重入

阶段 0 就锁定 saver、状态序列化、运行标识、effect_key 规则及写入归属；阶段 1 必须跑过一次最小持久化中断/进程重启/恢复验证，阶段 3 才扩展完整审核交互，而不是首次引入持久化。

包含 `interrupt()` 的节点恢复时会从节点开头重新执行，因此审核节点的中断前段只做可重复的读取/计划构造；不能在这里执行 SQL 或追加历史。其他副作用使用稳定业务键，不能用每次重入新生成的随机 ID 去重。`graph_effect` 保存已完成结果引用以便复用；写运行表、记忆和内部效果记录尽量处于同一 MySQL 事务。

跨数据库查询与效果记录不存在原子提交保证：崩溃发生在 SQL 返回但结果未保存的窗口时，标记不确定并走对账，不宣称 exactly-once，不自动重发可能有副作用的 SQL。检查点引用、查询结果、节点效果必须按版本关联，待审核状态只能对外发布已确认可恢复的 checkpoint。

停止、断连、模型或 SQL 错误应释放资源并区分完成、失败、取消、等待反馈。取消 Python 协程不等于数据库查询必然被中止；连接器需验证超时和取消行为。服务重启后可恢复已持久化的待审核任务，不承诺自动重启所有运行任务。

知识正文、召回配置和向量索引分开管理；Java 本地向量文件不直接复用，使用对应 embedding 配置重新建索引。默认本地存储需覆盖原检索及持久化能力；Elasticsearch、Milvus 放在后续阶段，但仍属于最终范围。文件与报告只使用 Python 自己的本地目录。

### 6.6 删除与配置变更

单会话删除、批量清空会话、Agent 删除遇目标范围内任一非终态运行均整次返回 409，无部分删除；先停止或经 CLI 失败收尾，再重试删除。Agent/会话持久化生命周期闸门按固定锁顺序与创建/恢复互斥；事务检查占用，设置删除标记以阻止新运行及晚到消息。终态运行、结果、模型记忆和展示消息随归属清理；checkpoint/文件/效果数据由持久化清理任务可重试删除，共享文件须确认无其他引用。崩溃后继续清理，不能通过晚到回调重建已删除会话。

运行和审核计划保存不含明文密钥的配置快照/指纹，包含数据源身份/目标、绑定/选表、逻辑关系、语义/召回、提示词、模型与索引版本。恢复及新的模型/SQL 操作前重新校验当前 key、权限及快照；影响计划的变化使旧批准失效，确认无在途操作后以 CONFIG_CHANGED 失败收尾并提示重新提问，不自动应用原反馈到新计划。纯标题/头像更新不影响；凭据轮换可使用当前凭据，但不绕过当前认证。已发出的操作按停止和不确定执行规则处理。

以上扩展的字段、鉴权、状态条件及验收以 [spec](python-backend-spec.md) 为准，属于明确的兼容差异，不计入原 98 个 Java 映射。

## 7. 验收原则与实施待核对项

普通 API 使用固定输入对比契约及数据变化；图流程使用可控模型输出验证分支，再以真实模型和数据库联调。LLM 自由文本不作逐字比较，但 SQL 结果、结构化计划、事件语义、人工反馈恢复和失败终止必须可核验。

实现前逐阶段核对 DTO、错误码、模型 provider、文件解析格式、检索参数、prompt 优先级、重试上限、API key 编码和数据库凭据。记忆归属与提交规则已在 6.4 节确定；具体存量数据转换仍需验证。新增审核查询、版本参数及前端适配作为兼容扩展单独验收；原有 98 个接口基线数量不改成 99 个 Java 接口。

最终切换前端入口前，按接口清单逐项记录通过、未通过及明确排除项；不能用占位响应、空列表或仅注册路由代替业务完成。没有对应环境的外部向量库验证明确记为未验证。

## 8. 六项审核意见的落实

| 审核问题 | 修订位置 | 必须提供的验收证据 |
| --- | --- | --- |
| 数据库基线遗漏风险 | 6.1：纠正大小写漏计，完整表清单及框架/新增表分账 | 两套 DDL 与 Mapper 核对、空库建表及选表级联验证 |
| 刷新后无法找回审核任务 | 第 5 节扩展接口、6.2 | 后端重启＋页面刷新＋重新进入会话后接受/拒绝 |
| 会话并发 | 6.3：Redis＋Lua 短锁、DB 占用与条件迁移 | 双标签页、待审核新问题、重复反馈、锁过期及崩溃对账 |
| 历史/记忆/checkpoint 混淆 | 6.4 | 追问、拒绝后重规划、消息重试与失败轮次隔离 |
| 删除 Python 后缺出口 | 第 4 节能力出口 | 默认/自定义 prompt 校验，能力不足案例有限步结束 |
| 持久化引入过晚 | 6.5、任务阶段 0/1 | 最小重启恢复、节点重入及副作用去重证据 |

执行语义依据：[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)；锁及脚本边界依据：[Redis 锁文档](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)、[Lua 脚本文档](https://redis.io/docs/latest/develop/programmability/eval-intro/)。具体 API 及依赖版本实施时锁定，本次没有运行实现测试。
