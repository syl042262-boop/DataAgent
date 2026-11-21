# Ticket 07 双轴代码审查

起点：用户确认的 `6ea5e0f`。实现：`1f9558a`、`8f44e3e`；修复：`ff2ed16`、`38d0a01`。按 code-review 技能运行独立 Standards、Spec 子代理；修复均独立复核。

## Standards

无文档规范违规。发现模型规划位于 interrupt 前会在恢复时重新生成计划，可能批准不同计划。已拆为持久化 Planner 输出后的独立 HumanFeedbackNode；HTTP 重启回归确认同一 threadId 恢复、计划非空、Planner 模型仅请求一次。复核无阻塞。

关于 nl2sqlOnly 进入 SQL 执行的初审疑点已撤销：Java PlannerNode 生成固定单 SQL 计划，SemanticConsistenceDispatcher 仍进入 SQL 执行，PlanExecutor 仅跳过报告，SqlExecute 仅跳过可选图表。当前实现保留原语义。

非阻塞维护建议：流式和非流式模型传输存在配置代码重复；规划参数验证重复选择工具对应字段。当前两种工具及两种传输路径规模有限，暂保留直接实现。

## Spec

初审三项均已修复：多 SQL 步骤独立维护重试预算；Schema 模型召回与关系节点授权表补充、失败上限；空增强结果提前结束。复核又发现空 Schema 召回应正常提前结束，已修复并补 HTTP/SSE 回归。11 条 SQL 计划成功、未授权关系补充四次后终止、空增强和空 Schema 都以 EARLY_END 持久化后 complete。

`38d0a01` 复核：未发现剩余阻塞项。

最终：Standards 0 项规范违规、1 项正确性问题已修复、2 项非阻塞建议；Spec 4 项问题已修复、0 项未解决。测试、复核及记录提交完成后才进入前后端联调。

联调追加：真实报告完成后发现快照同时保存 HTML 原文文本和渲染报告，页面出现重复内容。`d7ee4d1` 改为报告存在时仅保留稳定 report 消息键，finalAnswer 事实字段不变；HTTP 回归先失败后通过，独立 Spec 复核无阻塞。追加报告供应商 HTTP 500、SQL 空结果的入口回归也通过。

真实供应商随后返回 tool 而非 tool_to_use，四次均被严格校验拒绝。`8ea7bce` 补齐默认 JSON 字段示例，并将被拒计划和具体契约带入修复上下文；可控 HTTP 回归证明第二次能够修复。Spec 独立复核无阻塞。`05fe7dc` 为带报告引用的 HTML 消息增加原接口下载入口，Standards 与 Spec 均复核通过，前端 20 项单测通过，修改组件无新增类型错误。
