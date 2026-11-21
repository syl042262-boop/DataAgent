"""History, idempotent display messages and read-only durable run discovery."""

import asyncio
import base64
import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.agents import authorize_agent, camel_row
from app.local_files import validate_file_references

router = APIRouter()
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}


def decode_json(value):
    return json.loads(value) if isinstance(value, str) else value


def owned_session(conn, sid, request, agent_id=None, lock=False):
    row = (
        conn.execute(
            text(
                "SELECT * FROM chat_session WHERE id=:sid AND status<>'deleted'"
                + (" FOR UPDATE" if lock else "")
            ),
            {"sid": sid},
        )
        .mappings()
        .first()
    )
    if row is None or (agent_id is not None and row["agent_id"] != agent_id):
        raise HTTPException(404, "会话不存在")
    authorize_agent(conn, row["agent_id"], request)
    return row


def message_row(row):
    item = camel_row(row)
    # Java ChatMessage exposes metadata as a JSON string.
    if item.get("metadata") is not None and not isinstance(item["metadata"], str):
        item["metadata"] = json.dumps(item["metadata"], ensure_ascii=False)
    return item


class MessageInput(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str
    messageType: str = Field(default="text", max_length=50)
    metadata: str | dict | None = None
    titleNeeded: bool = False


@router.get("/api/sessions/{sid}/messages")
def messages(sid: str, request: Request):
    with request.app.state.engine.connect() as conn:
        owned_session(conn, sid, request)
        return [
            message_row(r)
            for r in conn.execute(
                text("SELECT * FROM chat_message WHERE session_id=:sid ORDER BY create_time,id"),
                {"sid": sid},
            ).mappings()
        ]


@router.post("/api/sessions/{sid}/messages")
def save_message(sid: str, body: MessageInput, request: Request):
    try:
        metadata = decode_json(body.metadata) if body.metadata is not None else {}
        if not isinstance(metadata, dict):
            raise TypeError()
    except (ValueError, TypeError):
        raise HTTPException(400, "metadata 必须是 JSON 对象") from None
    key = metadata.get("messageKey")
    if key is not None and (not isinstance(key, str) or not key or len(key) > 191):
        raise HTTPException(400, "messageKey 无效")
    with request.app.state.knowledge.lock, request.app.state.engine.begin() as conn:
        session = owned_session(conn, sid, request, lock=True)
        validate_file_references(conn, request.app.state.settings, body.content, metadata)
        if key:
            old = (
                conn.execute(
                    text(
                        "SELECT m.* FROM chat_message m JOIN chat_message_key k ON k.message_id=m.id "
                        "WHERE k.session_id=:sid AND k.message_key=:key"
                    ),
                    {"sid": sid, "key": key},
                )
                .mappings()
                .first()
            )
            if old:
                if (
                    old["content"],
                    old["role"],
                    old["message_type"],
                    decode_json(old["metadata"]),
                ) != (body.content, body.role, body.messageType, metadata):
                    raise HTTPException(409, "同一 messageKey 的消息内容不同")
                return message_row(old)
        inserted = conn.execute(
            text(
                "INSERT INTO chat_message (session_id,role,content,message_type,metadata) "
                "VALUES (:sid,:role,:content,:kind,:meta)"
            ),
            {
                "sid": sid,
                "role": body.role,
                "content": body.content,
                "kind": body.messageType,
                "meta": json.dumps(metadata, ensure_ascii=False),
            },
        )
        mid = inserted.lastrowid
        if key:
            conn.execute(
                text("INSERT INTO chat_message_key VALUES (:sid,:key,:mid)"),
                {"sid": sid, "key": key, "mid": mid},
            )
        title = session["title"]
        if body.titleNeeded and body.role == "user" and title == "新会话":
            title = body.content.strip()[:60] or title
        conn.execute(
            text(
                "UPDATE chat_session SET title=:title, update_time=CURRENT_TIMESTAMP WHERE id=:sid"
            ),
            {"sid": sid, "title": title},
        )
        return message_row(
            conn.execute(text("SELECT * FROM chat_message WHERE id=:mid"), {"mid": mid})
            .mappings()
            .one()
        )


@router.put("/api/sessions/{sid}/pin")
def pin(sid: str, request: Request, isPinned: bool):
    with request.app.state.engine.begin() as conn:
        owned_session(conn, sid, request, lock=True)
        conn.execute(
            text("UPDATE chat_session SET is_pinned=:p WHERE id=:sid"), {"p": isPinned, "sid": sid}
        )
    return {"success": True, "message": "会话置顶已更新", "data": None}


@router.put("/api/sessions/{sid}/rename")
def rename(sid: str, request: Request, title: str = Query(max_length=255)):
    if not title.strip():
        raise HTTPException(400, "标题不能为空")
    with request.app.state.engine.begin() as conn:
        owned_session(conn, sid, request, lock=True)
        conn.execute(
            text("UPDATE chat_session SET title=:t WHERE id=:sid"), {"t": title.strip(), "sid": sid}
        )
    return {"success": True, "message": "会话已重命名", "data": None}


def envelope(data):
    return {"success": True, "message": "获取成功", "data": data}


@router.get('/api/sessions/{sid}/active-run')
async def active_run(sid: str, request: Request, agentId: int | None = None):
    with request.app.state.engine.connect() as conn:
        session = owned_session(conn, sid, request, agentId)
        row = conn.execute(text(
            'SELECT r.* FROM agent_session_runtime s JOIN agent_run r '
            'ON r.thread_id=s.active_thread_id WHERE s.agent_id=:aid AND s.conversation_id=:sid'
        ), {'aid': session['agent_id'], 'sid': sid}).mappings().first()
        if row is None:
            return envelope(None)
        effects = conn.execute(text(
            "SELECT COUNT(*) FROM graph_effect WHERE thread_id=:tid AND status='IN_FLIGHT'"
        ), {'tid': row['thread_id']}).scalar_one()
    plan = decode_json(row['plan'])
    recoverable = False
    if row['status'] == 'WAITING_FEEDBACK' and row['checkpoint_id'] and not effects:
        saved = await request.app.state.saver.aget_tuple({'configurable': {
            'thread_id': row['thread_id'], 'checkpoint_id': row['checkpoint_id'],
        }})
        if saved:
            values = saved.checkpoint.get('channel_values', {})
            recoverable = values.get('plan') == plan and values.get('planRevision') == row['plan_revision']
    original = decode_json(row['request']) or {}
    return envelope({
        'agentId': row['agent_id'], 'conversationId': sid, 'threadId': row['thread_id'],
        'status': row['status'], 'planRevision': row['plan_revision'], 'plan': plan,
        'resumeRequest': {key: original.get(key) for key in ('query', 'humanFeedback', 'nl2sqlOnly')},
        'recoverable': recoverable,
    })


def utc(value):
    return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z") if value else None


@router.get("/api/sessions/{sid}/runs")
def runs(
    sid: str,
    request: Request,
    agentId: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = None,
):
    params: dict = {"sid": sid, "aid": agentId, "count": limit + 1}
    condition = ""
    if cursor is not None:
        try:
            stamp, tid = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            params.update(stamp=datetime.fromisoformat(stamp), tid=str(tid))
            condition = " AND (r.created_at < :stamp OR (r.created_at=:stamp AND r.thread_id<:tid))"
        except (ValueError, TypeError, UnicodeError):
            raise HTTPException(400, "cursor 无效") from None
    with request.app.state.engine.connect() as conn:
        session = owned_session(conn, sid, request, agentId)
        params["aid"] = session["agent_id"]
        rows = (
            conn.execute(
                text(
                    "SELECT r.thread_id,r.status,r.created_at,r.finished_at,r.result_version,x.outcome "
                    "FROM agent_run r LEFT JOIN agent_run_result x ON x.thread_id=r.thread_id "
                    "WHERE r.conversation_id=:sid AND r.agent_id=:aid"
                    + condition
                    + " ORDER BY r.created_at DESC,r.thread_id DESC LIMIT :count"
                ),
                params,
            )
            .mappings()
            .all()
        )
        active = conn.execute(
            text(
                "SELECT active_thread_id FROM agent_session_runtime "
                "WHERE agent_id=:aid AND conversation_id=:sid"
            ),
            params,
        ).scalar()
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = base64.urlsafe_b64encode(
                json.dumps([last["created_at"].isoformat(), last["thread_id"]]).encode()
            ).decode()
        return envelope(
            {
                "items": [
                    {
                        "threadId": r["thread_id"],
                        "status": r["status"],
                        "outcome": r["outcome"] if r["status"] in TERMINAL else None,
                        "resultVersion": r["result_version"],
                        "finishedAt": utc(r["finished_at"]),
                        "hasResult": r["status"] in TERMINAL and r["outcome"] is not None,
                    }
                    for r in rows[:limit]
                ],
                "nextCursor": next_cursor,
                "activeThreadId": active,
            }
        )


@router.get("/api/sessions/{sid}/runs/{tid}")
def run_detail(sid: str, tid: str, request: Request, agentId: int | None = None):
    with request.app.state.engine.connect() as conn:
        session = owned_session(conn, sid, request, agentId)
        agentId = session["agent_id"]
        row = (
            conn.execute(
                text(
                    "SELECT thread_id,status,version FROM agent_run "
                    "WHERE thread_id=:tid AND agent_id=:aid AND conversation_id=:sid"
                ),
                {"tid": tid, "aid": agentId, "sid": sid},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise HTTPException(404, "运行不存在")
        result = None
        if row["status"] in TERMINAL:
            snapshot = (
                conn.execute(
                    text(
                        "SELECT result_version,outcome,final_answer,artifacts,"
                        "messages,reason FROM agent_run_result WHERE thread_id=:tid"
                    ),
                    {"tid": tid},
                )
                .mappings()
                .first()
            )
            if snapshot:
                result = camel_row(snapshot)
                for field in ("artifacts", "messages"):
                    result[field] = decode_json(result[field])
        return envelope(
            {"threadId": tid, "status": row["status"], "version": row["version"], "result": result}
        )


@router.get("/api/agent/{agent_id}/sessions/stream")
def titles(agent_id: int, request: Request):
    def read():
        with request.app.state.engine.connect() as conn:
            authorize_agent(conn, agent_id, request)
            return dict(
                conn.execute(
                    text(
                        "SELECT id,title FROM chat_session WHERE agent_id=:aid "
                        "AND status<>'deleted'"
                    ),
                    {"aid": agent_id},
                )
                .tuples()
                .all()
            )

    initial = read()  # Authenticate before sending SSE headers.

    async def events():
        previous = initial
        while not await request.is_disconnected():
            current = await run_in_threadpool(read)
            for sid, title in current.items():
                if previous.get(sid) != title:
                    data = json.dumps(
                        {"type": "title-updated", "sessionId": sid, "title": title},
                        ensure_ascii=False,
                    )
                    yield f"event: title-updated\ndata: {data}\n\n"
            previous = current
            yield ": heartbeat\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )
