# Ticket 06 验证记录

日期：2026-11-15。范围：业务知识、语义模型、知识文档、本地文件及查询证据召回。

## 实现与契约

原接口 20–26、30–37、62–63、87–97 已实现，仍使用原 URL、multipart 字段和响应包裹。业务知识的内容编辑不修改召回开关；文档更新保留 question，只允许 title/content。语义模型绑定 Agent 当前活动数据源（没有活动源时沿用 Java 首个绑定源）；JSON/Excel 按 Agent、表、字段更新已有记录，保留已有启停状态。模板为原模板的独立副本，不依赖 Java 运行或 Java 目录。

新增管理扩展：`GET/PUT /api/agent/{id}/knowledge/recall-config` 保存独立 topK、similarityThreshold 与修订；`POST /api/agent/{id}/knowledge/rebuild` 重建三类本地索引并报告失败项；`POST /api/agent/{id}/knowledge/search` 只读召回。search/rebuild 使用 Agent 当前凭据校验，管理配置沿用原本机管理范围。Python 模式的业务知识和文档页增加召回设置。

本地索引为 `DATAAGENT_DATA_DIR/knowledge.sqlite`，上传文件为 `files/` 下内容寻址对象。管理库 `python_knowledge_state` 保存记录归属、内容修订、已发布索引修订、embedding 空间与失败状态；`python_recall_config` 独立保存召回配置。索引命中须匹配当前有效记录、修订、空间及召回开关；语义字段还须匹配当前数据源与选表。新状态纳入 effective-config 指纹，供 Ticket 08 配置变化保护使用。

先持久化 PENDING，再构建/原子替换本地索引，最后发布 COMPLETED；失败保留内容并排除旧向量，重启时未完成构建转 FAILED。单 worker 用同一锁串行化内容构建、删除与检索，避免旧构建覆盖新记录。索引包含确定的记录/分块键，重建不会追加重复分块。`cleanup_unreferenced_file` 为 Ticket 08 提供可重试清理边界：检查未删除知识和头像引用后才删除本地对象，共享知识引用仍在时保留文件。

文档支持页面原有 PDF、DOC、DOCX、TXT、MD 及 markdown。PDF/DOCX 使用 Python 解析器；DOC 使用经官方 SHA-512 校验的本地 Tika 3.3.3 JAR（需要 Java 17+，无需 Java 后端服务）。未安装解析器、空文件、损坏文档、无文本扫描 PDF、超限上传和 embedding 错误均明确失败。支持 token、recursive、sentence、paragraph、semantic 五种分块；semantic 使用激活 embedding 比较相邻句子。扫描 PDF 不自动 OCR。

显式差异：索引操作在当前请求内完成，响应可直接观察 COMPLETED/FAILED；没有模拟 Java 的后台处理进度。文件 URL 为 `/api/upload/files/{path}`，文件只读 URL 来自上传响应。头像验证实际图片内容，读取返回 MIME、原始文件名和 nosniff。查询流复用原 `EvidenceRecallNode` 节点名，JSON 证据进入 checkpoint 和 SQL 模型上下文；完整查询增强/规划分支仍由 Ticket 07 交付。

## 检查

- 知识专项：12 项，最终全量运行全部通过；真实 MySQL、SQLite、受控供应商 HTTP 边界；包括五种分块 × 四种格式、真实 Tika DOC、XLS/XLSX、部分导入及数据库错误、embedding 401 后重试、共享文件删除、重启、HTTP/SSE 证据、选表过滤和页面空筛选请求。
- 前端现有单测：20 passed。全局 TypeScript 检查仍有原有错误（model-config 等页面的 `.value`、服务导入及历史类型问题），本票新增组件和修改的知识页面未出现类型报错。
- 最终后端全量 44 passed，ruff、mypy 通过；前端 20 passed。最终全局 TypeScript 检查仍为 25 项既有错误，本票新增/修改组件与知识页面无类型报错。原模板缺少默认样式的 openpyxl 警告及既有 SQLAlchemy 弃用警告不影响测试。
- 真实 embedding：使用管理库已激活配置，通过 HTTP 保存 GMV 和办公时间两条知识，销售额问题的第一名为 GMV；验证了实际供应商返回的向量与本地相似度排序。
- [双轴审查](python-ticket06-review.md) 已完成且修复复核通过。浏览器联调在审查和修复提交 `7164169` 完成后开始。

## 浏览器前后端联调

使用 Python 后端 8065、Nuxt Python 模式 3001（原有 3000 已被占用），验收 Agent 3。真实模型、真实 embedding、真实 PostgreSQL `t_order/t_user`。

- 业务知识页保存 topK=6、similarityThreshold=0.15，刷新和跨知识页面读取相同配置；创建“净成交额”术语，页面显示真实 embedding COMPLETED。
- 文档页上传 Markdown，显示 COMPLETED 与已召回；页面改名为“销售额口径说明（修订）”。重启后文件引用、内容和列表仍可读取。[截图](python-baseline/assets/ticket06-documents.png)。
- 语义模型页点击下载原 Excel 模板，填写 `t_order.amount / 实际支付金额 / decimal` 后从页面上传导入，列表显示启用字段。[截图](python-baseline/assets/ticket06-semantic.png)。
- 新建 Agent 页面先上传蓝色 PNG 再更换红色 PNG，返回不同本地地址和 image/png；创建 Agent 4 后公开详情保留同一红色头像 URL。
- 问答页提出按用户名汇总 GMV，SSE 中实际召回语义字段、文档及业务术语，真实 PostgreSQL 返回 Alice 199.50、Bob 88.00；刷新后同一结果仍可找回。[截图](python-baseline/assets/ticket06-query.png)。
- 首次真实模型请求在默认 30 秒超时处明确失败，未伪装为成功；本次验收进程设 `DATAAGENT_MODEL_TIMEOUT=120` 后同一查询成功。模型较慢时启动前设置该参数；未将凭据或本机环境写入仓库。

联调发现并修复页面空筛选值契约：类型 `""` 应表示不筛选；新增精确 HTTP 回归。提交 `534c525` 经 Spec 复核后继续联调。时间线补充结构化证据的可读显示，仅展示知识类型与内容，不向普通问答页面展示索引指纹；`149af2d` 再次复核无问题后继续联调。

本地 Tika 验证样例来自 [Apache Tika 的测试资源](https://github.com/apache/tika/tree/main/tika-parsers/tika-parsers-standard/tika-parsers-standard-modules/tika-parser-microsoft-module/src/test/resources/test-documents)，仅保存在被忽略的 data/acceptance 下；JAR 与校验和来自 [Apache 官方发行目录](https://downloads.apache.org/tika/3.3.3/)。
