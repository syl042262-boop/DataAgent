# FastAPI + LangGraph 独立后端平行复刻 Spec

日期：2026-11-14。基线：讨论结论、设计审核修订及本次 spec 六项审查修订。设计基线 Git `cb6af20`，首版 spec `da553ed`。本文件定义待实现的需求与验收，未开始实现 Python 服务。主测试边界已由用户确认，本次增加相应的故障与协议验收场景。

## Problem Statement

用户希望通过复刻现有 DataAgent 后端学习 LangGraph，能够对照已有业务理解图状态、节点、条件分支、流式事件、持久化中断和恢复。现有 Java 后端包含管理业务、自然语言查询、知识召回、规划、SQL 执行、报告及人工审核，单独实现一个简化 NL2SQL 示例不足以满足学习目标。

用户需要保留 Java 源码和原运行方式，在可独立运行的 Python 后端中获得兼容的接口与业务行为，能够使用现有前端验证完整流程。复刻还必须解决页面刷新后找回审核任务、同一会话重复执行、跨轮记忆丢失和恢复时重复副作用等问题，不能仅依赖浏览器或服务进程内存维持正确性。

## Solution

新增独立的 FastAPI + LangGraph 模块化单服务。FastAPI 承担兼容接口、参数、鉴权和 SSE；普通应用服务承担配置与管理业务；LangGraph 承担 AI 工作流。Python 使用独立管理数据库、本地文件目录和图持久化存储，无需启动 Java 服务。

以现有前端可观察到的接口、事件及业务效果作为“1:1”兼容标准，覆盖原 14 类 Controller 的 98 个显式 HTTP 映射。保留主要图分支、SQL 检查修复、报告和人工反馈；明确移除 Python 代码生成、沙箱执行和分析链路。业务数据源仅支持 MySQL、PostgreSQL，文件仅本地，向量后端保留本地、Elasticsearch、Milvus。

通过会话级持久化占用、Redis 短锁、计划版本与可恢复 checkpoint 支持可靠审核；增加审核运行摘要查询，使后端重启且页面刷新后仍能恢复原任务。分阶段交付可运行闭环，最终按完整范围验收。

## User Stories

1. As an 学习 LangGraph 的开发者, I want a 可独立运行的 Python 后端, so that 我能直接理解请求到图执行的全过程。
2. As an 项目维护者, I want a 保留 Java 源码与原运行方式的平行实现, so that 我能随时对照或切回原后端。
3. As an 前端使用者, I want a 兼容现有请求与响应的服务入口, so that 切换后仍能完成已有业务操作。
4. As an 学习 LangGraph 的开发者, I want a 按闭环分阶段交付的实现, so that 每阶段都能运行并观察新增能力。
5. As an 管理员, I want a 模型配置及激活能力, so that 聊天和 embedding 使用正确的配置。
6. As an 管理员, I want a Agent 配置与发布管理能力, so that 可以创建并使用不同的数据分析助手。
7. As an Agent 管理员, I want a 兼容原机制的 API key 管理与鉴权能力, so that 原有受保护入口继续校验访问凭据。
8. As an 数据管理员, I want a MySQL 与 PostgreSQL 数据源配置及连接测试能力, so that 能确认真实数据库可用。
9. As an 数据管理员, I want a 表与列元数据查询能力, so that 能核对查询所依据的 Schema。
10. As an Agent 管理员, I want a 数据源绑定及选表能力, so that Agent 只使用配置允许的表。
11. As an 数据管理员, I want a 逻辑关系及列映射管理能力, so that 查询能够使用必要的表间关系。
12. As an Agent 管理员, I want a 预设问题管理能力, so that 用户能够从已有问题开始查询。
13. As an 知识管理员, I want a 业务知识维护与召回配置能力, so that 查询能理解业务术语和规则。
14. As an 知识管理员, I want a 语义模型维护及批量导入能力, so that 能按原有方式管理业务语义。
15. As an 知识管理员, I want a Excel 模板下载和导入能力, so that 可以继续使用既有数据维护流程。
16. As an 知识管理员, I want a 知识文件上传、索引及失败重试能力, so that 文档能真正参与检索。
17. As an 知识管理员, I want a 本地向量索引的持久化及增删改检索能力, so that 重启后知识仍然可用。
18. As an 部署维护者, I want a Elasticsearch 与 Milvus 可选检索后端, so that 最终覆盖已确认的向量存储范围。
19. As an 管理员, I want a 保留启用规则和优先级的提示词配置能力, so that 自定义配置继续按原语义生效。
20. As an 管理员, I want a 对已移除 Python 工具指令的配置检查结果, so that 能修改不兼容提示词后再激活。
21. As an 数据分析用户, I want a 自然语言查询入口, so that 能从真实业务数据得到 SQL 和查询结果。
22. As an 数据分析用户, I want a 意图识别与明确的提前结束结果, so that 非分析请求不会进入无意义执行。
23. As an 数据分析用户, I want a 知识、Schema 和关系召回能力, so that 生成的查询有可核对的数据依据。
24. As an 数据分析用户, I want a 可行性判断和结构化执行计划, so that 知道服务准备如何完成问题。
25. As an 数据分析用户, I want a 有限次数的计划修复, so that 错误计划可以纠正且不会无限循环。
26. As an 数据分析用户, I want a SQL 生成、语义检查和执行错误修复能力, so that 查询失败时有明确处理路径。
27. As an 数据分析用户, I want a 达到重试上限后的明确终止结果, so that 能理解失败原因而不无限等待。
28. As an 数据分析用户, I want a 保留原语义的 nl2sqlOnly 模式, so that 可以使用已有的查询模式。
29. As an 数据分析用户, I want a 根据真实 SQL 结果生成的流式报告, so that 能阅读并下载有数据依据的分析。
30. As an 数据分析用户, I want a 能力不足时的明确说明与可支持查询建议, so that 不会把虚构的预测当成真实分析。
31. As an 数据分析用户, I want a 包含节点身份和尝试次数的进度时间线, so that 能区分节点重试与重复消息。
32. As an 前端使用者, I want a 明确的完成和错误事件, so that 页面能可靠结束等待并呈现结果。
33. As an 数据分析用户, I want a 创建、列表、置顶、改名和删除会话的能力, so that 能管理自己的历史分析。
34. As an 数据分析用户, I want a 会话标题实时更新能力, so that 侧边栏能及时反映本次问题。
35. As an 数据分析用户, I want a 重开会话时可读取的历史消息和报告, so that 能回顾之前的查询。
36. As an 数据分析用户, I want a 跨运行保留的成功轮次上下文, so that 下一条追问能延续原问题。
37. As an 计划审核者, I want a 执行前可查看的持久化计划, so that 可以决定是否接受。
38. As an 计划审核者, I want a 接受后恢复同一图运行的能力, so that 无需重新执行全部前置步骤。
39. As an 计划审核者, I want a 拒绝时附带意见并重新规划的能力, so that 新计划能反映我的要求。
40. As an 计划审核者, I want a 后端重启且页面刷新后仍可找回的审核任务, so that 不会失去等待审核的计划。
41. As an 计划审核者, I want a 审核计划版本校验, so that 旧页面不能误批准新计划。
42. As an 数据分析用户, I want a 同一会话只执行一个未结束任务的规则, so that 双标签页不会产生相互覆盖的执行。
43. As an 数据分析用户, I want a 待审核期间的新问题被明确拒绝, so that 原任务不会被静默替换。
44. As an 计划审核者, I want a 重复点击反馈只触发一次恢复的行为, so that 不会重复执行查询。
45. As an 数据分析用户, I want a 不同会话可以并行运行的能力, so that 一个待审核任务不阻塞其他会话。
46. As an 数据分析用户, I want a 按任务或会话停止运行的能力, so that 能取消不再需要的工作。
47. As an 计划审核者, I want a 取消待审核任务的能力, so that 结束等待时无需先批准执行。
48. As an 数据分析用户, I want a 连接断开及执行异常后的资源清理, so that 不会留下无法管理的后台任务。
49. As an 数据分析用户, I want a 失败、取消或能力不足轮次不进入后续模型记忆的规则, so that 追问不会受无效计划影响。
50. As an 数据分析用户, I want a 消息保存重试可复用的幂等标识, so that 相同逻辑消息不会反复出现在历史中。
51. As an 项目维护者, I want a 展示历史、跨轮记忆和图 checkpoint 的明确归属, so that 恢复和消息保存不会互相重复写入。
52. As an 项目维护者, I want a 崩溃后可对账的运行状态, so that 不确定执行不会被静默重跑。
53. As an 部署维护者, I want a Redis 不可用时明确拒绝新建及恢复任务的行为, so that 不会在失去协调能力时并发执行。
54. As an 项目维护者, I want a 锁过期时仍由持久化状态约束执行的机制, so that 超时不会自动授权第二个运行。
55. As an 数据迁移维护者, I want a 完整的业务表和新增内部表迁移清单, so that 能在空库建立可运行服务。
56. As an 数据迁移维护者, I want a Java 业务数据复制及凭据检查流程, so that 能复用业务配置并发现不可直接迁移的数据。
57. As an 数据迁移维护者, I want a 向量重建和历史 Python 文本读兼容能力, so that 可保留历史内容而不恢复已删除执行能力。
58. As an 前端使用者, I want a 头像、知识文件和报告的本地上传读取能力, so that 已有文件操作继续可用。
59. As an 验收者, I want a 每个接口的契约和真实业务效果记录, so that 不会把占位响应当成功能完成。
60. As an 学习 LangGraph 的开发者, I want a 图状态说明、节点映射和实际运行轨迹, so that 能把实现与原 Java 行为对照学习。
61. As an 启用 API key 的 Agent 使用者, I want a 携带请求头凭据的查询、审核及停止能力, so that 受保护流程可在 Python 模式下完整使用。
62. As an 计划审核者, I want a 与当前卡片绑定的计划版本, so that 批准操作不会作用于另一份计划。
63. As an 部署维护者, I want a 查看不确定运行及安全失败收尾的本机命令, so that 故障处理后会话能够重新使用。
64. As an 数据分析用户, I want a 不依赖前端保存成功的最终结果快照, so that 完成后刷新页面仍可找回回答和报告。
65. As an 管理员, I want a 删除与运行互斥的明确规则, so that 清理会话或 Agent 不会留下继续写入的后台任务。
66. As an 计划审核者, I want a 配置变化后旧计划失效的提示, so that 批准的计划不会静默改用新的数据源或权限。

## Implementation Decisions

### 架构与范围

- 采用一个模块化单服务，首版单 worker。模块包括兼容 API 与 SSE、应用服务、业务仓储、图编排、模型适配、SQL 连接器、向量检索、本地文件及 checkpoint。CRUD 使用普通服务，不包装成图节点。
- 保留 Java 源码及运行方式，允许前端或网关切换入口。Python 的运行、管理库、文件与索引均独立；不依赖运行中的 Java 服务，不共用写库。
- 最终覆盖原 98 个 HTTP 映射；审核找回、结果查询、并发、删除保护及运行接口鉴权属于显式兼容差异，单独验收。兼容定义包括业务效果，不要求类一一对应或模型自由文本逐字一致。Python 模式需要下述前端适配，不能承诺仅切换入口即可覆盖所有增强行为。
- 具体依赖版本、ORM、驱动与 saver 在实施时核对官方兼容性并锁定，本 spec 不预设尚未验证的实现选型。

### 图与能力出口

- 保留意图识别、知识召回、问题增强、Schema 召回、表关系、可行性检查、规划、执行调度、SQL 生成、语义一致性、SQL 执行、报告与人工反馈职责。主干到调度后，按原语义进入 SQL、报告、审核或计划修复。
- SQL 链保持生成、语义检查、执行及返回调度；保留提前结束、语义不一致回生成、执行失败修复及各自重试上限。nl2sqlOnly 按原实现单独核对，不等同于任意简化主图。
- 删除 PythonGenerate、PythonExecute、PythonAnalyze 节点及相关工具、路由和状态。规划器、可行性检查与运行时工具白名单必须一致，不生成新的 Python 执行事件；历史 PYTHON 文本保留读取能力。
- 报告节点直接使用 SQL 结果与上下文，保留 HTML 流式展示及下载。必须依赖已移除能力、且当前 SQL 无法可靠完成的请求，输出能力限制及可支持的查询替代方案，以 FINAL_ANSWER 后 complete 结束，不生成虚构报告。执行异常走 error。
- 未知工具只允许在原计划修复预算内纠正，超限结束。默认、自定义、导入及编辑的提示词均检查工具兼容性；发现 Python 工具指令时标明问题并禁止激活，保留原文供修订。运行时校验不能仅依赖文本关键词检查。
- 提示词先迁移原内容、启用规则、优先级与输出约定，仅调整图消息组织和删除工具说明。模型 provider、解析格式、检索参数和具体重试值由源码提取后固化到契约。
- 节点返回结构化增量；状态区分输入、证据、Schema、计划、SQL 结果、反馈、计数和最终输出，各字段明确替换或累积语义。checkpoint 只保存可序列化数据或可在恢复时读取的持久化引用。

### HTTP、事件与鉴权

- 普通接口兼容方法、URL、参数位置、别名、默认值、必填性、响应包裹、状态码、分页、日期、空值和错误格式；不得直接用 FastAPI 默认校验错误替代旧契约。multipart 字段及下载 MIME、文件名、响应头均纳入核对。
- 图入口保留 `GET /api/stream/search` 及 agentId、conversationId、threadId、query、humanFeedback、humanFeedbackContent、rejectedPlan、nl2sqlOnly 参数。
- 统一事件适配层将图状态输出与模型分片映射成既有 SSE；不透传全部 LangGraph 内部事件。普通 message 保留 agentId、threadId、eventType、stepId、attempt、nodeName、textType、text、error、complete。HUMAN_FEEDBACK_REQUIRED 额外必须携带 planRevision 和完整结构化 plan，与 threadId 一起取自同一次持久化审核状态。nodeName 使用原对外常量，stepId 标识单次节点执行，attempt 区分重复运行。
- eventType 保留 NODE_OUTPUT、FINAL_ANSWER、HUMAN_FEEDBACK_REQUIRED；新输出 textType 保留 JSON、SQL、HTML、MARK_DOWN、RESULT_SET、TEXT。空文本状态事件不能被过滤。保留显式 `event: complete`、`event: error`，错误 JSON 的 text 可被前端读取；不能仅关闭连接表示成功，同一流不重复发终止事件。
- 停止入口保留 `POST /api/stream/stop`，按 conversationId 及可选 threadId 取消，成功状态 204。断连取消对应运行，但已持久化并正常结束流的待审核状态不能被误判为断连取消。
- 标题 SSE 保留 `GET /api/agent/{agentId}/sessions/stream`，事件名 title-updated，数据包含 type、sessionId、title，并保留约两秒一次的 heartbeat comment。
- 延续 Agent API key 凭据格式：X-API-Key 优先，其次 Authorization Bearer；使用 Agent 当前的 apiKeyEnabled 及有效 key 校验。Python 模式前端使用可设置请求头的 fetch 流式 SSE 客户端，按 SSE 帧边界解析，支持 AbortController、显式 complete/error 及停止；标题流同样携带凭据。禁止把 key 放入 URL 或持久化运行请求，前端凭据由使用者输入并仅保存在内存，刷新后缺凭据时先重新输入再找回状态；不通过公开 Agent 配置响应获得原始 key。Java 模式沿用原调用方式。
- 启用 key 时缺失/无效凭据返回 401；未启用时仍校验 Agent 存在及请求资源归属。认证后，跨 Agent 会话或运行按 404 处理，避免泄漏资源；Agent key 并不构成新增用户身份或租户隔离体系。运行入口的鉴权矩阵如下，未列管理接口仍按原契约，不宣称全站鉴权已补齐。API key 编码和数据库密文须实际验证可迁移性。

| 运行入口 | Agent 解析 | 校验与兼容差异 |
| --- | --- | --- |
| search（新问题及反馈恢复） | 原 agentId 参数 | 当前 key 校验，会话与运行归属；恢复额外校验计划版本和配置 |
| active-run、运行列表与结果详情 | sessionId 所属 Agent；可选 agentId 必须匹配 | 当前 key 校验及会话/运行归属 |
| stop | Python 模式增加必填 agentId，保留 conversationId 与可选 threadId | 当前 key 校验；同时提供的标识必须指向同一会话与 Agent；跨归属不得取消。该参数及鉴权为显式差异，成功仍为 204 |
| 标题 SSE | 路径 agentId | 当前 key 校验，不向其他 Agent 推送；这是原未保护入口的显式增强 |

- Python 模式不自动重连会产生执行的新问题/反馈 GET，不因网络失败自动新建运行；刷新或断线后只用只读摘要和结果接口找回状态。跨域部署允许所需凭据头及预检，凭据错误在流开始前返回 HTTP 错误，前端明确呈现。

### 数据与存储

- 管理库使用独立 MySQL，与 MySQL/PostgreSQL 业务查询连接配置分开。业务数据源枚举仅开放这两类，其余明确返回不支持。
- 业务迁移基线为 13 张表：agent、business_knowledge、semantic_model、agent_knowledge、datasource、logical_relation、agent_datasource、agent_datasource_tables、agent_preset_question、chat_session、chat_message、user_prompt_config、model_config。对照 MySQL/H2 DDL、实体及 Mapper 核对字段、索引、外键、默认值和初始化数据，不能区分建表关键字大小写统计表数。
- 保留数据源绑定选表唯一性、外键及解绑级联；处理两套方言差异。H2 只作原迁移基线参考，不成为 Python 支持的数据源或管理库。
- 新增内部持久化模型：agent_run 保存唯一 threadId、归属、请求、状态、计划及 planRevision、checkpoint 引用、version、owner、配置快照、最终结果引用、错误与时间；agent_session_runtime 以 Agent＋conversationId 唯一保存 active_thread_id；agent_conversation_turn 以 Agent＋会话＋threadId 唯一保存问题、计划版本及记忆提交状态；graph_effect 以 threadId＋effect_key 唯一保存副作用阶段、提交状态及结果引用。
- agent_run_result 按 threadId 唯一持久化最终快照，保存结果版本、结局类型、最终回答、报告及 SQL 结果引用、错误/取消说明、稳定消息键和展示所需类型。大文件先持久化且验证可读，再提交引用；不可读的结果不能被声明成功。清理规则与会话/Agent 删除一起定义。
- saver 所需表单列迁移和版本管理，不与业务表混计。Java chat memory 与 saver 自动建表单独盘点，不直接读取其框架序列化数据；模型记忆转换导入或明确重建，Java checkpoint 不导入。
- 知识正文、召回配置、向量索引分别管理。向量后端先实现本地，最终覆盖 Elasticsearch、Milvus；使用对应 embedding 配置重建索引，不直接读取 Java 本地向量文件。文件与报告保存到 Python 自己的本地目录。

### 审核找回与生命周期

- conversationId 表示聊天会话，threadId 表示一次可恢复图运行；新问题创建新运行，反馈恢复原 threadId。人工审核先持久化可恢复中断，再发布 HUMAN_FEEDBACK_REQUIRED 并正常结束当前 SSE；接受继续调度，拒绝携带意见重新规划。
- 新增 `GET /api/sessions/{sessionId}/active-run`：无占用返回 200 与 null；有占用返回 agentId、conversationId、threadId、status、planRevision、plan、resumeRequest、recoverable。resumeRequest 包含原 query、humanFeedback、nl2sqlOnly，不含密钥；计划及参数来自持久化记录，不能重新调用模型重建。
- 前端加载历史后查询摘要，重建原请求、计划与审核状态，复用反馈路径；新增可选 feedbackRevision，适配后的前端每次反馈必须携带。正常流在收到 HUMAN_FEEDBACK_REQUIRED 时，将 plan、planRevision、threadId 一起保存到同一审核卡片，刷新恢复亦如此；不能在点击批准时查询最新版本再套用到旧卡片。版本不匹配拒绝且不启动恢复；planRevision 每生成一份需审核的新计划递增，不随普通节点事件递增。无版本旧客户端仅允许首次审核且无重规划的兼容情况，后续要求刷新升级客户端。
- 仅 WAITING_FEEDBACK 且 checkpoint 可恢复时展示审核按钮。RUNNING、RESUMING、CANCELLING、RECOVERY_REQUIRED 展示占用并禁止新问题，不承诺补发断线前完整 token 流。Java 后端不启用此扩展。
- 状态从 CREATED 进入 RUNNING，可经 WAITING_FEEDBACK、RESUMING 回执行；终态为 COMPLETED、FAILED、CANCELLED，取消经过 CANCELLING，不确定恢复进入 RECOVERY_REQUIRED。待审核及中间状态均占用会话。
- 锁粒度为 Agent＋conversationId，同一会话只允许一个未结束运行，待审核期间新问题拒绝而不替换。不同会话可并行。Redis 只用于短锁，不在用户审核期间持锁，不作为事件总线。
- 创建运行时，在短锁内用 MySQL 事务锁定会话占用行、检查空闲并创建运行；占用行主键及事务约束防止并发初始化。反馈检查归属、版本、checkpoint 后，通过状态和 version 条件更新 WAITING_FEEDBACK 到 RESUMING，只有成功者可以续跑。
- Redis 使用带 owner token 和 TTL 的条件获取，释放及续期用 Lua 比较 token 后操作，不能无条件删除。失锁停止发起新状态变更，重新获取并读取数据库版本；Redis 不可用拒绝新建/恢复，已有占用保留。
- Redis、MySQL 与 checkpoint 不具备共同原子事务。MySQL 行锁、版本条件更新和唯一约束是最终防线，锁或心跳过期不能证明原执行已经停止，不自动夺取仍可能执行的任务。
- 启动先对账运行与 checkpoint，再放行对应会话：仅状态、计划版本、效果记录与 checkpoint 一致且确认旧执行停止的持久化中断还原 WAITING_FEEDBACK；已提交结束结果补终态；其他情况保持 RECOVERY_REQUIRED 和占用。RESUMING 期间崩溃同样对账，不盲目再次批准。
- 提供部署维护者通过本机运行的管理 CLI，包含 inspect（只读查看运行、owner、状态/version、checkpoint、未确定效果与数据库查询标识）和 resolve-failed（失败收尾）。使用部署侧管理凭据，不暴露公共强制恢复 HTTP 接口。resolve-failed 必填 threadId、预期 version、操作者及原因；必须提供旧 worker 已退出/任务已 join 的证据，并对已提交数据库查询确认结束或经连接器取消后确认停止。无查询标识、数据库不可达等无法确认的情况拒绝操作，提示核查步骤，继续保留占用；仅锁或心跳过期不算证据。
- CLI 在与新建/恢复相同的协调及数据库版本约束下再次检查证据和状态，仅允许 RECOVERY_REQUIRED 转 FAILED：持久化失败快照、丢弃本轮暂存记忆、条件释放自身占用并写入审计记录。重复执行返回已收尾结果，过期 version 拒绝。已确认停止但 SQL 结果仍不确定时只允许失败收尾，保留不确定说明，不重发 SQL。首版不提供人工任意跳节点/强制续跑；安全的等待审核恢复由启动对账完成。
- 完成和取消须先确认实际执行停止，持久化最终快照、提交或丢弃本轮记忆，再用同一管理库事务写终态和结果引用，仅当 active_thread_id 仍指向自身才释放占用；完成结果必须在发布最终回答/complete 前持久化。待审核取消不重新执行图。协程取消不等于数据库操作已停止，连接器需验证实际超时和取消效果。
- 新增并发规则下，普通 JSON 占用冲突返回 409、Redis 不可用返回 503；图入口完成鉴权和参数校验后，使用兼容 error 事件的 text 表示忙、过期反馈或暂不可用，随后终止，不发成功 complete。身份错误沿用原鉴权状态码。

### 记忆、幂等与重入

- chat_message 继续由前端调用保存接口写入展示历史，图节点不重复插入；后端记忆服务独立维护跨轮上下文；checkpoint 只负责单次运行恢复；agent_run 为审核摘要提供依据；agent_run_result 是不依赖浏览器的最终结果事实来源，不是第二份图节点展示消息。
- 新增只读 `GET /api/sessions/{sessionId}/runs`，返回分页运行摘要（threadId、status、outcome、resultVersion、finishedAt、hasResult）及 activeThreadId，终态运行即使已释放占用仍可发现；排序及游标保证稳定翻页，不能要求浏览器已保存 threadId 才可找回。新增 `GET /api/sessions/{sessionId}/runs/{threadId}` 返回运行状态；终态同时返回最终快照，非终态 result 为 null，资源不属于该会话返回 404。不导出凭据或内部 checkpoint 内容。
- 页面进入会话、流异常或完成后历史保存失败时，用运行列表和详情补查；对 RUNNING/RESUMING/CANCELLING 使用只读状态轮询直到等待审核或终态，离开页面停止轮询。快照只返回最终结果及必要报告/数据引用，不回放全部 token。COMPLETED 可包含成功或能力不足等业务结局；FAILED/CANCELLED 明确原因，已有局部数据标为未完成，不伪装成功报告。
- 服务器给快照中的每个需展示结果分配稳定消息键（threadId＋结果种类＋序号），在线流中保存最终结果与刷新后补存均使用同一组键；列表与详情在删除前保留。前端按快照补存或直接展示时按键合并，不追加第二份逻辑结果；原旧客户端无键行为仍作为已知限制。
- 适配后的前端收到终止事件后，先按已收到的 threadId 查询运行详情，再以快照中的 resultVersion 与消息键保存最终展示结果；流中 token 仅用于临时展示，不自行生成另一组最终结果键。正常在线与刷新找回走同一结果合并流程；查询暂失败可稍后重试只读详情，不能重发执行请求。
- 模型记忆保留“用户问题＋规划结果”语义及原窗口/长度配置，按 Agent＋会话读取。当前计划暂存于同一轮；拒绝后替换原计划版本，成功完成才提交，失败、取消、能力不足丢弃本轮暂存并保留既往成功轮次。
- 消息保存接口增加可选 metadata 幂等键，适配后的前端为同一次逻辑保存复用稳定键，后端按会话＋键返回原消息。旧客户端无键保持旧行为，不承诺去重；摘要找回不重新保存历史。
- 审核节点中断前段只做可重复读取及计划构造，不执行 SQL 或追加展示消息。副作用使用稳定 effect_key；重入复用已提交结果引用，运行、记忆和内部效果记录尽量同事务保存。
- 查询数据源与效果记录之间不能保证原子提交。SQL 已返回但效果未持久化时崩溃，标记不确定并对账，不自动重发可能有副作用的 SQL，不宣称 exactly-once。
- 阶段 0 确定 saver、状态序列化、标识、effect_key、写入归属与跨存储对账；阶段 1 必须验证最小图中断、进程重启、同 threadId 恢复和副作用去重，阶段 3 才扩展完整审核 UI。

### 删除与配置变化

- 删除单会话、清空 Agent 全部会话或删除 Agent 时，只要目标范围内有非终态运行（含 WAITING_FEEDBACK、CANCELLING、RECOVERY_REQUIRED），整次请求返回 409，不部分删除，不隐式取消。用户先停止；不确定运行经 CLI 处理到终态后再重试。无占用时沿用原成功响应。
- 删除与运行创建/恢复共享持久化 Agent/会话生命周期闸门：按 Agent 后会话的固定顺序取得行锁，事务内检查目标存在、删除标记及运行占用。批量清空/删除 Agent 先设置可恢复的删除标记，阻止新建、恢复和历史补存，再处理目标；进程崩溃后继续清理，不允许新运行落入已删除范围。单会话删除同样禁止晚到的反馈、结果或消息保存重建会话。
- 删除业务记录时同步删除或标记清理其运行、结果、模型记忆及展示消息；checkpoint、效果数据和文件通过持久化清理任务按归属删除，失败可重试。共享知识/文件仅清理已无引用的对象，未完成清理不对外重新开放该标识；保留不含凭据或结果正文的最小故障/操作审计。未显式删除前不自动按 TTL 清除可找回的最终结果。
- 清空会话仅删除本次目标集合；事务提交逻辑删除及持久化清理任务后撤销 Agent 的临时闸门，允许创建不同标识的新会话。删除 Agent/单会话的标识保持已删除，不因旧请求重试恢复。原成功响应表示逻辑删除及清理任务已提交，不表示所有外部文件已物理删除；部署工具列出清理进度及错误并支持重试。事务提交失败不能返回成功。
- 运行创建及生成待审核计划时保存不含明文密钥的配置快照/指纹：Agent、数据源身份与数据库目标、绑定/选表、逻辑关系、语义/召回配置、提示词有效内容及优先级、模型 provider/模型/参数和 embedding/索引版本。可变配置通过单调修订或规范化指纹比较，不只存可变记录 ID；密钥仅保存凭据引用。
- 恢复及每次新的模型/SQL 外部操作前，重新校验当前 API key、Agent 存在、绑定和允许表，再比较计划所用配置。权限收紧不因快照而绕过；数据源改指向、绑定/选表/提示词/模型等影响计划的配置变化使旧计划失效，停止发起新操作，确认无在途执行后以 CONFIG_CHANGED 失败快照结束并释放占用，前端提示重新提问。不能将原反馈自动应用到新计划；无需重规划的纯展示标题/头像更新不使计划失效。
- 凭据轮换但身份/权限和其他配置不变时，外部连接使用当前凭据；客户端 API key 必须重新通过校验。已开始的外部操作不能承诺被配置变更瞬时撤回，按取消/不确定执行规则确认停止后处理，必要时进入 RECOVERY_REQUIRED，不在未确认时释放占用。

## Testing Decisions

- 用户已确认主测试边界为 HTTP/SSE。以真实应用入口检查对外请求、响应、事件、持久化结果和业务副作用；在模型调用适配边界注入可控输出，不 mock 整个工作流，不断言私有函数、调用顺序或内部目录结构。
- 覆盖模块包括兼容接口、配置与管理业务、图与事件适配、运行及审核服务、会话记忆、数据迁移、连接器、检索和文件服务。持久化与并发场景使用真实 MySQL、PostgreSQL、Redis 和 saver；仅在外部存储适配确有必要时补充集成边界。
- 参考现有 GraphControllerTest 的请求参数、反馈及 SSE 用例，SessionEventControllerTest 的标题事件及响应头用例，以及各管理 Controller 的行为测试。参考 GraphServiceImplTest 的新运行标识、审核复用标识、中断事件、拒绝后再次中断和节点事件身份用例；复用行为案例，不照搬其内部 mock 断言。已有 Java 测试不能作为 Python 兼容性通过证据。
- 98 个原接口逐项记录方法、参数、错误、状态码、包裹及真实数据变化；空值、日期、分页、上传下载、鉴权失败、不支持数据源和无效配置均纳入契约。新增摘要、feedbackRevision、消息幂等键和并发错误规则单列。适合固定输入的场景对照 Java，明确排除范围单独标注。
- 图场景用固定模型输出覆盖正常链路、提前结束、nl2sqlOnly、计划修复、语义不一致、SQL 执行修复、各类上限和能力不足。断言结构化计划、真实 SQL 结果、事件语义与有限结束；不逐字匹配自由文本。
- SSE 检查空文本状态、节点身份、重复尝试、类型、顺序、标题心跳和终止唯一性；待审核事件仅在 checkpoint 可恢复后出现。错误流不跟成功 complete；正常待审核结束不能触发误取消。
- API key 开启/关闭分别覆盖新查询、在线拒绝后再审核、刷新找回、结果查询、停止及标题 SSE；验证 fetch SSE 分片解析、401 显示、跨 Agent 404、跨会话停止不生效、URL 不含 key 及执行 GET 不自动重试。审核卡片必须绑定事件中的计划版本，旧卡片不能通过读取最新版本批准新计划。
- 恢复验收必须包含后端重启＋页面刷新＋重新进入会话，然后接受、拒绝各一次。验证原请求和计划重建、threadId 复用、版本校验、旧客户端限制、跨 Agent 拒绝及占用提示。
- 并发验收覆盖双标签页新问题、待审核新问题、双击反馈、旧版本反馈、不同会话并行、Redis 不可用、失锁及错误 token 释放。通过任务数、实际查询效果、状态和可读结果证明没有第二次执行。
- 故障场景覆盖 checkpoint 与运行记录提交窗口、进入 RESUMING 前后崩溃、SQL 返回但效果未记录、取消与结束竞争。验证对账及完整处理闭环：进入 RECOVERY_REQUIRED，CLI 查看原因，证据不足拒绝收尾，确认执行停止后按 version 失败收尾，会话可开始新问题；重复和过期 CLI 请求不能重复清理或误放行。
- 最终结果验证后端完成后、浏览器保存前断开或刷新，以及终态提交后 SSE 最终事件发送前崩溃：无需已知 threadId 即可从运行列表找到结果，详情含同一回答/报告，稳定键补存只出现一次；同时检查错误/取消结局、文件引用、跨 Agent 拒绝和未删除前结果留存。
- 删除验收覆盖运行、待审核、不确定状态的单会话删除、批量清空和 Agent 删除均 409 且无部分删除，终态后可删除；覆盖删除与创建/完成竞争、晚到消息保存、清理任务中崩溃后重试，以及共享文件不被误删。配置验收覆盖审核期间改数据源、选表、模型和提示词导致旧计划失效，当前权限收紧不得按快照继续执行，纯标题及正常凭据轮换遵守例外。
- 记忆场景覆盖第二轮新 threadId 的追问、拒绝后计划替换、成功仅提交一轮、失败/取消/能力不足隔离、消息重试去重及旧客户端无键行为。审核摘要只恢复卡片，不重复保存历史。
- 数据验收覆盖空库迁移可重复执行、13 张业务表与新增内部/saver 表、绑定选表唯一性及解绑级联；复制数据核对 ID、凭据、API key、历史与文件引用。两个业务数据库分别验证连接、Schema、方言、类型及真实 SQL。
- 知识和文件验收覆盖索引持久化、召回、过滤、更新、删除和 embedding 重试；本地、Elasticsearch、Milvus 分别验证。上传、读取、模板和报告下载核对内容与响应头；无环境项目保持未验证。
- 提供至少一个经测试确认 SQL 无法可靠满足、必须依赖已移除外部 Python 预测库的案例，验证默认和导入提示词都不会执行 Python 或虚构预测；同时保留可由 SQL 完成的统计请求。
- 最终用真实模型、真实业务数据库及现有前端联调，从知识召回到报告完整走通；单独记录数据库取消实际效果、资源释放与未验证外部服务。占位响应、空列表或仅注册路由不计完成。

## Out of Scope

- 修改原 Java 后端源码、替换原服务实现，或要求 Python 依赖 Java 在线运行。
- Python 代码生成、沙箱执行、分析节点及对应工具；OSS 文件存储。
- SQL Server、Oracle、Hive、H2、达梦等业务连接器，或非 MySQL 管理库。
- 导入 Java checkpoint、继续 Java 在途任务、直接复用 Java 本地向量文件和框架序列化记忆。
- 多 worker/多进程部署、分布式 SSE 事件总线、自动续跑重启前所有任务、完整 token 流回放。
- 新用户体系、多租户体系、额外鉴权协议、提示词全面优化、图流程重新设计，以及 Java/Python 类结构逐一映射。
- 跨存储 exactly-once 保证，以及在执行是否停止尚不确定时自动释放会话或重发 SQL。
- 本次 spec 整理中的后端实现、依赖锁定和真实服务联调；这些均为后续实施任务。

## Further Notes

- 参考资料：[已修订设计](python-backend-design.md)、[接口基线及源码摘要](python-backend-api-inventory.md)、[实施任务与验收](python-backend-tasks.md)。本 spec 使用这些资料的已确认结论，不把更早讨论中的建议当成最终决定。
- 实施顺序为阶段 0 契约/骨架/持久化与幂等设计，阶段 1 真实查询及最小重启恢复，阶段 2 完整业务分支，阶段 3 完整审核/恢复/取消，阶段 4 补齐管理与外部存储并最终验收。早期简化图不缩减最终范围。
- 六项审核结论全部纳入：完整迁移清单、刷新找回审核、会话级并发、三类历史/记忆归属、删除 Python 后的能力出口、持久化前置。已核实原 MySQL 基线存在 13 张业务表，不能将关键字大小写造成的漏计当成缺表修复。
- 本次 spec 审查另外补齐凭据传递及鉴权矩阵、审核事件版本、异常恢复 CLI 出口、最终结果快照、删除互斥、配置变化校验。恢复 CLI 首版只允许有证据的失败收尾，不引入人工强制重跑。增加运行列表及详情两个只读 HTTP 扩展，原 Java 映射仍为 98 个。
- 阶段 0 准入：先完成 98 个接口的契约矩阵（参数/DTO/默认值/错误/鉴权/副作用）、新增扩展与兼容差异、固定验收样例。标明需配置环境的验证项；影响某阶段行为的契约不能留空或仅写“兼容原实现”，对应差异确认后才进入该阶段功能实现。骨架和源码提取可同步进行，不把路由计数当成契约已完成。
- 尚待实施时从源码提取并验证的内容包括 DTO 细节、错误码、具体重试值、provider、解析格式、检索参数、凭据编码和存量记忆转换。逐项形成契约证据，不宣称这些已经验证通过。
- 最终交付需包含独立启动指南、入口切换和切回 Java 的说明、迁移清单、图状态与节点映射、实际运行轨迹，以及逐接口和逐阶段验收记录。每次改动检查适用 .gitignore，并仅提交本次变更且使用明确的 Git 描述。
- 发布状态：本地 spec 已形成；当前会话未提供项目 issue tracker 配置与分诊标签词汇，不能仅凭上游 Git remote 推断发布目标。按 to-spec 要求先运行 `/setup-matt-pocock-skills` 配置后，再将本 spec 发布到明确的项目 tracker 并应用 `ready-for-agent`，不另行分诊。本地文件不表示 issue 已创建。
