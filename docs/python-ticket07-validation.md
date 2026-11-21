# Ticket 07 验证记录

日期：2026-11-15。范围：完整分析图、结构化规划、SQL 修复、流式报告和跨轮记忆。

## 契约与实现

图路径为 IntentRecognition → EvidenceRecall → QueryEnhance → SchemaRecall → TableRelation → FeasibilityAssessment → Planner → PlanExecutor。Schema 召回按增强问题选择授权表，关系节点可以从完整授权 Schema 补充遗漏表；未知表禁止继续，关系补充最多初次加三次修复。闲聊、空问题增强及能力不足以持久化最终回答后 complete 结束。

Planner 输出结构化计划，SQL 工具使用 instruction，报告工具使用 summary_and_recommendations；运行时只允许 SQL_GENERATE_NODE 和 REPORT_GENERATOR_NODE。计划错误最多初次加三次修复，来源为 Java PlanExecutorDispatcher 中 repairCount > 2 的结束规则。每个 SQL 步骤最多生成 10 次，来源为 DataAgentProperties.maxSqlRetryCount；事件 attempt 与步骤重试预算分离。语义不一致回生成，确定的 SQL 错误携带原因回修复，连接中断或超时保留不确定状态而不盲目重发。

nl2sqlOnly 对照 Java PlannerNode.handleNl2SqlOnly、PlanExecutorNode、SemanticConsistenceDispatcher 和 SqlExecuteNode：固定单 SQL 计划，保留语义检查和真实查询，不请求模型规划、不进入审核或报告。早期 Python 最小图只生成 SQL 的路径已修正。

报告通过供应商 SSE delta 输出 HTML；非流式供应商明确接受其 JSON 响应作为一个分片。文件先写本地内容寻址存储，再将 URL、内容、MIME 和文件名写入最终快照；报告消息使用稳定 threadId/report 消息键。报告文件响应使用 sandbox CSP，前端仍需清理模型 HTML。接口 46 接受原始 UTF-8 片段，返回带文档外壳的 text/html 下载；空内容为 400，历史片段也可导出。

模型记忆只读取当前 Agent、conversationId 的 COMMITTED 问题和计划。最多五轮、每份计划最多 2000 字符，对照 Java DataAgentProperties 及 MultiTurnContextManager。新 threadId 和应用重启不丢失历史；成功完成时与结果事务一起提交，失败/提前结束/能力不足不提交当前轮。展示消息补存不写记忆。

模型规划与 HumanFeedbackNode 分开 checkpoint，避免 resume 重跑规划并批准不同计划。完整拒绝重规划、在线取消及配置保护仍按票据归属在 Ticket 08 交付。

## 验证进度

初次实现全量：52 passed、1 skipped；skip 为旧版 DOC 解析所需环境未显式注入。审查修复后专项验证通过，包括多 SQL 预算、关系补充上限、空增强出口，以及重启批准不重新规划。ruff、mypy app/tools 通过。最终全量：56 passed、1 skipped（旧版 DOC）；随后显式指定已安装的 Tika JAR 与 DOC 样例，该专项 1 passed。前端单测 20 passed；Nuxt 全局类型检查仍有既有 model-config、服务导入、markdown 等错误，本票修改的 ChatMessageList 未出现类型报错。双轴审查全部复核通过，见 [审查记录](python-ticket07-review.md)。

浏览器前后端联调在审查修复、复核和提交完成后开始。联调追加修复后，全量 57 passed（包含 DOC，无跳过），后补报告错误/空结果专项 2 passed；ruff、mypy 仍通过。重复报告修复及测试记录提交后才恢复联调。

最后一轮（规划 JSON 契约和报告下载入口复核后）：后端全量 **60 passed**，包含 DOC 且无跳过；前端 **20 passed**；ruff、mypy 通过。结果记录提交后恢复真实浏览器验收。

## 真实浏览器前后端联调

后端 8065（DATAAGENT_MODEL_TIMEOUT=120）、Nuxt Python 模式 3001、Agent 3，真实 gpt-6.1-sol、真实 embedding、PostgreSQL t_user/t_order；未启动 Java 后端。首次联调从 a88016f 之后开始；联调发现的问题均先修复、测试、独立复核和提交，再恢复浏览器验收。

- 实际 GMV 请求因知识口径要求排除取消/退款、而表无对应状态字段，以 UNSUPPORTED 明确说明限制及全部订单金额替代查询；未执行无依据 SQL 或伪造报告。
- 采用全部关联订单金额口径，真实 SQL 返回 Alice 199.50、Bob 88.00。完整时间线可见意图、证据、增强、Schema、表关系、可行性、结构化计划、SQL、语义校验、执行及报告；重复执行计划显示“第 2 次”。[时间线截图](python-baseline/assets/ticket07-timeline.png)。
- 联调初期出现重复报告消息，修复 d7ee4d1 后每次运行仅一个稳定 report 消息；真实供应商曾持续输出 tool 字段而达到规划修复上限，修复 8ea7bce 明确 JSON 字段及错误计划上下文后，相同请求成功。失败记录保留，未伪装为完成。
- 最终成功运行 6aa0806a-6db2-4502-83ae-8388506fe6f7，页面正确渲染一份 HTML 报告。[报告截图](python-baseline/assets/ticket07-report.png)。页面“下载 HTML”实际生成 report_20261115161745.html，验证 UTF-8 文档包含 Alice、Bob、199.50、88.00；本地报告读取响应 200、text/html; charset=utf-8，文件名 report.html。
- 重启 Python 后端并刷新浏览器，同一报告仍在；DOM 只有一个报告标题和一个下载入口，未重复补存。
- 同会话仅输入“沿用上一轮的汇总口径，只看 Alice，保留报告”，新 threadId 1698a914-229c-4404-ab90-4cea18187357 读取上一成功计划，真实 SQL 仅返回 Alice 199.50，生成第二份独立报告。[追问截图](python-baseline/assets/ticket07-followup.png)。再次刷新，两份报告各出现一次，两条稳定历史消息键不同；两份本地报告均能以 200 读取。
- 前端开发服务器在测试 prepare 后曾报 app manifest 缓存 404；重启开发服务器后恢复，最终页面无新增浏览器错误。原有 Nuxt 类型检查问题仍保留，未将其作为本票通过证据。

最终后端 60 passed，前端 20 passed，ruff/mypy 通过，双轴审查与联调修复复核完成。完整拒绝重规划、取消/配置保护继续由 Ticket 08 交付，ES/Milvus 等由 Ticket 09 交付。
