# DataAgent Python — Tickets 01–09 已完成

独立 FastAPI 服务。无需启动 Java；管理库和 saver/文件目录独立。当前已完成 Tickets 01–09：模型与 Agent 管理、访问密钥、预设问题、MySQL/PostgreSQL 数据源与绑定选表、持久化 LangGraph 查询闭环、提示词与逻辑关系、会话历史和最终结果找回，以及业务知识、语义模型、知识文档、本地文件和持久化检索。完整规划、Schema/关系选择、有限 SQL 修复、流式 HTML 报告、下载及成功轮次跨轮记忆已在 Ticket 07 完成；完整版本审核、刷新恢复、原生取消/对账、配置及删除保护由 Ticket 08 完成；ES/Milvus、隔离迁移和最终联调由 Ticket 09 完成。

| Ticket | 状态与验收 |
| --- | --- |
| 01 独立骨架、模型配置及契约 | [已完成](../docs/python-ticket01-validation.md) |
| 02 Agent 与 MySQL 配置 | [已完成](../docs/python-ticket02-validation.md) |
| 03 持久化 MySQL 查询闭环 | [已完成](../docs/python-ticket03-validation.md) |
| 04 PostgreSQL、提示词与逻辑关系 | [已完成](../docs/python-ticket04-validation.md) |
| 05 会话历史与结果找回 | [已完成](../docs/python-ticket05-validation.md) |
| 06 知识、文件及本地检索 | [已完成](../docs/python-ticket06-validation.md) |
| 07 规划、SQL 修复、报告与跨轮记忆 | [已完成](../docs/python-ticket07-validation.md) |
| 08 审核、取消对账、配置与删除保护 | [已完成](../docs/python-ticket08-validation.md) |
| 09 ES/Milvus、迁移与最终验收 | [已完成](../docs/python-ticket09-validation.md) |

## Ticket 02 配置流程

前端在 `JAVA/data-agent-frontend-nuxt` 运行前设置 `$env:NUXT_PUBLIC_BACKEND='python'`，然后 `npm run dev`。默认值 `java` 保留原模式；切回时移除此环境变量并重启前端。新建 Agent 后，在管理列表点击“配置”，或进入 `/agent/{id}`：保存信息、发布/下线、生成或重置密钥、启用/关闭鉴权、设置每行一个预设问题。问答页点击预设问题只填入输入框。删除 Agent 和历史清理已完成，存在非终态时整体返回 409。

在“数据连接”新增 MySQL 数据源并测试，在 Agent 配置页绑定、选择表、保存并初始化 Schema。初始化读取真实表列并将快照保存到 `python_agent_schema`，供后续查询使用；知识本地检索由 Ticket 06 接入。改选表、重新绑定、修改数据源会清除旧快照；解绑和删除数据源通过外键清理选表及快照。绑定会激活该源并关闭其他源，重复绑定沿用 Java 行为清空原选表。toggle 启用时存在其他活动源会拒绝，须先禁用。PostgreSQL 已在 Ticket 04 完成连接、元数据与方言查询；其他类型明确拒绝。

连接默认使用结构化主机/端口/数据库与独立凭据。MySQL 可填写 `jdbc:mysql://HOST:PORT/DB` 或 `mysql://HOST:PORT/DB`；URL 中主机/端口/数据库优先。允许参数：`characterEncoding=UTF-8|utf8|utf8mb4`、`connectTimeout`/`socketTimeout`（1–180000 毫秒，转换为秒向下取整、最少 1 秒）、`useSSL=true|false`、`useUnicode=true`。SSL=true 使用系统信任链验证证书；未知参数、重复参数、URL 内嵌用户密码被拒绝，不静默忽略驱动参数。列表和详情的密码为 `******`，编辑保留该值或不传密码会保留原密码；数据库密码由管理库保护，不作为公开连接 URL 的一部分。

Agent 密钥只在生成/重置返回完整值，其他响应脱敏；新密钥由安全随机数生成，管理库仅存 SHA-256 摘要。Python 新增 `GET /api/agent/{id}/access` 用于凭据预检：X-API-Key 优先于 Authorization Bearer，启用鉴权时无效凭据 401、不存在 Agent 404、关闭鉴权放行。运行页手动输入密钥，只保存在模块内存，刷新需重输。查询、标题流及运行结果找回已携带凭据头并校验归属；停止与取消已在 Ticket 08 完成，含待审核任务取消及真实 SQL 原生终止。Java bcrypt/legacy 密钥兼容和隔离复制由 Ticket 09 的迁移 CLI 验证；模型密钥与 Agent 访问密钥分别管理。

本机保留 `dataagent_ticket02_demo.sales` 与只读演示用户供页面继续体验，和 `dataagent_python` 管理库分离。验收见 [Ticket 02](../docs/python-ticket02-validation.md)。

## Docker 一键启动

安装并启动 Docker Desktop（使用 Linux 容器），或准备 Docker Engine 和 Docker Compose 插件。在仓库根目录执行：

```sh
docker compose up -d --build --wait
```

启动后打开 `http://127.0.0.1:3000`。Compose 会启动 Nuxt、FastAPI、MySQL 和 Redis，自动执行管理库迁移；无需启动 Java，也不需要宿主机安装 Python 或 Node。首次构建需要联网下载镜像和依赖。

- 首次使用请在页面的「模型配置」添加并激活模型，并在「数据连接」配置业务库。内置 MySQL 是独立的管理库，不预装业务数据。Docker Desktop 下连接宿主机数据库或模型服务时，用 `host.docker.internal`，而不是 `localhost`。
- 默认使用本地向量存储，不启动 Elasticsearch 或 Milvus。业务数据源 PostgreSQL 和旧版 `.doc` 解析所需的 Java/Tika 不包含在默认部署中。
- 仅前端端口对本机开放。端口冲突时，可在仓库根目录的 `.env` 设置 `DATAAGENT_WEB_PORT=3001`。首次启动前也可设置 `DATAAGENT_MYSQL_PASSWORD`（使用字母、数字、下划线或连字符），替换默认的本地开发密码；修改配置不会自动更改已有数据库卷里的密码。
- 查看状态：`docker compose ps`；查看日志：`docker compose logs -f`；停止：`docker compose down`。管理库、Redis、Python checkpoint 和上传文件保存在命名卷中；不要使用 `docker compose down -v`，除非要清空这些数据。

## 本机启动

需要 Python 3.12、uv、MySQL 8 和 Redis（运行协调）；PostgreSQL 查询另需可连接的业务库。创建专用空库（utf8mb4/utf8mb4_bin），复制 `.env.example` 为 `.env` 后配置 `DATAAGENT_DATABASE_URL`；不要指向 Java 或业务查询数据库。管理库用户需本库 DDL/DML 权限。然后在 `PYTHON/`：

```powershell
uv sync --frozen
uv run uvicorn app.main:app --host 127.0.0.1 --port 8065 --workers 1
```

只支持单 worker，不使用 `--reload` 承载正式运行。启动以 MySQL 命名锁串行执行有校验和的幂等迁移，再初始化本地 SQLite saver；失败会中止启动。关闭释放 saver 和连接池。`GET http://127.0.0.1:8065/echo/ok` 返回 `ok`。`data/` 保存 checkpoint；管理库和目录都应备份，不能只备份其中一个。

本次验收已创建本机容器 `dataagent-ticket01-mysql`，映射 `127.0.0.1:13306`，当前 `.env` 指向其中独立的 `dataagent_python` 库。容器停止后可用 `docker start dataagent-ticket01-mysql` 恢复；不要删除容器后期待其中配置仍在。

模型配置页兼容原接口：关闭 Java 8065 服务，进入 `JAVA/data-agent-frontend-nuxt` 启动前端，访问 `http://localhost:3000/system/model-config`；原代理指向 8065。管理页面可以保存、编辑、删除非激活模型、设置默认及连接测试；Java 后端源码未修改。切回 Java 时停止 Python 并按 JAVA/README 启动 Java。同一时间只让一个后端占用 8065；查询图与会话历史已可使用；知识与文件接口已在 Ticket 06 完成。

## 模型配置

Ticket 06 已完成的知识模块使用激活的 EMBEDDING 配置，正文和召回设置分别持久化。本地文件与 `knowledge.sqlite` 和管理库一起备份。旧版 DOC 需要 Java 17+，先执行 `uv run python tools/install_doc_parser.py` 安装经官方 SHA-512 校验的 Tika 3.3.3；默认路径 `data/tools/tika-app-3.3.3.jar`，可用 `DATAAGENT_TIKA_APP_JAR` 指定位置。PDF、DOCX、TXT、MD 不依赖 Java。扫描 PDF 无可提取文字时返回失败，不自动 OCR。细节见 [Ticket 06 验证记录](../docs/python-ticket06-validation.md)。

页面配置 CHAT、EMBEDDING 各一个：baseUrl 和模型路径直接拼接；例如 baseUrl `https://api.example.com` 配 `/v1/chat/completions`，baseUrl 已带 `/v1` 时配 `/chat/completions`。API key 由服务端持久化，列表脱敏，编辑时保留掩码可复用旧 key。新增未激活，设置默认只切换同类型；连接测试才发真实请求。check-ready 检查激活配置存在，不代表外部服务永远可用。

与 Java 一致，已激活 embedding 的 provider/baseUrl/modelName/embeddingsPath 不允许直接改变，其他模型空间也不能热切换为默认；需要新版本向量集合及重建流程（后续检索 tickets）。`DATAAGENT_EMBEDDING_DIMENSION` 默认 0，表示不检查维度；设正数后，连接测试拒绝不同维度向量。凭据轮换不改变模型空间。

如使用已有项目的 `.env`，可通过验收命令导入并调用模型（不会打印密钥）：

```powershell
uv run python tools/accept_real_models.py --source-env .env
```

脚本识别 OPENAI_BASE_URL、OPENAI_API_KEY、LLM_MODEL，以及 EMBEDDING_BASE_URL、EMBEDDING_API_KEY、EMBEDDING_MODEL。它通过公开 HTTP 完成保存、测试和激活。秘密只保存在被忽略的 `.env` 和本机管理库中；不要提交或分享数据库转储。正式配置来源是管理页面/数据库，env 仅用于启动和显式验收导入，不会在启动时覆盖页面配置。

## 检查

HTTP 测试创建随机 MySQL schema，结束后删除；需测试服务器的 CREATE/DROP DATABASE 权限，切勿使用生产凭据。

```powershell
$env:DATAAGENT_TEST_DATABASE_URL='mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/?charset=utf8mb4'
uv run pytest
uv run mypy app tools
uv run ruff check app tests tools
uv run python tools/verify_saver.py
uv run python tools/build_baseline.py
```

测试通过 HTTP 验证真实 MySQL 的重启持久化、密钥保留、两种模型调用、配置类型约束、激活/删除及错误脱敏；外部供应商边界使用可控 HTTP 服务。真实供应商及页面验证单独记录在 [验收记录](../docs/python-ticket01-validation.md)。

[完整契约矩阵](../docs/python-baseline/http-contracts.md)、[DTO](../docs/python-baseline/schemas.md)、[13 表对账](../docs/python-baseline/storage-audit.md)、[公共运行/恢复契约](../docs/python-runtime-contract.md)。001 保留 13 表 MySQL 基线，002 创建运行/记忆/效果/结果/删除闸门等基础表；saver 框架表独立管理。无演示 Agent、假模型或真实密钥种子；存量复制由 Ticket 09 负责。

## 外部向量存储（Ticket 09 已完成）

默认 `DATAAGENT_VECTOR_BACKEND=local`。选择 `elasticsearch` 或 `milvus` 时，设置 `DATAAGENT_VECTOR_URL`（ES HTTP 9200；Milvus REST 19530）、独立的 `DATAAGENT_VECTOR_NAMESPACE` 和可选 `DATAAGENT_VECTOR_TOKEN`。URL 不得包含凭据或 query。每个 embedding 空间/维度使用单独集合。配置和密钥只保存在本机 `.env`。

切换存储或 embedding 空间后，通过 `POST /api/agent/{id}/knowledge/rebuild` 重建，携带该 Agent 的访问凭据。只恢复数据库或远端服务的一部分不能代表恢复成功；管理库、本地 `data/` 和外部索引应一致备份。远端丢失会明确失败并将受影响记录标记 FAILED；重试 embedding 可恢复。外部服务失败不会静默回退 SQLite。重建前应确保旧目标可清理；新目标凭据不会发送到旧目标，旧目标需要鉴权时先恢复旧配置完成清理。

真实 ES/Milvus 的适配、HTTP、迁入真实 embedding 重建及最后浏览器查询/报告均通过；见 [Ticket 09 验收记录](../docs/python-ticket09-validation.md)。

## 离线 Java 副本导入（Ticket 09）

先停止目标 Python 服务，准备全新的专用管理库和独立 `DATAAGENT_DATA_DIR`。将 Java 管理库复制到另一个 MySQL schema；源连接使用只读账户，不能让两个应用共享写库。源数据库必须包含全部 13 张业务表。不要把业务查询库当管理源库。Java 无存量数据时，可在独立 schema 执行仓库的 `JAVA/data-agent-management/src/main/resources/sql/schema.sql` 和 `data.sql` 建立示例副本；示例的数据库主机/连接参数必须在管理页面重新配置。

在 `PYTHON/` 的本机环境配置 `DATAAGENT_MIGRATION_SOURCE_URL`（指向副本，不要把含密码的命令保存到脚本或提交），目标仍由 `.env` 中的 `DATAAGENT_DATABASE_URL` 决定。执行：

```powershell
uv run python -m app.migration --source-files D:/migration/java-files
uv run python -m app.migration --source-files D:/migration/java-files --apply
```

第一条只检查源快照和知识文件，输出 `VALIDATED` 与 `validationScope=SOURCE_SNAPSHOT_AND_FILES`，不保证目标约束检查一定成功。第二条初始化目标迁移并原子导入业务行及导入报告。源库用只读一致性快照；同一 MySQL server UUID/库名的源与目标被拒绝。目标业务、运行、删除墓碑、知识状态以及 saver/index 数据必须为空；不能复用一个曾运行并删除过 Agent 的库。失败回滚业务行，修正问题后可重复命令；相同源内容/文件摘要重复执行返回 ALREADY_IMPORTED，不覆盖已有目标业务数据。

13 张业务表保留 ID、时间、外键和字段；新增 `python_data_import` 保存不含密钥值的表计数/策略/摘要。Java legacy Agent key 转 SHA-256 摘要，默认 `{bcrypt}…::尾号` 保留 bcrypt 校验并移除显示后缀；未知编码明确失败，先在源副本旋转该 key。Python 新生成 key 仍使用 SHA-256。数据源密码和模型凭据按原值复制，必须通过连接测试验证可用；不能把密文当明文可用来宣称迁移成功。

知识文件必须位于 `--source-files` 内，迁入内容寻址目录；活跃文件缺失或越界会中止，已逻辑删除文档不要求旧文件存在。知识文件、头像及历史正文/嵌套 JSON metadata 中的本地上传链接均改写为新内容寻址 URL；外部 URL 不下载。所有知识状态变为 FAILED 并提示重建，不能复用 Java 向量。Java 框架记忆/checkpoint 表只列入 excludedTables，不导入；Python 模型记忆明确从新的成功轮次重建，展示历史保持可读，历史 PYTHON 文本不会产生执行状态或新运行。当前检索允许 local/ES/Milvus 重建；综合真实模型验收见进行中的 Ticket 09 记录。


### 离线 embedding 空间切换

在线页面的不同 embedding 空间热切换仍会拒绝。需要更换模型时，先通过模型配置页新增目标 EMBEDDING 配置并测试，停止 Python 服务，再在相同 .env/数据目录执行 `uv run python -m app.vector_operations --model-id ID`。

命令拒绝未结束运行和未完成清理。它保留旧状态及旧向量，先在独立空间完整暂存所有知识，再核对内容版本及模型配置，同一个 MySQL 事务发布全部知识版本并切换默认模型。失败保留旧默认和旧召回，可重试。SQLite 按空间保存多版本，远端按空间/维度分集合；旧版本保留到对应知识重建或删除时清理。暂存不能覆盖当前发布空间；同模型重新索引用知识 rebuild 接口，切换后端时选择新 namespace。维护完成后再启动单 worker 服务。

该命令是停服维护协议；不要在另一个 Python 进程仍提供写请求时运行。

最终验收：后端 102 项、前端 20 项、全局 typecheck、ruff/mypy 和独立进程 saver 均通过。原 98 个映射有逐接口实际调用证据；双轴审查已闭环，并在提交后完成浏览器联调。Java 后端源码未修改；本次不启动未配置的 Java 服务。迁移数据来自仓库 SQL 示例副本，不代表生产存量。
