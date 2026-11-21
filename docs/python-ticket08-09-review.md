# Tickets 08–09 双轴代码审查

固定起点：42fc913269f090f51db5f59cc2b2ecb1cec65f94。初始总审终点 dad3625，修复复核至 3e9a8d8 / 706002b / e497447。差异命令 git diff 42fc913...HEAD；全部提交可用 git log 42fc913..HEAD --oneline 追溯。Standards 和 Spec 使用两个新的独立上下文子代理并行审查；后续分别复核修复，均只读，未自行运行测试。

## Standards

初始发现 1 项 P3：前端新增 activeRun/stopRun 无 JSDoc，新增图计划字段没有同步到模块文档，违反前端 README 的同步 JSDoc 和 pnpm gen:ctx 要求。

修复：四个运行方法和计划版本字段增加注释并运行生成器；生成器现由 index.ts 拥有模块 README，辅助文件和测试不再覆盖入口文档。graph 文档保留 GraphService/GraphRequest/GraphNodeResponse 和新字段；chat 文档含四个方法。复核：P3 已闭环，无新增可执行问题；Standards 当前无未解决发现。

## Spec

初始发现 1 项 P2：删除清理只识别运行快照的报告链接，未识别迁入消息正文/嵌套 metadata；导致历史独立报告不清理，或者误删其他会话仍引用的共享文件。

修复：删除候选和存活引用检查包含历史正文/元数据；暂存报告写持久文件效果键；新消息/头像引用与清理共用文件生命周期锁，并拒绝已清理文件。HTTP 回归覆盖跨 Agent 历史共享、最后引用删除及迁入历史报告清除。复核：原 P2 闭环，未发现新增具体代码问题。另复核 Java /uploads 前缀迁移，确认路径解码/resolve 后仍受 source-files 边界限制，无阻塞。

Standards 初始 1 项、现未解决 0 项；Spec 初始 1 项、现未解决 0 项。综合 HTTP/真实服务验证由主代理执行，浏览器联调在实现、测试、审查及提交后执行；初始总审之后的最终浏览器联调已完成，见 Ticket 09 验收结论。
