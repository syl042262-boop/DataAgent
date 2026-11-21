"""Rebuild reviewable Java contract/schema evidence without running Java.

The output is a source baseline, not a claim of runtime parity for future tickets.
"""

import hashlib
import json
import re
from pathlib import Path

import sqlparse

ROOT = Path(__file__).resolve().parents[2]
JAVA = ROOT / "JAVA/data-agent-management/src/main"
PACKAGE = JAVA / "java/com/alibaba/cloud/ai/dataagent"
OUTPUT = ROOT / "docs/python-baseline"


def balanced(source, start, opening, closing):
    depth = 0
    tokens = re.finditer(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*|[{}()]', source[start:]
    )
    for token in tokens:
        value = token.group()
        if value == opening:
            depth += 1
        elif value == closing:
            depth -= 1
            if depth == 0:
                return start + token.end()
    raise ValueError("Unbalanced Java source")


def compact(source):
    return re.sub(r"\s+", " ", source).strip().replace("|", "\\|")


def owner(number):
    groups = {
        1: [61, *range(66, 73)],
        2: [*range(1, 5), *range(6, 20), *range(27, 30), *range(47, 56)],
        3: [38, 39, 64],
        4: [*range(56, 61), *range(73, 87)],
        5: [41, 42, 43, 44, 98],
        6: [*range(20, 27), *range(30, 38), 62, 63, *range(87, 98)],
        7: [46],
        8: [5, 40, 45, 65],
    }
    return next(ticket for ticket, numbers in groups.items() if number in numbers)


def build_contracts():
    inventory = (ROOT / "docs/python-backend-api-inventory.md").read_text(encoding="utf-8")
    rows = re.findall(r"\| (\d+) \| (\w+Controller) \| (\w+) \| `([^`]+)`", inventory)
    assert len(rows) == 98
    controllers = {}
    schema_names = set()
    matrix = [
        "# 98 个接口契约矩阵\n",
        "由 `PYTHON/tools/build_baseline.py` 从当前 JAVA 源码重建。编号对应原清单；主交付归属按当前 01–09 本地任务索引维护。01–07 已交付，08 实施中，最终逐接口/真实副作用验收由 09 汇总；本源码矩阵本身不证明运行时兼容。\n",
        "参数栏保留完整绑定注解：PathVariable=路径，RequestParam=查询，RequestBody=JSON，RequestPart=multipart；required 未写默认为 true，required=false 的引用类型默认为 null、boolean 为 false。defaultValue 如实保留。DTO 字段/校验/初值见 [schema catalog](schemas.md)。返回类型中的泛型是准确响应包裹，Map 的具体字段见逐接口返回分支。\n",
        "Python 绑定/验证错误约定 HTTP 400；Java GlobalExceptionHandler 的 generic Exception 分支为 500，见下方完整源码，属于显式差异。管理接口未增加鉴权（开放本机管理）；search 使用当前 Agent key，Python 的 stop/标题/运行扩展增加同样鉴权，详见 [公共协议](../python-runtime-contract.md)。全局异常分支和逐路由返回分支附后，不能把 ApiResponse.error 的 HTTP 200 当成功。日期/字段别名以 schema catalog 注解为准，null 保留，分页字段不得更名。\n",
        "|编号|方法/路径|Ticket / Python状态|参数与DTO|响应类型|HTTP/错误|鉴权|业务效果入口|前端消费|\n|---:|---|---|---|---|---|---|---|---|",
    ]
    details = ["\n## 逐接口返回和错误分支\n"]
    consumer = {
        "AgentController": "agent",
        "AgentDatasourceController": "agentDatasource",
        "AgentKnowledgeController": "agentKnowledge",
        "AgentPresetQuestionController": "presetQuestion",
        "BusinessKnowledgeController": "businessKnowledge",
        "ChatController": "chat",
        "DatasourceController": "datasource",
        "EchoController": None,
        "FileUploadController": "fileUpload",
        "GraphController": "graph",
        "ModelConfigController": "modelConfig",
        "PromptConfigController": "prompt",
        "SemanticModelController": "semanticModel",
        "SessionEventController": "sessionStateManager",
    }
    evidence = []
    for number_text, name, verb, path in rows:
        number = int(number_text)
        file = PACKAGE / "controller" / (name + ".java")
        source = file.read_text(encoding="utf-8")
        if name not in controllers:
            controllers[name] = iter(re.finditer(r"@(Get|Post|Put|Delete)Mapping\b", source))
        mapping = next(controllers[name])
        method = re.search(r"\bpublic\s+([^;{]+?)\s+(\w+)\(", source[mapping.end() :])
        assert method
        param_start = mapping.end() + method.end() - 1
        param_end = balanced(source, param_start, "(", ")")
        body_start = source.index("{", param_end)
        body_end = balanced(source, body_start, "{", "}")
        params = source[param_start + 1 : param_end - 1]
        body = source[body_start:body_end]
        returns = method.group(1)
        fn = method.group(2)
        imports = re.findall(
            r"import com\.alibaba\.cloud\.ai\.dataagent\.(?:dto|entity|vo)\.([\w.]+);", source
        )
        for imported in imports:
            schema_names.add(imported.split(".")[-1])
        calls = sorted(set(re.findall(r"\b(\w+(?:Service|Util))\.(\w+)\(", body)))
        effects = "; ".join(".".join(c) for c in calls) or ("只读健康检查" if number == 61 else fn)
        statuses = {200}
        for marker, status in [
            ("badRequest", 400),
            ("notFound", 404),
            ("internalServerError", 500),
            ("noContent", 204),
            ("InternalServerException", 500),
            ("InvalidInputException", 400),
            ("INTERNAL_SERVER_ERROR", 500),
            ("NOT_FOUND", 404),
        ]:
            if marker in body:
                statuses.add(status)
        if number == 65:
            statuses.discard(200)
        if "checkAgentExists" in body or "checkDatasourceExists" in body:
            statuses.add(404)
        if "status(403)" in body:
            statuses.add(403)
        auth = (
            "Java Agent key；401"
            if number == 64
            else (
                "Java 无；Python 增加 Agent key/401"
                if number in (40, 41, 42, 43, 44, 45, 46, 65, 98)
                else "无（本机管理）"
            )
        )
        service_dir = consumer[name]
        frontend = (
            "无（运维探活）"
            if service_dir is None
            else f"[services/{service_dir}](../../JAVA/data-agent-frontend-nuxt/app/services/{service_dir}/index.ts)"
        )
        state = "已交付；最终验收见09" if owner(number) <= 7 else "实施中；待最终验收"
        status_text = "/".join(map(str, sorted(statuses)))
        if "ApiResponse" in returns or "Map<" in returns:
            status_text += "; 200 success=false 业务错误"
        matrix.append(
            f"|{number}|{verb} `{path}`|{owner(number):02} / {state}|`{compact(params) or '无'}`|`{compact(returns)}`|{status_text}|{auth}|{effects}|{frontend}|"
        )
        # Exact body includes status branches, Map fields, MIME/headers, filters and defaults.
        details.append(
            f"\n### {number}. {fn}\n\n```java\n{source[mapping.start() : body_end].strip()}\n```\n"
        )
        evidence.append(
            {
                "id": number,
                "method": verb,
                "path": path,
                "ticket": owner(number),
                "parameters": compact(params),
                "response": compact(returns),
                "http": sorted(statuses),
                "source": file.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(source.encode()).hexdigest(),
            }
        )
    handler = (PACKAGE / "controller/GlobalExceptionHandler.java").read_text(encoding="utf-8")
    details.append(
        "\n## Java 全局错误处理基线\n\n```java\n"
        + handler[handler.index("@RestControllerAdvice") :]
        + "\n```\n"
    )
    (OUTPUT / "http-contracts.md").write_text("\n".join(matrix + details), encoding="utf-8")
    (OUTPUT / "http-contracts.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    catalog = [
        "# DTO、实体及响应字段基线\n",
        "完整字段类型、约束、默认值、JSON 日期/忽略注解及 Map 构造见下方。无显式初值的引用字段为 null；Java primitive 为 0/false。Map 请求字段见对应 controller 方法。保留源码作为逐字段核对证据，不代表未来 Python ORM 必须照搬类层次。\n",
    ]
    for directory in ("dto", "entity", "vo"):
        for file in sorted((PACKAGE / directory).rglob("*.java")):
            source = file.read_text(encoding="utf-8")
            if directory in {"entity", "dto", "vo"}:
                content = re.sub(r"/\*[\s\S]*?\*/", "", source)
                content = re.sub(
                    r"^(?:package|import) [^\n]+\n", "", content, flags=re.MULTILINE
                ).strip()
                catalog.append(
                    f"\n## {file.stem}\n\n来源 `{file.relative_to(ROOT).as_posix()}`\n\n```java\n{content}\n```\n"
                )
    (OUTPUT / "schemas.md").write_text("\n".join(catalog), encoding="utf-8")


def build_storage():
    sources = {}
    for dialect, file in [
        ("mysql", JAVA / "resources/sql/schema.sql"),
        ("h2", JAVA / "resources/sql/h2/schema-h2.sql"),
    ]:
        tables = {}
        for statement in sqlparse.split(file.read_text(encoding="utf-8")):
            match = re.search(
                r"create\s+table\s+if\s+not\s+exists\s+`?(\w+)`?", statement, re.IGNORECASE
            )
            if match:
                tables[match.group(1).lower()] = statement[match.start() :]
        assert len(tables) == 13, (dialect, len(tables))
        sources[dialect] = tables
    entities = {
        "agent": "Agent",
        "business_knowledge": "BusinessKnowledge",
        "semantic_model": "SemanticModel",
        "agent_knowledge": "AgentKnowledge",
        "datasource": "Datasource",
        "logical_relation": "LogicalRelation",
        "agent_datasource": "AgentDatasource",
        "agent_datasource_tables": "AgentDatasourceTables",
        "agent_preset_question": "AgentPresetQuestion",
        "chat_session": "ChatSession",
        "chat_message": "ChatMessage",
        "user_prompt_config": "UserPromptConfig",
        "model_config": "ModelConfig",
    }
    result = [
        "# 业务表、实体及 Mapper 对账\n",
        "不区分建表关键字大小写：MySQL 13 张、H2 13 张，表名集合一致。`001_business.sql` 保留 MySQL DDL 的所有列、索引、外键、默认值和 ON DELETE/UPDATE；H2 仅作对照，Python 不运行 H2。以下每表并列两套完整 DDL 和实际 Mapper，实体字段在 schemas.md。Mapper 不存在独立类时保留实际匹配文件。\n",
        "原 data.sql 为演示 Agent/知识/语义数据，不含可用模型或用户凭据，默认不复制，以免假配置被误认为就绪；空库必要初始数据只有 migration 版本和模型类型互斥行（002）。存量业务复制、密文验证、ID/文件重写由 Ticket 09 执行，不运行破坏性覆盖。\n",
    ]
    for name, entity in entities.items():
        result.append(f"\n## {name}\n\n实体 `{entity}`，字段见 [catalog](schemas.md)。\n")
        for dialect in sources:
            result.append(f"\n### {dialect}\n\n```sql\n{sources[dialect][name]}\n```\n")
        mappers = list((PACKAGE / "mapper").glob(entity + "*Mapper.java"))
        if not mappers and name == "agent_datasource_tables":
            mappers = list((PACKAGE / "mapper").glob("*Datasource*Mapper.java"))
        for mapper in mappers:
            content = mapper.read_text(encoding="utf-8")
            content = re.sub(r"/\*[\s\S]*?\*/", "", content)
            content = re.sub(
                r"^(?:package|import) [^\n]+\n", "", content, flags=re.MULTILINE
            ).strip()
            result.append(
                f"\nMapper `{mapper.relative_to(ROOT).as_posix()}`\n\n```java\n{content}\n```\n"
            )
    result.append(
        "\n## 方言及约束决策\n\nMySQL 为列/约束权威：保留 utf8mb4_bin 对表列名的大小写区分、JSON metadata、MEDIUMTEXT、unsigned temperature、自动增量和 ON UPDATE 时间；H2 的兼容语法不复制到 Python。agent_datasource 的 (agent_id,datasource_id) 唯一、agent_datasource_tables 的 (agent_datasource_id,table_name) 唯一及解绑级联均完整保留。semantic_model.datasource_id 和 user_prompt_config.agent_id 原本无外键，不擅自增加。实体展示字段 selectTables 等不当作存储列；JSON metadata 由 API 转换，不能再次字符串化。\n\n框架表：Java MysqlSaver 自动建图表及 Spring AI ChatMemory 表与这 13 张表分开；精确版本框架表字段与索引见 [框架表清单](../python-framework-tables.md)，迁移工具显式排除，不复制其序列化字节。Java checkpoint 重建，chat memory 从成功轮次转换为 agent_conversation_turn 后重建，历史 PYTHON 文本仅读兼容。\n\nPython 新表和唯一键见 `PYTHON/migrations/002_runtime.sql`；无隐式跨存储外键。运行/效果/结果由 runtime 服务写、展示消息由消息 API 写，所有删除通过公共生命周期闸门后先提交清理作业。SQLite saver 独立文件内由锁定版本 setup 建立 checkpoints、writes 表（实际兼容性另有重启验证），不计入业务表数。应用生命周期调用 setup，业务迁移版本记录只记录 MySQL 001/002，变更既有 SQL 校验和会阻止启动。\n"
    )
    (OUTPUT / "storage-audit.md").write_text("\n".join(result), encoding="utf-8")


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    build_contracts()
    build_storage()
    for generated in OUTPUT.glob("*.md"):
        generated.write_text(
            "\n".join(
                line.rstrip() for line in generated.read_text(encoding="utf-8").splitlines()
            ).rstrip()
            + "\n",
            encoding="utf-8",
        )
    print("Generated 98 HTTP contracts, schema catalog and 13-table MySQL/H2/Mapper audit")
