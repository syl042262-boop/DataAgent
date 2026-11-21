"""Independent business connections: credentials never enter public responses."""

import ssl
from contextlib import contextmanager
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.agents import camel_row, response

DIALECT_INFO: dict[str, dict[str, str]] = {
    "mysql": {
        "label": "MySQL",
        "quote_hint": "MySQL 标识符需要引用时请使用反引号。",
        "pid_sql": "SELECT CONNECTION_ID()",
    },
    "postgresql": {
        "label": "PostgreSQL",
        "quote_hint": 'PostgreSQL 标识符（含大小写混合或保留字）请使用双引号，例如 "Table"."Column"。',
        "pid_sql": "SELECT pg_backend_pid()",
    },
}


def dialect_info(source_type: str) -> dict[str, str]:
    if source_type not in DIALECT_INFO:
        raise ValueError("仅支持 MySQL 和 PostgreSQL 数据源")
    return DIALECT_INFO[source_type]


class DatasourceInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = None
    host: str | None = Field(default=None, min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    databaseName: str | None = Field(default=None, min_length=1, max_length=255)
    schemaName: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    connectionUrl: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|inactive)$")
    description: str | None = None
    creatorId: int | None = None


def require_datasource(connection, identifier, lock=False):
    row = (
        connection.execute(
            text("SELECT * FROM datasource WHERE id=:id" + (" FOR UPDATE" if lock else "")),
            {"id": identifier},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "数据源不存在")
    result = dict(row)
    result["schema_name"] = connection.execute(
        text("SELECT schema_name FROM python_datasource_options WHERE datasource_id=:id"),
        {"id": identifier},
    ).scalar()
    return result


def public_datasource(row):
    result = camel_row(row)
    result["password"] = "******"
    return result


def mysql_connection_options(source):
    host, port, database = source["host"], source["port"], source["database_name"]
    options: dict[str, Any] = {"connect_timeout": 5, "read_timeout": 15, "write_timeout": 15}
    charset = "utf8mb4"
    raw = source.get("connection_url")
    if raw:
        try:
            parsed = urlsplit(raw.removeprefix("jdbc:"))
            if (
                parsed.scheme != "mysql"
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
                or not parsed.path.strip("/")
            ):
                raise ValueError()
            host, port, database = parsed.hostname, parsed.port or 3306, unquote(parsed.path[1:])
            pairs = parse_qsl(parsed.query, strict_parsing=True)
            if len(dict(pairs)) != len(pairs):
                raise ValueError()
            for key, value in pairs:
                if key == "characterEncoding":
                    charset = {"UTF-8": "utf8mb4", "utf8": "utf8", "utf8mb4": "utf8mb4"}[value]
                elif key in ("connectTimeout", "socketTimeout"):
                    timeout = int(value)
                    if not 1 <= timeout <= 180000:
                        raise ValueError()
                    options["connect_timeout" if key == "connectTimeout" else "read_timeout"] = max(
                        1, timeout // 1000
                    )
                elif key == "useSSL" and value in ("true", "false"):
                    options["ssl"] = ssl.create_default_context() if value == "true" else None
                elif key == "useUnicode" and value == "true":
                    pass  # PyMySQL returns Unicode by default.
                else:
                    raise ValueError()
        except (ValueError, KeyError):
            raise ValueError("MySQL URL 格式或参数不支持，URL 不得包含凭据") from None
    return URL.create(
        "mysql+pymysql",
        username=source["username"],
        password=source["password"],
        host=host,
        port=port,
        database=database,
        query={"charset": charset},
    ), options


def postgresql_connection_options(source):
    host, port, database = source["host"], source["port"], source["database_name"]
    schema_name = (source.get("schema_name") or "").strip() or "public"
    options: dict[str, Any] = {
        "connect_timeout": 5,
        "options": "-c statement_timeout=15000",
    }
    raw = source.get("connection_url")
    if raw:
        try:
            parsed = urlsplit(raw.removeprefix("jdbc:"))
            if (
                parsed.scheme not in ("postgresql", "postgres")
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
                or not parsed.path.strip("/")
            ):
                raise ValueError()
            host, port, database = parsed.hostname, parsed.port or 5432, unquote(parsed.path[1:])
            pairs = parse_qsl(parsed.query, strict_parsing=True)
            if len(dict(pairs)) != len(pairs):
                raise ValueError()
            for key, value in pairs:
                if key == "currentSchema" and value.strip():
                    if not source.get("schema_name"):
                        schema_name = value.strip()
                elif key == "sslmode" and value in (
                    "disable",
                    "allow",
                    "prefer",
                    "require",
                    "verify-ca",
                    "verify-full",
                ):
                    options["sslmode"] = value
                elif key in ("connectTimeout", "socketTimeout"):
                    timeout = int(value)
                    if not 1 <= timeout <= 180000:
                        raise ValueError()
                    if key == "connectTimeout":
                        options["connect_timeout"] = max(1, timeout // 1000) if timeout > 180 else timeout
                    else:
                        stmt_ms = timeout if timeout > 180 else timeout * 1000
                        options["options"] = f"-c statement_timeout={stmt_ms}"
                else:
                    raise ValueError()
        except ValueError:
            raise ValueError("PostgreSQL URL 格式或参数不支持，URL 不得包含凭据") from None
    return (
        URL.create(
            "postgresql+psycopg",
            username=source["username"],
            password=source["password"],
            host=host,
            port=port,
            database=database,
        ),
        options,
        schema_name,
    )


@contextmanager
def business_connection(source, *, preserve_errors=False):
    source_type = source["type"]
    if source_type == "mysql":
        url, options = mysql_connection_options(source)
        schema_name = None
    elif source_type == "postgresql":
        url, options, schema_name = postgresql_connection_options(source)
    else:
        raise ValueError("仅支持 MySQL 和 PostgreSQL 数据源")
    engine = create_engine(
        url,
        poolclass=NullPool,
        connect_args=options,
    )
    try:
        with engine.connect() as connection:
            if source_type == "postgresql" and schema_name:
                safe_schema = schema_name.replace('"', '""')
                connection.exec_driver_sql(f'SET search_path TO "{safe_schema}"')
                connection.commit()
            yield connection
    except SQLAlchemyError:
        if preserve_errors:
            raise
        raise ValueError("数据库连接或元数据读取失败，请检查配置和权限") from None
    finally:
        engine.dispose()


def _pg_schema(source) -> str | None:
    if source.get("type") != "postgresql":
        return None
    return (source.get("schema_name") or "").strip() or "public"


def table_names(source):
    schema = _pg_schema(source)
    with business_connection(source) as connection:
        return sorted(inspect(connection).get_table_names(schema=schema))


def schema_snapshot(source, selected):
    schema = _pg_schema(source)
    with business_connection(source) as connection:
        inspector = inspect(connection)
        existing = set(inspector.get_table_names(schema=schema))
        if not set(selected).issubset(existing):
            raise ValueError("选择了不存在的数据表")
        return {
            table: [
                {"name": col["name"], "type": str(col["type"]), "nullable": col["nullable"]}
                for col in inspector.get_columns(table, schema=schema)
            ]
            for table in selected
        }


router = APIRouter(prefix="/api/datasource")


@router.get("/types")
def types():
    return response(
        [
            {
                "code": code,
                "typeName": kind,
                "dialect": dialect,
                "protocol": "jdbc",
                "displayName": dialect,
            }
            for code, kind, dialect in [(1, "mysql", "MySQL"), (2, "postgresql", "PostgreSQL")]
        ]
    )


@router.get("")
def list_sources(request: Request, status: str = "", type: str = ""):
    clause, params = "", {}
    if status:
        clause, params = " WHERE status=:value", {"value": status}
    elif type:
        clause, params = " WHERE type=:value", {"value": type}
    with request.app.state.engine.connect() as connection:
        ids = (
            connection.execute(
                text("SELECT id FROM datasource" + clause + " ORDER BY id DESC"), params
            )
            .scalars()
            .all()
        )
        return [public_datasource(require_datasource(connection, i)) for i in ids]


def save_source(body, request, identifier=None):
    values = body.model_dump(exclude_unset=True)
    with request.app.state.engine.begin() as connection:
        old = require_datasource(connection, identifier, lock=True) if identifier else {}
        mapping = {
            "databaseName": "database_name",
            "creatorId": "creator_id",
            "connectionUrl": "connection_url",
            "schemaName": "schema_name",
        }
        merged = {**old, **{mapping.get(k, k): v for k, v in values.items()}}
        if merged.get("type") not in ("mysql", "postgresql"):
            raise ValueError("仅支持 MySQL 和 PostgreSQL 数据源")
        for field in ("name", "host", "port", "database_name", "username"):
            if not merged.get(field):
                raise ValueError("数据源必填配置不能为空")
        if identifier and values.get("password") in (None, "******"):
            merged["password"] = old["password"]
        elif merged.get("password") is None or merged.get("password") == "******":
            raise ValueError("请填写数据源密码")
        merged["status"] = merged.get("status") or "inactive"
        merged["description"] = merged.get("description")
        merged["creator_id"] = merged.get("creator_id")
        merged["connection_url"] = merged.get("connection_url") or None
        if merged["connection_url"]:
            if merged["type"] == "mysql":
                mysql_connection_options(merged)
            elif merged["type"] == "postgresql":
                postgresql_connection_options(merged)
            else:
                raise ValueError("仅支持 MySQL 和 PostgreSQL 数据源")
        fields = (
            "name",
            "type",
            "host",
            "port",
            "database_name",
            "username",
            "password",
            "status",
            "description",
            "creator_id",
            "connection_url",
        )
        if identifier:
            connection.execute(
                text(
                    "UPDATE datasource SET "
                    + ",".join(f"{k}=:{k}" for k in fields)
                    + ",test_status='unknown' WHERE id=:id"
                ),
                {**merged, "id": identifier},
            )
            # A changed connection invalidates all snapshots derived from it.
            connection.execute(
                text(
                    "DELETE s FROM python_agent_schema s JOIN agent_datasource b "
                    "ON b.id=s.agent_datasource_id WHERE b.datasource_id=:id"
                ),
                {"id": identifier},
            )
        else:
            result = connection.execute(
                text(
                    "INSERT INTO datasource ("
                    + ",".join(fields)
                    + ") VALUES ("
                    + ",".join(f":{k}" for k in fields)
                    + ")"
                ),
                merged,
            )
            identifier = result.lastrowid
        connection.execute(
            text(
                "INSERT INTO python_datasource_options(datasource_id,schema_name) "
                "VALUES (:id,:schema) ON DUPLICATE KEY UPDATE schema_name=:schema"
            ),
            {"id": identifier, "schema": merged.get("schema_name")},
        )
        return public_datasource(require_datasource(connection, identifier))


@router.post("")
def create_source(body: DatasourceInput, request: Request):
    return save_source(body, request)


@router.get("/{identifier}")
def get_source(identifier: int, request: Request):
    with request.app.state.engine.connect() as connection:
        return public_datasource(require_datasource(connection, identifier))


@router.put("/{identifier}")
def update_source(identifier: int, body: DatasourceInput, request: Request):
    return save_source(body, request, identifier)


@router.delete("/{identifier}")
def delete_source(identifier: int, request: Request):
    with request.app.state.engine.begin() as connection:
        require_datasource(connection, identifier, lock=True)
        connection.execute(text("DELETE FROM datasource WHERE id=:id"), {"id": identifier})
    return response(message="数据源删除成功")


def read_source(request, identifier):
    with request.app.state.engine.connect() as connection:
        return require_datasource(connection, identifier)


@router.post("/{identifier}/test")
def test_source(identifier: int, request: Request):
    with request.app.state.engine.begin() as connection:
        source = require_datasource(connection, identifier, lock=True)
        success = True
        try:
            with business_connection(source) as business:
                business.execute(text("SELECT 1")).scalar_one()
        except ValueError:
            success = False
        connection.execute(
            text("UPDATE datasource SET test_status=:status WHERE id=:id"),
            {"id": identifier, "status": "success" if success else "failed"},
        )
    return response(message="连接测试成功" if success else "连接测试失败", success=success)


@router.get("/{identifier}/tables")
def tables(identifier: int, request: Request):
    return table_names(read_source(request, identifier))


@router.get("/{identifier}/tables/{table_name}/columns")
def columns(identifier: int, table_name: str, request: Request):
    snapshot = schema_snapshot(read_source(request, identifier), [table_name])
    return response([column["name"] for column in snapshot[table_name]], "获取字段列表成功")
