"""Logical relation management and column-mapping validation."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents import response
from app.datasources import require_datasource, schema_snapshot


class LogicalRelationInput(BaseModel):
    id: int | None = None
    sourceTableName: str = Field(min_length=1, max_length=100)
    sourceColumnName: str = Field(min_length=1, max_length=100)
    targetTableName: str = Field(min_length=1, max_length=100)
    targetColumnName: str = Field(min_length=1, max_length=100)
    relationType: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=500)


def _row_to_relation(row: Any) -> dict[str, Any]:
    data = dict(row)
    return {
        "id": data["id"],
        "datasourceId": data["datasource_id"],
        "sourceTableName": data["source_table_name"],
        "sourceColumnName": data["source_column_name"],
        "targetTableName": data["target_table_name"],
        "targetColumnName": data["target_column_name"],
        "relationType": data["relation_type"],
        "description": data["description"],
        "createdTime": data["created_time"].isoformat() if data.get("created_time") else None,
        "updatedTime": data["updated_time"].isoformat() if data.get("updated_time") else None,
    }


def _validate_relation_columns(source: dict[str, Any], relations: list[LogicalRelationInput]) -> None:
    if not relations:
        return
    tables_needed = sorted(
        {r.sourceTableName for r in relations} | {r.targetTableName for r in relations}
    )
    try:
        snapshot = schema_snapshot(source, tables_needed)
    except ValueError as exc:
        raise ValueError("逻辑关系引用的数据表不存在") from exc

    table_cols = {
        table: {col["name"] for col in cols}
        for table, cols in snapshot.items()
    }
    for rel in relations:
        if rel.sourceColumnName not in table_cols.get(rel.sourceTableName, set()):
            raise ValueError(
                f"无效列映射: {rel.sourceTableName}.{rel.sourceColumnName} 不存在"
            )
        if rel.targetColumnName not in table_cols.get(rel.targetTableName, set()):
            raise ValueError(
                f"无效列映射: {rel.targetTableName}.{rel.targetColumnName} 不存在"
            )


def load_logical_relations(
    conn, datasource_id: int, selected_tables: list[str] | None = None
) -> list[dict[str, Any]]:
    rows = (
        conn.execute(
            text(
                "SELECT * FROM logical_relation "
                "WHERE datasource_id=:ds_id AND (is_deleted=0 OR is_deleted IS NULL) "
                "ORDER BY id ASC"
            ),
            {"ds_id": datasource_id},
        )
        .mappings()
        .all()
    )
    items = [_row_to_relation(r) for r in rows]
    if selected_tables is not None:
        allowed = set(selected_tables)
        items = [
            item
            for item in items
            if item["sourceTableName"] in allowed and item["targetTableName"] in allowed
        ]
    return items


router = APIRouter(prefix="/api/datasource")


@router.get("/{datasource_id}/logical-relations")
def get_logical_relations(datasource_id: int, request: Request):
    with request.app.state.engine.connect() as conn:
        require_datasource(conn, datasource_id)
        items = load_logical_relations(conn, datasource_id)
    return response(items, "success get logical relations")


@router.post("/{datasource_id}/logical-relations")
def add_logical_relation(
    datasource_id: int, body: LogicalRelationInput, request: Request
):
    with request.app.state.engine.begin() as conn:
        source = require_datasource(conn, datasource_id, lock=True)
        _validate_relation_columns(source, [body])
        exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM logical_relation "
                "WHERE datasource_id=:ds_id AND (is_deleted=0 OR is_deleted IS NULL) "
                "AND source_table_name=:source_table AND source_column_name=:source_col "
                "AND target_table_name=:target_table AND target_column_name=:target_col"
            ),
            {
                "ds_id": datasource_id,
                "source_table": body.sourceTableName,
                "source_col": body.sourceColumnName,
                "target_table": body.targetTableName,
                "target_col": body.targetColumnName,
            },
        ).scalar_one()
        if exists:
            raise ValueError("该逻辑外键关系已存在")
        res = conn.execute(
            text(
                "INSERT INTO logical_relation "
                "(datasource_id, source_table_name, source_column_name, "
                "target_table_name, target_column_name, relation_type, description, is_deleted) "
                "VALUES (:ds_id, :source_table, :source_col, :target_table, :target_col, "
                ":relation_type, :description, 0)"
            ),
            {
                "ds_id": datasource_id,
                "source_table": body.sourceTableName,
                "source_col": body.sourceColumnName,
                "target_table": body.targetTableName,
                "target_col": body.targetColumnName,
                "relation_type": body.relationType,
                "description": body.description,
            },
        )
        row = (
            conn.execute(
                text("SELECT * FROM logical_relation WHERE id=:id"),
                {"id": res.lastrowid},
            )
            .mappings()
            .one()
        )
    return response(_row_to_relation(row), "success create logical relation")


@router.put("/{datasource_id}/logical-relations/{relation_id}")
def update_logical_relation(
    datasource_id: int,
    relation_id: int,
    body: LogicalRelationInput,
    request: Request,
):
    with request.app.state.engine.begin() as conn:
        source = require_datasource(conn, datasource_id, lock=True)
        existing = (
            conn.execute(
                text(
                    "SELECT * FROM logical_relation "
                    "WHERE id=:id AND datasource_id=:ds_id AND (is_deleted=0 OR is_deleted IS NULL) "
                    "FOR UPDATE"
                ),
                {"id": relation_id, "ds_id": datasource_id},
            )
            .mappings()
            .first()
        )
        if existing is None:
            raise HTTPException(404, "逻辑外键不存在")
        _validate_relation_columns(source, [body])
        dup = conn.execute(
            text(
                "SELECT COUNT(*) FROM logical_relation "
                "WHERE datasource_id=:ds_id AND id<>:id AND (is_deleted=0 OR is_deleted IS NULL) "
                "AND source_table_name=:st AND source_column_name=:sc "
                "AND target_table_name=:tt AND target_column_name=:tc"
            ),
            {
                "ds_id": datasource_id,
                "id": relation_id,
                "st": body.sourceTableName,
                "sc": body.sourceColumnName,
                "tt": body.targetTableName,
                "tc": body.targetColumnName,
            },
        ).scalar_one()
        if dup:
            raise ValueError("该逻辑外键关系已存在")
        conn.execute(
            text(
                "UPDATE logical_relation SET "
                "source_table_name=:st, source_column_name=:sc, "
                "target_table_name=:tt, target_column_name=:tc, "
                "relation_type=:rtype, description=:desc "
                "WHERE id=:id AND datasource_id=:ds_id"
            ),
            {
                "id": relation_id,
                "ds_id": datasource_id,
                "st": body.sourceTableName,
                "sc": body.sourceColumnName,
                "tt": body.targetTableName,
                "tc": body.targetColumnName,
                "rtype": body.relationType,
                "desc": body.description,
            },
        )
        row = (
            conn.execute(
                text("SELECT * FROM logical_relation WHERE id=:id"),
                {"id": relation_id},
            )
            .mappings()
            .one()
        )
    return response(_row_to_relation(row), "success update logical relation")


@router.delete("/{datasource_id}/logical-relations/{relation_id}")
def delete_logical_relation(datasource_id: int, relation_id: int, request: Request):
    with request.app.state.engine.begin() as conn:
        require_datasource(conn, datasource_id, lock=True)
        res = conn.execute(
            text(
                "UPDATE logical_relation SET is_deleted=1 "
                "WHERE id=:id AND datasource_id=:ds_id AND (is_deleted=0 OR is_deleted IS NULL)"
            ),
            {"id": relation_id, "ds_id": datasource_id},
        )
        if res.rowcount == 0:
            raise HTTPException(404, "逻辑外键不存在")
    return response(message="success delete logical relation")


@router.put("/{datasource_id}/logical-relations")
def save_logical_relations(
    datasource_id: int,
    relations: list[LogicalRelationInput],
    request: Request,
):
    with request.app.state.engine.begin() as conn:
        source = require_datasource(conn, datasource_id, lock=True)
        _validate_relation_columns(source, relations)

        seen: set[tuple[str, str, str, str]] = set()
        unique: list[LogicalRelationInput] = []
        for rel in relations:
            key = (
                rel.sourceTableName,
                rel.sourceColumnName,
                rel.targetTableName,
                rel.targetColumnName,
            )
            if key not in seen:
                seen.add(key)
                unique.append(rel)

        existing_ids = {
            row["id"]
            for row in conn.execute(
                text(
                    "SELECT id FROM logical_relation "
                    "WHERE datasource_id=:ds_id AND (is_deleted=0 OR is_deleted IS NULL) "
                    "FOR UPDATE"
                ),
                {"ds_id": datasource_id},
            ).mappings()
        }
        incoming_ids = {r.id for r in unique if r.id is not None and r.id in existing_ids}
        for old_id in existing_ids - incoming_ids:
            conn.execute(
                text("UPDATE logical_relation SET is_deleted=1 WHERE id=:id"),
                {"id": old_id},
            )
        for rel in unique:
            if rel.id is not None and rel.id in existing_ids:
                conn.execute(
                    text(
                        "UPDATE logical_relation SET "
                        "source_table_name=:st, source_column_name=:sc, "
                        "target_table_name=:tt, target_column_name=:tc, "
                        "relation_type=:rtype, description=:desc "
                        "WHERE id=:id AND datasource_id=:ds_id"
                    ),
                    {
                        "id": rel.id,
                        "ds_id": datasource_id,
                        "st": rel.sourceTableName,
                        "sc": rel.sourceColumnName,
                        "tt": rel.targetTableName,
                        "tc": rel.targetColumnName,
                        "rtype": rel.relationType,
                        "desc": rel.description,
                    },
                )
            else:
                conn.execute(
                    text(
                        "INSERT INTO logical_relation "
                        "(datasource_id, source_table_name, source_column_name, "
                        "target_table_name, target_column_name, relation_type, description, is_deleted) "
                        "VALUES (:ds_id, :st, :sc, :tt, :tc, :rtype, :desc, 0)"
                    ),
                    {
                        "ds_id": datasource_id,
                        "st": rel.sourceTableName,
                        "sc": rel.sourceColumnName,
                        "tt": rel.targetTableName,
                        "tc": rel.targetColumnName,
                        "rtype": rel.relationType,
                        "desc": rel.description,
                    },
                )
        items = load_logical_relations(conn, datasource_id)
    return response(items, "success save logical relations")
