"""Bindings serialize on the Agent row; FK cascades remove selections and snapshots."""

import json

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents import camel_row, lock_agent, require_agent, response
from app.datasources import public_datasource, require_datasource, schema_snapshot


class Selection(BaseModel):
    datasourceId: int
    tables: list[str] | None = Field(default=None, max_length=1000)


class Toggle(BaseModel):
    datasourceId: int
    isActive: bool


def binding(connection, agent_id, datasource_id):
    row = (
        connection.execute(
            text("SELECT * FROM agent_datasource WHERE agent_id=:a AND datasource_id=:d"),
            {"a": agent_id, "d": datasource_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError("未找到对应的数据源关联记录")
    result = camel_row(row)
    result["selectTables"] = list(
        connection.execute(
            text(
                "SELECT table_name FROM agent_datasource_tables WHERE agent_datasource_id=:id ORDER BY id"
            ),
            {"id": row["id"]},
        ).scalars()
    )
    result["datasource"] = public_datasource(require_datasource(connection, datasource_id))
    result["schemaInitialized"] = (
        connection.execute(
            text("SELECT 1 FROM python_agent_schema WHERE agent_datasource_id=:id"),
            {"id": row["id"]},
        ).scalar()
        == 1
    )
    return result


def current_binding(connection, agent_id):
    require_agent(connection, agent_id)
    datasource_id = connection.execute(
        text("SELECT datasource_id FROM agent_datasource WHERE agent_id=:a AND is_active=1"),
        {"a": agent_id},
    ).scalar()
    if datasource_id is None:
        raise ValueError("未配置活动数据源")
    return binding(connection, agent_id, datasource_id)


def invalidate_schema(connection, binding_id):
    connection.execute(
        text("DELETE FROM python_agent_schema WHERE agent_datasource_id=:id"), {"id": binding_id}
    )


router = APIRouter(prefix="/api/agent/{agent_id}/datasources")


@router.get("")
def bindings(agent_id: int, request: Request):
    with request.app.state.engine.connect() as connection:
        require_agent(connection, agent_id)
        ids = (
            connection.execute(
                text("SELECT datasource_id FROM agent_datasource WHERE agent_id=:a ORDER BY id"),
                {"a": agent_id},
            )
            .scalars()
            .all()
        )
        return response([binding(connection, agent_id, i) for i in ids])


@router.get("/active")
def active(agent_id: int, request: Request):
    with request.app.state.engine.connect() as connection:
        return response(current_binding(connection, agent_id))


@router.post("/tables")
def select_tables(agent_id: int, body: Selection, request: Request):
    selected = list(dict.fromkeys(body.tables or []))
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, agent_id)
        source = require_datasource(connection, body.datasourceId, lock=True)
        existing = binding(connection, agent_id, body.datasourceId)
        if selected:
            schema_snapshot(source, selected)  # Validate before replacing existing selection.
        connection.execute(
            text("DELETE FROM agent_datasource_tables WHERE agent_datasource_id=:id"),
            {"id": existing["id"]},
        )
        for table in selected:
            connection.execute(
                text(
                    "INSERT INTO agent_datasource_tables "
                    "(agent_datasource_id,table_name) VALUES (:id,:name)"
                ),
                {"id": existing["id"], "name": table},
            )
        invalidate_schema(connection, existing["id"])
    return response(message="更新成功")


@router.put("/toggle")
def toggle(agent_id: int, body: Toggle, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, agent_id)
        require_datasource(connection, body.datasourceId, lock=True)
        binding(connection, agent_id, body.datasourceId)
        if body.isActive:
            other = connection.execute(
                text(
                    "SELECT id FROM agent_datasource WHERE agent_id=:a "
                    "AND datasource_id<>:d AND is_active=1"
                ),
                {"a": agent_id, "d": body.datasourceId},
            ).first()
            if other:
                raise ValueError("同一智能体下只能启用一个数据源，请先禁用其他数据源")
        connection.execute(
            text(
                "UPDATE agent_datasource SET is_active=:flag WHERE agent_id=:a AND datasource_id=:d"
            ),
            {"a": agent_id, "d": body.datasourceId, "flag": int(body.isActive)},
        )
        return response(binding(connection, agent_id, body.datasourceId))


@router.post("/init")
def initialize(agent_id: int, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, agent_id)
        current = current_binding(connection, agent_id)
        source = require_datasource(connection, current["datasourceId"], lock=True)
        if not current["selectTables"]:
            raise ValueError("表列表不能为空")
        snapshot = schema_snapshot(source, current["selectTables"])
        connection.execute(
            text(
                "INSERT INTO python_agent_schema(agent_datasource_id,schema_snapshot) "
                "VALUES (:id,:snapshot) ON DUPLICATE KEY UPDATE "
                "schema_snapshot=:snapshot,initialized_at=CURRENT_TIMESTAMP(6)"
            ),
            {"id": current["id"], "snapshot": json.dumps(snapshot)},
        )
    return response(message="Schema初始化成功")


@router.post("/{datasource_id}")
def bind(agent_id: int, datasource_id: int, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, agent_id)
        require_datasource(connection, datasource_id, lock=True)
        connection.execute(
            text("UPDATE agent_datasource SET is_active=0 WHERE agent_id=:a"), {"a": agent_id}
        )
        connection.execute(
            text(
                "INSERT INTO agent_datasource(agent_id,datasource_id,is_active) "
                "VALUES (:a,:d,1) ON DUPLICATE KEY UPDATE is_active=1"
            ),
            {"a": agent_id, "d": datasource_id},
        )
        current = binding(connection, agent_id, datasource_id)
        # Preserve Java re-bind behavior: reactivating via POST clears the selection.
        connection.execute(
            text("DELETE FROM agent_datasource_tables WHERE agent_datasource_id=:id"),
            {"id": current["id"]},
        )
        invalidate_schema(connection, current["id"])
        return response(binding(connection, agent_id, datasource_id), "数据源添加成功")


@router.delete("/{datasource_id}")
def unbind(agent_id: int, datasource_id: int, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, agent_id)
        require_datasource(connection, datasource_id, lock=True)
        connection.execute(
            text("DELETE FROM agent_datasource WHERE agent_id=:a AND datasource_id=:d"),
            {"a": agent_id, "d": datasource_id},
        )
    return response(message="数据源已移除")
