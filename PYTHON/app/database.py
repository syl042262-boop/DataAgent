"""Versioned, checksummed MySQL migrations; never use the Java database."""

import hashlib
from pathlib import Path

import sqlparse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def open_database(url: str) -> Engine:
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    if engine.dialect.name != "mysql":
        engine.dispose()
        raise ValueError("管理库仅支持独立 MySQL")
    return engine


def migrate(engine: Engine) -> None:
    # MySQL DDL auto-commits: each statement must remain retryable after a crash.
    with engine.connect() as connection:
        acquired = connection.execute(
            text("SELECT GET_LOCK('dataagent_python_migrations', 30)")
        ).scalar()
        if acquired != 1:
            raise RuntimeError("Cannot acquire migration lock")
        try:
            connection.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS python_schema_migration "
                "(version VARCHAR(100) PRIMARY KEY, checksum CHAR(64) NOT NULL)"
            )
            for path in sorted((Path(__file__).parent.parent / "migrations").glob("*.sql")):
                source = path.read_text(encoding="utf-8-sig")
                checksum = hashlib.sha256(source.encode()).hexdigest()
                applied = connection.execute(
                    text("SELECT checksum FROM python_schema_migration WHERE version=:version"),
                    {"version": path.name},
                ).scalar()
                if applied:
                    if applied != checksum:
                        raise RuntimeError(f"Applied migration changed: {path.name}")
                    continue
                for statement in sqlparse.split(source):
                    if statement.strip():
                        connection.exec_driver_sql(statement)
                connection.execute(
                    text("INSERT INTO python_schema_migration VALUES (:version, :checksum)"),
                    {"version": path.name, "checksum": checksum},
                )
                connection.commit()
        finally:
            connection.execute(text("SELECT RELEASE_LOCK('dataagent_python_migrations')"))
            connection.commit()
