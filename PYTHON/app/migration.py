"""Offline, repeatable import from a read-only Java database copy.

Only the thirteen business tables are copied. Java framework memory/checkpoints
are deliberately excluded; new successful Python turns rebuild model memory.
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.database import migrate, open_database
from app.local_files import DOCUMENT_TYPES, store_file

BUSINESS_TABLES = (
    "agent",
    "datasource",
    "business_knowledge",
    "semantic_model",
    "agent_knowledge",
    "logical_relation",
    "agent_datasource",
    "agent_datasource_tables",
    "agent_preset_question",
    "chat_session",
    "chat_message",
    "user_prompt_config",
    "model_config",
)


class MigrationError(ValueError):
    """Operator-safe migration error; contains identifiers, never source values."""


@dataclass(frozen=True)
class FileCopy:
    relative: str
    filename: str
    category: str
    content: bytes = field(repr=False)


def snapshot(engine):
    with engine.connect() as conn:
        conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        conn.exec_driver_sql("SET TRANSACTION READ ONLY")
        conn.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT")
        identity = conn.exec_driver_sql("SELECT @@server_uuid, DATABASE()").one()
        tables = set(inspect(conn).get_table_names())
        missing = set(BUSINESS_TABLES) - tables
        if missing:
            raise MigrationError("Missing business tables: " + ",".join(sorted(missing)))
        rows = {
            table: [
                dict(row)
                for row in conn.execute(text(f"SELECT * FROM `{table}` ORDER BY id")).mappings()
            ]
            for table in BUSINESS_TABLES
        }
        conn.rollback()
    return identity, rows, sorted(tables - set(BUSINESS_TABLES))


def credential(value):
    if not value:
        return None
    if value.startswith("{bcrypt}"):
        encoded = value.partition("::")[0][8:]
        if not re.fullmatch(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", encoded):
            raise MigrationError("Invalid Java bcrypt encoding; rotate the affected Agent key")
        return "{bcrypt}" + encoded
    if value.startswith("{"):
        raise MigrationError("Unsupported Java key encoding; rotate the affected Agent key")
    # Java legacy keys are plaintext. Store only a SHA-256 digest in Python.
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def prepare(rows, source_files, settings, source_prefix="/uploads"):
    files: dict[str, FileCopy] = {}

    def copy_file(reference, category, owner):
        value = reference
        for prefix in ["/api/upload/files", "/api/upload" + source_prefix, source_prefix]:
            if value.startswith(prefix + "/"):
                value = value[len(prefix) + 1 :]
                break
        value = unquote(value).replace("\\", "/")
        path = (source_files / value).resolve()
        if not path.is_relative_to(source_files) or not path.is_file():
            raise MigrationError(f"{owner}: file missing or outside source-files")
        suffix = path.suffix.lower()
        supported = {
            "knowledge": DOCUMENT_TYPES,
            "avatars": {".jpg", ".jpeg", ".png", ".gif", ".webp"},
            "reports": {".html", ".htm", ".md", ".csv", ".xlsx", ".json", ".txt", ".pdf"},
        }
        if suffix not in supported[category]:
            raise MigrationError(f"{owner}: unsupported file type")
        if not 0 < path.stat().st_size <= settings.max_upload_bytes:
            raise MigrationError(f"{owner}: empty file or upload limit exceeded")
        content = path.read_bytes()
        relative = f"{category}/{hashlib.sha256(content).hexdigest()}{suffix}"
        files[relative] = FileCopy(relative, path.name, category, content)
        return relative

    # Rewrite display links only; never interpret historical code or checkpoints.
    prefixes = "|".join(
        re.escape(prefix)
        for prefix in ["/api/upload/files", "/api/upload" + source_prefix, source_prefix]
    )
    links = re.compile(r"""(?:https?://[^\s/"'<>]+)?(?:""" + prefixes + r""")/([^\s"'<>?#)]+)""")

    def rewrite(value, owner):
        if isinstance(value, str):

            def replace(match):
                reference = match.group(1)
                category = next(
                    (
                        part
                        for part in reference.split("/")[:-1]
                        if part in {"knowledge", "avatars", "reports"}
                    ),
                    "reports" if Path(reference).suffix.lower() in {".html", ".htm"} else "knowledge",
                )
                if category not in {"knowledge", "avatars", "reports"}:
                    category = (
                        "reports"
                        if Path(reference).suffix.lower() in {".html", ".htm"}
                        else "knowledge"
                    )
                return "/api/upload/files/" + copy_file(reference, category, owner)

            return links.sub(replace, value)
        if isinstance(value, dict):
            return {key: rewrite(item, owner) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item, owner) for item in value]
        return value

    for row in rows["agent"]:
        row["api_key"] = credential(row["api_key"])
        if row["api_key_enabled"] and not row["api_key"]:
            raise MigrationError(f"Agent {row['id']}: enabled key missing")
        if row.get("avatar"):
            row["avatar"] = rewrite(row["avatar"], f"agent {row['id']}")
    for row in rows["chat_message"]:
        owner = f"chat_message {row['id']}"
        row["content"] = rewrite(row["content"], owner)
        if row.get("metadata") is not None:
            metadata = row["metadata"]
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except ValueError:
                    raise MigrationError(f"{owner}: invalid metadata JSON") from None
            row["metadata"] = rewrite(metadata, owner)
    for kind, table in [("business", "business_knowledge"), ("document", "agent_knowledge")]:
        for row in rows[table]:
            row.update(embedding_status="FAILED", error_msg="Imported from Java; rebuild embedding")
            if kind != "document" or row.get("is_deleted") or not row.get("file_path"):
                continue
            row["file_path"] = copy_file(
                row["file_path"], "knowledge", f"agent_knowledge {row['id']}"
            )
            row["file_size"] = len(files[row["file_path"]].content)
    return list(files.values())


def require_fresh_target(conn, settings):
    permitted = {"python_schema_migration", "python_model_type_lock", "python_local_file"}
    for table in inspect(conn).get_table_names():
        if table in permitted:
            continue
        # Table names originate from the catalog, not migration data.
        quoted = conn.dialect.identifier_preparer.quote(table)
        if conn.execute(text(f"SELECT 1 FROM {quoted} LIMIT 1")).first():
            raise MigrationError(
                f"Target must be a fresh dedicated Python database; existing rows in {table}"
            )
    for filename, tables in [
        ("checkpoints.sqlite", ["checkpoints", "writes"]),
        ("knowledge.sqlite", ["chunks", "external_targets"]),
    ]:
        path = (settings.data_dir / filename).resolve()
        if not path.is_file():
            continue
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            names = {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            for table in tables:
                if table in names and db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                    raise MigrationError("Target data directory must be fresh; existing " + table)


def import_copy(settings, source_url, source_files, apply=False, source_prefix="/uploads"):
    if not re.fullmatch(r"/[A-Za-z0-9_/-]+", source_prefix) or ".." in source_prefix.split("/"):
        raise MigrationError("Source URL prefix must be a local absolute URL path")
    source_prefix = source_prefix.rstrip("/")
    source = open_database(source_url)
    target = open_database(settings.database_url)
    try:
        identity, rows, excluded = snapshot(source)
        with target.connect() as conn:
            target_identity = conn.exec_driver_sql("SELECT @@server_uuid, DATABASE()").one()
        if identity == target_identity:
            raise MigrationError("Source and target must be different databases")
        digest = hashlib.sha256(
            json.dumps(rows, sort_keys=True, default=str, ensure_ascii=False).encode()
        ).hexdigest()
        files = prepare(rows, source_files.resolve(), settings, source_prefix)
        file_hashes = sorted(item.relative for item in files)
        digest = hashlib.sha256((digest + json.dumps(file_hashes)).encode()).hexdigest()
        report = {
            "status": "VALIDATED",
            "importId": digest,
            "businessTables": {table: len(values) for table, values in rows.items()},
            "excludedTables": excluded,
            "files": len(files),
            "memoryPolicy": "REBUILD_FROM_NEW_SUCCESSFUL_TURNS",
            "javaCheckpointsImported": False,
            "validationScope": "SOURCE_SNAPSHOT_AND_FILES",
            "warnings": [
                "Imported knowledge requires embedding rebuild",
                "Validate datasource connection URLs and credentials via HTTP before use",
            ],
        }
        if not apply:
            return report
        migrate(target)
        with target.connect() as conn:
            # Exclusive import lock plus empty destination prevent partial overwrites.
            if conn.exec_driver_sql("SELECT GET_LOCK('dataagent_python_import',30)").scalar() != 1:
                raise MigrationError("Migration import lock unavailable")
            try:
                existing = conn.execute(
                    text("SELECT report FROM python_data_import WHERE import_id=:id"),
                    {"id": digest},
                ).scalar()
                if existing:
                    result = json.loads(existing) if isinstance(existing, str) else existing
                    return {**result, "status": "ALREADY_IMPORTED"}
                require_fresh_target(conn, settings)
                # Immutable files may survive a rolled-back import; retries reuse them.
                for item in files:
                    store_file(
                        target, settings, item.filename, item.content, category=item.category
                    )
                for table in BUSINESS_TABLES:
                    columns = {column["name"] for column in inspect(conn).get_columns(table)}
                    for row in rows[table]:
                        if set(row) - columns:
                            raise MigrationError(
                                f"{table}: source columns differ from target schema"
                            )
                        values = dict(row)
                        for key, value in values.items():
                            if isinstance(value, (dict, list)):
                                values[key] = json.dumps(value, ensure_ascii=False)
                        names = ",".join(f"`{name}`" for name in values)
                        binds = ",".join(":" + name for name in values)
                        try:
                            conn.execute(
                                text(f"INSERT INTO `{table}` ({names}) VALUES ({binds})"), values
                            )
                        except SQLAlchemyError:
                            raise MigrationError(
                                f"{table} id={row['id']}: insert rejected; check schema and constraints"
                            ) from None
                for kind, table in [
                    ("business", "business_knowledge"),
                    ("semantic", "semantic_model"),
                    ("document", "agent_knowledge"),
                ]:
                    for row in rows[table]:
                        if row.get("is_deleted"):
                            continue
                        conn.execute(
                            text(
                                "INSERT INTO python_knowledge_state "
                                "(kind,record_id,agent_id,embedding_status,error_msg) "
                                "VALUES (:kind,:id,:aid,'FAILED','Imported from Java; rebuild embedding')"
                            ),
                            {"kind": kind, "id": row["id"], "aid": row["agent_id"]},
                        )
                report["status"] = "IMPORTED"
                conn.execute(
                    text("INSERT INTO python_data_import(import_id,report) VALUES (:id,:report)"),
                    {"id": digest, "report": json.dumps(report, ensure_ascii=False)},
                )
                conn.commit()
            finally:
                # Roll back failures before releasing ownership. Never commit
                # from finally: a failed row must not leave a partial import.
                conn.rollback()
                conn.exec_driver_sql("SELECT RELEASE_LOCK('dataagent_python_import')")
                conn.commit()
        return report
    finally:
        source.dispose()
        target.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-files", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--source-url-prefix", default="/uploads")
    args = parser.parse_args()
    try:
        source = os.environ.get("DATAAGENT_MIGRATION_SOURCE_URL")
        if not source:
            raise MigrationError("Set DATAAGENT_MIGRATION_SOURCE_URL to a Java database copy")
        result = import_copy(
            Settings(), source, args.source_files, args.apply, args.source_url_prefix
        )
    except MigrationError as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from None
    except Exception as exc:  # noqa: BLE001 -- no database URLs, values or upstream errors in CLI output
        print(
            json.dumps(
                {
                    "status": "FAILED",
                    "error": type(exc).__name__,
                    "action": "Check source schema, constraints and credentials; retry into the empty target",
                }
            )
        )
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
