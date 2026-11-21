# Ticket 08 验证记录（已完成）

实现及增量审查已经覆盖在线审核、取消、对账、配置保护与安全删除；最终全套测试、双轴总审和浏览器联调现已完成；以下过程记录由文末最终结论覆盖。固定审查起点为 42fc913。

审核事件在运行记录、planRevision 和持久化 checkpoint 一致后发布，含完整 plan/threadId/planRevision。拒绝在同一个 threadId 重新规划并递增版本，前置召回不重跑；恢复要求当前凭据、当前配置及卡片版本。前端将计划和版本绑定同一卡片，重新进入会话读取 active-run，停止按钮支持运行和待审核。

运行配置使用无密钥明文的有效指纹，覆盖数据源身份、选表、关系、提示词、模型、知识内容/索引/召回状态及外部存储身份。纯名称/头像和正常凭据轮换不改变空间；每个外部操作前重新鉴权及校验配置。旧 key 立即失败，需要新 key 继续访问。已经不确定的 SQL 不因配置错误而被误判为已停止。

stop 必填 agentId/conversationId，可选 threadId，当前 key 和归属一致后成功 204。待审核立即终结；执行中先 CANCELLING，只有 native stop 的实际成功及执行线程观察到结束才能释放占用。MySQL KILL CONNECTION、PostgreSQL pg_terminate_backend 分别使用真实数据库验证；真实 HTTP/SSE 断开也会触发停止并等待同步 SQL 工作结束。

启动对账核对 saver、运行、效果及 worker 的主机/PID/进程创建时间。只有一致审核 checkpoint 且停止证据满足才恢复等待；仅依靠过期 Redis 锁不能证明进程停止。已提交结果在原 worker 确认停止、无 IN_FLIGHT 时修复终态，保留原快照，不重发 SQL；SUCCESS 提交记忆，EARLY_END/UNSUPPORTED/FAILED/CANCELLED 丢弃当前轮。CANCELLING 仅接受已提交 CANCELLED 快照，其余矛盾保留对账占用。

本机运维入口：

- `python -m app.operations inspect --thread-id ID`：查看状态/version、checkpoint、worker 及不确定效果/查询 ID。
- `python -m app.operations resolve-failed --thread-id ID --expected-version N --operator NAME --reason TEXT`：仅对 RECOVERY_REQUIRED 收尾，要求原 worker 及原数据源中的在途查询确已结束、版本匹配。写审计并以 FAILED 释放占用；相同参数重复执行返回原结果。不得靠强制 HTTP 恢复或任意清理 Redis 锁替代。

删除单会话、清空 Agent 会话、删除 Agent 共用 Agent 后会话的锁顺序。范围内有任何非终态则整体 409；空闲时同事务写逻辑删除及持久化 cleanup job。晚到消息/反馈不能重建对象。checkpoint、MySQL 运行/结果/记忆/消息/效果、外部向量及文件清理可重复执行；失败保留任务，启动和每 5 秒重试。同步 SQL/文件/外部 HTTP 及知识锁均在线程池，不能阻塞事件循环。共享文件只有无存活引用时删除。

## 验证证据与界限

此前 9 项 review HTTP 测试通过，涵盖拒绝/旧版本/重启接受、摘要、配置/密钥、待审核 stop、实际 MySQL native stop、真实 uvicorn 断流、实际子进程 kill 与 CLI 版本/重复收尾，以及 SQL 超时和配置变更共同发生的不确定执行。

本次补充 4 项通过：真实 PostgreSQL pg_sleep 执行中 stop、数据库 PID 消失后 CANCELLED/释放占用/允许删除；已提交 SUCCESS、EARLY_END、UNSUPPORTED 快照周围非终态残留的启动修复。这三项采用明确的存储故障注入和一个实际退出的本机 worker 进程，HTTP 验证快照原样、占用释放和模型调用数不增加；它们不冒充真实崩溃窗口，真实 kill 场景由前述 CLI 测试单列覆盖。

前端 unit tests 此前 20 项通过。Nuxt 全局 typecheck 存在前序模型配置引用、服务导入导出、markdown/test 类型错误，不能称全局通过。最终浏览器重启刷新/重新输入凭据/接受与拒绝等交互尚待按用户要求在所有代码流程完成后执行。

### 总审修复：历史与暂存报告的文件生命周期

清理候选现在包含展示消息正文和嵌套 JSON metadata 的本地文件引用；存活会话的引用会阻止共享文件删除。报告在最终快照之前以稳定 `v1:report_file:main:0` 效果键登记文件引用，防止另一个清理任务删除已写入、尚未发布结果的同内容文件。报告写入/登记、新消息补存和头像引用写入与清理共用知识文件生命周期锁。

HTTP 回归验证：生成报告后另一个 Agent 的两个无运行历史会话分别以 metadata 和正文共享引用；删除原 Agent 后仍可读取；逐个删除历史会话，最后一个引用删除后文件 404。迁入历史报告也验证删除历史会话后文件清除，而仍被知识/头像引用的其他文件保留。已清理的本地文件不能通过晚到消息或头像引用重新发布，写入返回 400；需重新上传有效文件。

## 最终状态

最终后端全套 102 passed、前端 20 passed/typecheck、双轴审查和最后浏览器联调均通过。浏览器实际重启后恢复、拒绝/再重启/接受、密钥刷新及轮换、追问、待审核取消和空闲会话删除均有记录，详见 Ticket 09 的最终结论与截图。所有实现已提交；本票状态完成。
