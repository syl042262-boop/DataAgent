# DataAgent

DataAgent 是一个用自然语言查询数据库并生成分析报告的应用。后端使用 FastAPI 和 LangGraph，前端使用 Nuxt 4、Vue 3 和 Vuetify。运行 Python 版只需启动 Python 后端和 Nuxt 前端，以及 MySQL 管理库与 Redis。

## 功能

- 连接 MySQL 或 PostgreSQL 业务库，为智能体选择可查询的表并初始化 Schema。
- 在对话中生成并执行 SQL，查看或下载查询结果和分析报告。
- 配置业务知识、文档和语义模型，为问答补充业务术语和表字段含义。
- 查看历史会话，恢复已保存的运行结果，在需要时审核分析计划或停止查询。

## 用 Docker 启动

安装并启动 Docker Desktop，或准备 Docker Engine 和 Docker Compose 插件。在仓库根目录执行：

```sh
docker compose up -d --build --wait
```

打开 [数据分析工作空间](http://127.0.0.1:3000)。Compose 会启动前端、后端、MySQL 和 Redis，后端会自动执行管理库迁移。MySQL 管理库保存应用配置与运行记录，业务数据通过页面另行连接。在 Docker Desktop 下，容器连接宿主机上的数据库或模型服务时使用 `host.docker.internal`。

```sh
docker compose ps
docker compose logs -f backend
docker compose down
```

## 第一次提问

1. 在「模型配置」添加并测试 OpenAI 兼容的聊天模型与嵌入模型，分别设为默认。
2. 在「数据连接」添加 MySQL 或 PostgreSQL 业务库，并测试连接。查询账号建议只授予所选表的读取权限。
3. 新建智能体，在配置页绑定数据源、选择业务表、初始化 Schema，再发布智能体。
4. 打开智能体的问答页，围绕已选表提问。如已启用访问鉴权，进入问答页后输入该智能体的访问密钥。

## 本地开发

准备 Python 3.12、uv、Node.js 24、pnpm 11、MySQL 8 和 Redis。在 MySQL 中创建独立的空管理库，字符集使用 `utf8mb4`，排序规则使用 `utf8mb4_bin`。将 [环境变量示例](PYTHON/.env.example) 复制为 `PYTHON/.env`，配置 `DATAAGENT_DATABASE_URL` 和 `DATAAGENT_REDIS_URL`。

在第一个 PowerShell 窗口从仓库根目录启动后端：

```powershell
Set-Location PYTHON
uv sync --frozen
uv run uvicorn app.main:app --host 127.0.0.1 --port 8065 --workers 1
```

通过 [后端健康检查](http://127.0.0.1:8065/echo/ok) 确认服务已启动。

在第二个 PowerShell 窗口从仓库根目录启动前端：

```powershell
Set-Location JAVA/data-agent-frontend-nuxt
$env:NUXT_PUBLIC_BACKEND = 'python'
$env:DATAAGENT_PROXY_TARGET = 'http://127.0.0.1:8065'
pnpm install --frozen-lockfile
pnpm dev
```

## 目录

| 路径 | 内容 |
| --- | --- |
| [`PYTHON/`](PYTHON/) | FastAPI 后端、LangGraph 查询流程、数据库迁移和测试 |
| [`JAVA/data-agent-frontend-nuxt/`](JAVA/data-agent-frontend-nuxt/) | Nuxt 前端。保留原目录路径以兼容 Compose 和相关脚本 |
| [`compose.yaml`](compose.yaml) | 本地容器编排 |

前端可运行 `pnpm run test:unit` 和 `pnpm run typecheck`。后端在 `PYTHON/` 下运行 `uv run pytest`，并通过 `DATAAGENT_TEST_DATABASE_URL` 指向允许创建和删除临时库的专用 MySQL 测试实例。部分集成测试还需要 Redis、PostgreSQL 或外部向量服务。

管理库和 `PYTHON/data/` 分别存放业务配置、运行记录和本地文件、工作流检查点及本地知识索引，备份时应同时保留。

## 许可证

本项目基于 [Spring AI Alibaba DataAgent](https://github.com/spring-ai-alibaba/DataAgent)，采用 [Apache License 2.0](JAVA/LICENSE)。
