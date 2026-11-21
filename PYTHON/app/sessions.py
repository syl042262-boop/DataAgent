"""Chat session listing and creation (Ticket 03)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents import camel_row, lock_agent, require_agent


class SessionCreateInput(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    userId: int | None = None


def session_row(row) -> dict:
    item = camel_row(row)
    item["isPinned"] = bool(item.get("isPinned"))
    return item


def require_session(connection, agent_id: int, session_id: str) -> dict:
    row = (
        connection.execute(
            text(
                "SELECT * FROM chat_session WHERE id=:sid AND agent_id=:aid AND status<>'deleted'"
            ),
            {"sid": session_id, "aid": agent_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "会话不存在")
    return dict(row)


router = APIRouter(prefix="/api/agent/{agent_id}/sessions")


@router.get("")
def list_sessions(agent_id: int, request: Request):
    with request.app.state.engine.connect() as connection:
        require_agent(connection, agent_id)
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM chat_session WHERE agent_id=:aid AND status<>'deleted' "
                    "ORDER BY is_pinned DESC, update_time DESC, create_time DESC"
                ),
                {"aid": agent_id},
            )
            .mappings()
            .all()
        )
        return [session_row(r) for r in rows]


@router.post("")
def create_session(
    agent_id: int,
    request: Request,
    body: Annotated[SessionCreateInput | None, Body()] = None,
):
    session_id = str(uuid.uuid4())
    title = body.title if body and body.title is not None else "新会话"
    user_id = body.userId if body else None
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, agent_id)
        connection.execute(
            text(
                "INSERT INTO chat_session (id, agent_id, title, status, is_pinned, user_id) "
                "VALUES (:id, :agent_id, :title, 'active', 0, :user_id)"
            ),
            {"id": session_id, "agent_id": agent_id, "title": title, "user_id": user_id},
        )
        row = (
            connection.execute(
                text("SELECT * FROM chat_session WHERE id=:id"),
                {"id": session_id},
            )
            .mappings()
            .one()
        )
        return session_row(row)
