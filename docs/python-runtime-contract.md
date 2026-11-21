# Python 公共运行与恢复契约（Ticket 01）

本文件冻结后续 tickets 的公共边界。01 只实现探活和模型管理；未实现的图、会话、文件接口返回 404，不挂成功占位路由。原接口逐项输入、返回分支、默认值、状态及前端调用见 [98 接口矩阵](python-baseline/http-contracts.md)、[DTO catalog](python-baseline/schemas.md)。

## 运行及持久化选型

Python 3.12，FastAPI lifespan 初始化独立 MySQL 管理库和 AsyncSqliteSaver；单 worker，Uvicorn 绑定 localhost:8065。生产多 worker 不在本规格内。退出 lifespan 先关闭 saver 再 dispose 管理库连接池；启动迁移或 saver 失败即启动失败，不能探活成功却不可存储。模型网络请求使用 httpx，超时默认 30 秒、无自动重试、无环境代理继承；可使用配置中的显式 HTTP 代理。配置更新后每次调用从数据库读当前值，不依赖进程缓存。

精确依赖和所有传递版本/哈希由 `PYTHON/uv.lock` 冻结，`uv sync --frozen` 重建。模型适配为 OpenAI-compatible HTTP（与 Java DynamicModelFactory 一致），不依赖厂商原生 SDK。Redis 是后续短锁客户端；PyMySQL 是管理库及 MySQL 业务驱动，psycopg 是后续 PostgreSQL 驱动。实际 saver 兼容性用 `tools/verify_saver.py` 的两个独立进程中断/恢复验证；03 继续验证最小业务图与效果去重，不把本次 saver smoke 当完整恢复验收。

选择本地 SQLite saver 是本机单 worker 学习部署决策；[官方参考](https://reference.langchain.com/python/langgraph.checkpoint.sqlite)说明其适用本地场景，[checkpoint 说明](https://langchain-ai.github.io/langgraph/reference/checkpoints/)不建议将其用于生产并发负载。后续生产替换须单独验证，不能直接将本方案扩展成多 worker。FastAPI 的资源管理依据 [lifespan 文档](https://fastapi.tiangolo.com/advanced/events/)。

## Ticket 01 管理接口

`GET /echo/ok` 返回 HTTP 200、text/plain `ok`。`/api/model-config` 的 7 个原映射原样实现，响应统一 `{success:boolean,message:string,data:any|null}`：list 返回完整 ModelConfigDTO 列表（id 降序）；add/update/delete/activate/test 成功 data=null；check-ready 返回 `{chatModelReady,embeddingModelReady,ready}`。ready 只表示两个类型有激活配置，不向供应商发探测，也不承诺持续连通。

add 的 provider/baseUrl/modelName/modelType 必填。温度 0、maxTokens 2000、代理关闭；新增强制 isActive=false，忽略传入 id，密钥可对 custom 留空；其他 provider 激活及调用时必须有 key。模型类型仅 CHAT/EMBEDDING。模型路径默认 `/v1/chat/completions`、`/v1/embeddings`，拼接在 baseUrl 后（baseUrl 若已含 /v1，则路径应填 `/chat/completions`、`/embeddings`）。路径只能是相对绝对路径，不能填外部 URL。embedding 请求编码 float，返回必须为非空有限数值数组；聊天返回必须为非空文本。

列表 API key 和 proxyPassword 均不泄漏原文。update 必填 id，不能改 modelType；API key 为空或含 `****`、代理密码为空或含 `****` 时保留已保存值；isActive 只由 activate 操作控制。activate 验证静态配置，在同一个 MySQL 事务内锁定模型类型行、停用同类型其他配置并激活目标；不发模型网络请求，与 Java 激活/连接测试分离。调用 test 才实际使用库中完整凭据请求供应商。当前激活模型不允许删除，未激活模型软删后不再列出或调用。无默认假模型、无默认启用项。

业务失败（不存在/删除激活配置/模型类型变化/供应商连接失败）保留 HTTP 200 + success=false。结构绑定及校验失败 HTTP 400 + 同一包裹，不返回 FastAPI 默认 detail 数组。Python 显式收紧 URL、字段长度、温度范围、正 maxTokens、完整代理配置；基础设施不可用 HTTP 503 + 脱敏通用错误，是与 Java 吞异常 200/500 的明确差异。供应商失败只返回状态码或连接失败提示，不回显响应正文、URL、凭据。管理接口仍是原本机管理契约，无新增用户体系。

固定差异样例：`POST add {apiKey:"secret"}` -> 400 success=false，不含 secret/detail；`POST activate/999999` -> 200 success=false；删除当前激活模型 -> 200 success=false；test 的供应商 401 -> 200 success=false、message 含 401；新建传 isActive=true -> list 仍 false；脱敏表单编辑再 test 仍用原 key。普通错误自由文本允许不同，但字段/状态/业务效果不能不同。

embedding 保留 Java EmbeddingModelCompatibilityValidator：当前默认模型的 provider/baseUrl/modelName/embeddingsPath 组成空间身份。update 当前默认时改变任一身份字段或 activate 不同空间模型，均 HTTP 200 success=false，原默认和配置不变；纯密钥轮换、maxTokens 等非空间字段不受此限制。没有当前默认时允许首次激活。配置 DATAAGENT_EMBEDDING_DIMENSION 默认 0（Java 默认），大于 0 时 test 返回向量长度必须一致，否则 HTTP 200 success=false，提示重建索引。检索票须在有版本集合/重建协议后增加合法迁移路径，不能绕过本守卫。固定样例：A 激活后切换 modelName 不同的 B 失败；修改 A.modelName 失败且回读仍 A；预期维度 4、实际 [0.2,0.4,0.6] 测试失败。

## 标识、状态及写入归属

agentId 为正整数，conversationId 等于 chat_session.id（UUID），threadId 为每个新问题生成的 UUID；恢复不生成新 threadId。version 是数据库 CAS 版本，每次状态改变递增；planRevision 是每份需审核新计划的单调整数，从 1 开始，重试节点不递增。

状态转换：CREATED -> RUNNING；RUNNING -> WAITING_FEEDBACK -> RESUMING -> RUNNING；运行中可进入 CANCELLING，确认停止后 CANCELLED；成功 COMPLETED，确定失败 FAILED，不确定执行 RECOVERY_REQUIRED。后三个 COMPLETED/FAILED/CANCELLED 才是终态；能力不足可以 COMPLETED/outcome=UNSUPPORTED，但记忆不提交。任何非终态保留占用。

可序列化 state schema version=1：agentId/conversationId/threadId、request（query/humanFeedback/nl2sqlOnly）、evidence/schema/relations 引用、plan/planRevision、sql、resultRefs、feedback、attempts（节点名到整数）、finalAnswer、outcome、configFingerprint。JSON 标量/列表/字典或持久化引用；不存 client、DB 连接、生成器、异常对象、凭据、完整二进制。节点默认替换字段，事件追加到外部流，不在 checkpoint 无限累积 token；结果引用可重读才可提交。

agent_run 是状态/审核事实源；agent_session_runtime 是会话唯一占用；agent_conversation_turn 维护跨 threadId 成功记忆；graph_effect 维护副作用边界；agent_run_result 保存最终快照；chat_message 仅消息 API 写展示历史。图节点不能重复写展示消息。记忆按 Agent+会话读取成功问题+计划，窗口沿用 Java 配置；失败/取消/能力不足丢弃本轮 STAGED，拒绝重规划替换本轮计划，不追加成功轮次。

effect_key 格式 `v1:{operation}:{logicalStepId}:{ordinal}`，同一逻辑步骤重试和图重入复用，不含 attempt、随机数、模型自由文本或 key。唯一 (threadId,effect_key)。阶段 PREPARED -> IN_FLIGHT -> COMMITTED；提交存 result_ref，重入读结果；IN_FLIGHT 未确定时不重发 SQL，进入 RECOVERY_REQUIRED。SQL 数据源与管理库不能原子提交，不宣称 exactly-once。查询 id/worker owner 持久化到效果记录用于确认停止。

## 三个新增只读 HTTP 扩展

统一鉴权失败 401、资源不存在/跨归属 404，普通参数失败 400、占用冲突 409、协调存储不可用 503；JSON 成功使用 ApiResponse 包裹。3 个路由均以路径 sessionId 找到所属 Agent；可选 query agentId 若给出必须相同，不得绕过鉴权。扩展不计入原 98 个映射。

1. `GET /api/sessions/{sessionId}/active-run`（11）：200 data=null 或 `{agentId,conversationId,threadId,status,planRevision,plan,resumeRequest,recoverable}`。resumeRequest 仅 query/humanFeedback/nl2sqlOnly；recoverable 仅 WAITING_FEEDBACK 且 checkpoint、计划版本、效果一致才 true。
2. `GET /api/sessions/{sessionId}/runs?limit=20&cursor=...`（05）：limit 1..100；200 data=`{items:[{threadId,status,outcome,resultVersion,finishedAt,hasResult}],nextCursor,activeThreadId}`。按 `(created_at,thread_id)` 降序 keyset 分页，cursor 为该元组的 URL-safe base64 JSON，非法 cursor 400，不用易漂移 offset；空列表 items=[]、nextCursor=null。finishedAt 使用 UTC RFC3339，未终态 null。
3. `GET /api/sessions/{sessionId}/runs/{threadId}`（05）：200 data=`{threadId,status,version,result}`；未终态 result=null，终态 result=`{resultVersion,outcome,finalAnswer,artifacts,messages,reason}`。artifacts 为可授权读取的 SQL/报告引用，不暴露内部绝对路径；messages 为 `{messageKey,messageType,role,content,metadata}` 列表。不导出 checkpoint 或请求凭据。

最终结果键 `v1:{threadId}:{kind}:{ordinal}`（kind=answer/report/sql/error，ordinal 从 0 开始）；在线完成与刷新补查同一快照复用相同键。消息 POST 原 DTO 增加可选 `metadata.messageKey`，按 (sessionId,messageKey) 唯一返回原消息；同键不同正文 409，防止静默覆盖。旧客户端无键保持原追加语义。resultVersion 从 1 起，客户端只能按服务端快照合并，不能用流 token 生成第二套最终键。

## 凭据、SSE 与前端

X-API-Key 优先，次为 Authorization Bearer（大小写不敏感）；当前 apiKeyEnabled 控制是否必需。总是检查 Agent 存在和资源归属，密钥不放 URL、不写 checkpoint/request/快照。凭据先校验再开始 SSE；适配前端只在内存保留使用者输入，刷新后先重新输入。模型管理凭据与 Agent key 不混用。

`GET /api/stream/search` 保留原 query 参数和默认值（矩阵 #64）；增加可选 feedbackRevision 正整数，适配客户端反馈必带。新问题新 threadId，反馈必须原 threadId+会话匹配。无版本旧客户端仅首次计划且从未重规划允许，其他拒绝。旧 planRevision 拒绝且不恢复。按钮必须绑定收到的 threadId/planRevision/plan，不能点击时查询最新版本批准。

普通 SSE `event: message` 的 data 保留 agentId/threadId/eventType/stepId/attempt/nodeName/textType/text/error/complete；eventType=NODE_OUTPUT/FINAL_ANSWER/HUMAN_FEEDBACK_REQUIRED；textType=JSON/SQL/HTML/MARK_DOWN/RESULT_SET/TEXT。HUMAN_FEEDBACK_REQUIRED 增加完整 plan、planRevision，取自同一已提交审核状态。stepId 是单次节点执行 id，attempt 是节点尝试序号；nodeName 使用 Java 对外常量。空 text 状态事件保留。终止恰好一个 `event: complete` 或 `event: error`，error data.text 可读，不能靠关闭 TCP 判成功。

fetch SSE 解析 CRLF/LF、跨 chunk 帧、多行 data、comment 和 event；AbortController 处理断连。禁止自动重连执行性的 GET。忙/旧反馈/Redis 不可用在完成认证及参数检查后的流中发 error.text 后结束，不发 complete；身份失败在流前 401。待审核先持久化 checkpoint，再写 WAITING_FEEDBACK，再发 HUMAN_FEEDBACK_REQUIRED 并正常结束当前流；其正常结束不能触发取消。

`POST /api/stream/stop`（12）query 必填 agentId、conversationId，可选 threadId，必须互相归属一致，成功 204 空体。Java 原 stop 无 key、无 agentId；Python 显式增强。`GET /api/agent/{agentId}/sessions/stream`（05）同样新增 key，事件 title-updated data=`{type:"title-updated",sessionId,title}`，约 2 秒 heartbeat comment，不向其他 Agent 发事件。CORS 允许明确来源和 Authorization/X-API-Key 预检。

## 会话占用、提交及对账

Redis key `dataagent:run:{agentId}:{conversationId}`，随机 owner token，SET NX PX 30000；续期每 10 秒、Lua 比较 token 后 PEXPIRE，释放 Lua 比较后 DEL。只覆盖创建/恢复短临界区，人工等待不持 Redis 锁。Redis 不可用拒绝创建/恢复且不删已有占用；失锁停止新状态变更，重获锁后读 MySQL 版本。

固定顺序锁 agent_lifecycle、agent_session_runtime 行；INSERT IGNORE 初始化再 SELECT FOR UPDATE。检查 lifecycle=OPEN、无 active_thread_id，原子新建 run+turn+占用；占用非空 409，不因 TTL/心跳超时夺取。恢复需 WAITING_FEEDBACK、planRevision、version 和 checkpoint 一致，CAS 到 RESUMING，只有成功者执行；重复反馈不重发操作。

提交顺序：文件/SQL 结果先持久化并验证可读 -> agent_run_result 快照 -> 同一 MySQL 事务提交/丢弃记忆、run 终态/结果版本、仅释放指向自身的 active_thread_id -> FINAL_ANSWER/complete。故障时即使浏览器未保存消息也可经 runs/详情找回。阶段重入使用 effect_key；不确定 SQL 不自动重发。

启动先对账后放行：已提交结果补终态；可证明旧 worker 停止且 checkpoint/计划/效果一致的 interrupt 恢复 WAITING_FEEDBACK；其他一律 RECOVERY_REQUIRED，保留占用。进程协程取消不能证明数据库查询停止，需查询 id/连接器确认。不能把 saver 和 MySQL 视为一个事务。

本机 CLI（12）：`python -m app.recovery inspect --thread-id UUID` 返回状态/version/owner/checkpoint/未确定 effects/query ids（无正文密钥）。`resolve-failed --thread-id UUID --expected-version N --operator NAME --reason TEXT --evidence-file PATH` 只在部署端管理权限下运行；证据包含 worker 已退出/join 和每条已提交数据库操作已结束或已取消且确认停止。证据不足、DB 不可达、缺 query id 均拒绝，锁过期不算证据。共享短锁/行锁/CAS，只允许 RECOVERY_REQUIRED -> FAILED，写失败快照、丢弃暂存记忆、条件释放、审计。相同操作幂等，过期版本拒绝；不提供强制续跑/任意跳节点/重发不确定 SQL。

## 配置指纹与删除闸门

指纹为规范 JSON（键排序、UTF-8）SHA-256：Agent 执行配置、数据源身份/目标、绑定选表、逻辑关系、语义与召回参数、有效提示词内容/优先级、模型 provider/name/参数、embedding 与索引版本。不含 key/代理密码，只保留当前凭据引用；标题/头像等纯展示变更不入指纹。每次外部模型/SQL 操作及恢复前校验当前身份、绑定权限及指纹；变化以 CONFIG_CHANGED 失败，先确认无在途操作才释放，否则 RECOVERY_REQUIRED。凭据轮换不变身份/权限时使用当前凭据，不让旧快照绕过权限。

删除 Agent、清空会话、删单会话（13）共享 Agent 后会话的行锁顺序。目标范围任一非终态整次 409，不部分删/隐式取消。空闲时事务写删除闸门、逻辑删除及 agent_cleanup_job，再返回原成功包裹；外部 checkpoint/效果/文件清理异步重试，失败不会重开已删 id。批量清空只清本次集合，提交后解除 Agent 临时闸门允许新 UUID 会话；永久删除保留 tombstone，晚到消息/反馈不能重建。保留最小无正文审计，不按 TTL 静默删除结果。

固定验收：同会话双新请求只有一个执行；待审核拒绝新问题；同版本双反馈一次恢复；旧版本无执行；跨 Agent 404；Redis 失联拒绝且不释放；过期锁不产生新运行；结果已提交但 SSE 丢失仍可找回同键；改选表拒绝旧计划；RECOVERY_REQUIRED 删除 409；CLI 仅心跳过期证据拒绝。实际业务验收分别由 03/05/11/12/13 完成。

### Ticket 09 embedding 空间迁移补充

第 25 段在线热切换拒绝行为保留。合法迁移由停服维护命令 `python -m app.vector_operations --model-id ID` 完成：无非终态运行且清理已完成，完整暂存新空间后核对 revision 和模型，最后同一 MySQL 事务发布全部索引状态及默认模型。暂存不得覆盖当前发布空间；失败旧状态和旧向量可继续读取并支持重试。SQLite chunks 以 space 隔离，ES/Milvus 集合以空间哈希及维度隔离。数据目录、管理库和外部服务共同备份；旧目标需要原凭据清理时恢复旧配置，不将当前目标 token 发送给历史目标。
