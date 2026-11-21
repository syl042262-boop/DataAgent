"""SSE graph streaming endpoint (Ticket 03: GET /api/stream/search)."""

import asyncio
import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.agents import authorize_agent, lock_agent
from app.effective_config import read_effective_config
from app.query_cancellation import stop_query
from app.query_graph import QueryGraphState, build_query_graph
from app.run_coordination import (
    CoordinationUnavailableError,
    RunCancelledError,
    RunCoordinator,
    RunHandle,
    SessionBusyError,
    UncertainExecutionError,
)
from app.sessions import require_session

router = APIRouter(prefix="/api/stream")


@router.post('/stop', status_code=204)
def stop_run(request: Request, agentId: int, conversationId: str, threadId: str | None = None):
    if agentId <= 0 or not conversationId.strip():
        raise HTTPException(400, 'agentId 和 conversationId 必填')
    engine = request.app.state.engine
    coordinator = RunCoordinator(engine, request.app.state.redis)
    with coordinator._session_lock(agentId, conversationId) as (conn, _):
        authorize_agent(conn, agentId, request)
        row = conn.execute(text(
            'SELECT * FROM agent_run WHERE agent_id=:aid AND conversation_id=:cid '
            + ('AND thread_id=:tid ' if threadId else '')
            + 'ORDER BY created_at DESC LIMIT 1 FOR UPDATE'
        ), {'aid': agentId, 'cid': conversationId, 'tid': threadId}).mappings().first()
        if row is None:
            if threadId:
                raise HTTPException(404, '运行记录不存在')
            return Response(status_code=204)
        if row['status'] in {'COMPLETED', 'FAILED', 'CANCELLED'}:
            return Response(status_code=204)
        if row['status'] == 'RECOVERY_REQUIRED':
            raise HTTPException(409, '运行需要对账，不能直接释放会话')
        waiting = row['status'] == 'WAITING_FEEDBACK'
        conn.execute(text("UPDATE agent_run SET status='CANCELLING', version=version+1 "
                          'WHERE thread_id=:tid'), {'tid': row['thread_id']})
        handle = RunHandle(row['thread_id'], agentId, conversationId,
                           row['version'] + 1, row['owner'])
    if waiting:
        coordinator.cancel_run(handle)
    else:
        try:
            stop_query(handle.thread_id)
        except Exception as exc:
            coordinator.mark_recovery_required(handle, reason='无法确认数据库停止')
            raise HTTPException(409, '无法确认停止，请对账后处理') from exc
    return Response(status_code=204)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _error_payload(agent_id: int, thread_id: str, message: str) -> dict[str, Any]:
    return {
        "agentId": str(agent_id),
        "threadId": thread_id,
        "nodeName": "StreamGuard",
        "textType": "TEXT",
        "text": message,
        "error": True,
        "complete": False,
    }


def _complete_payload(agent_id: int, thread_id: str) -> dict[str, Any]:
    return {
        "agentId": str(agent_id),
        "threadId": thread_id,
        "nodeName": "",
        "textType": "TEXT",
        "text": "",
        "error": False,
        "complete": True,
    }


def _build_config_snapshot(engine, models, agent_id: int, settings=None) -> tuple[dict[str, Any], str]:
    with engine.connect() as conn:
        try:
            effective = read_effective_config(conn, agent_id, settings)
            return effective["config"], effective["configFingerprint"]
        except ValueError:
            snapshot: dict[str, Any] = {"agentId": agent_id}
            canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
            return snapshot, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.get("/search")
async def stream_search(
    request: Request,
    agentId: str,
    query: str = "",
    conversationId: str | None = None,
    threadId: str | None = None,
    humanFeedback: bool = False,
    humanFeedbackContent: str | None = None,
    rejectedPlan: bool = False,
    nl2sqlOnly: bool = False,
    feedbackRevision: int | None = None,
):
    try:
        parsed_agent_id = int(agentId)
        if parsed_agent_id <= 0:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "agentId 必须是正整数") from None

    if not humanFeedback and not query.strip():
        raise HTTPException(400, "query 不能为空")

    engine = request.app.state.engine
    with engine.connect() as conn:
        authorize_agent(conn, parsed_agent_id, request)
        if conversationId:
            require_session(conn, parsed_agent_id, conversationId)
        if humanFeedback and threadId:
            owner_match = conn.execute(
                text(
                    "SELECT 1 FROM agent_run WHERE thread_id=:tid AND agent_id=:aid "
                    + ("AND conversation_id=:cid" if conversationId else "")
                ),
                {"tid": threadId, "aid": parsed_agent_id, "cid": conversationId},
            ).scalar()
            if owner_match != 1:
                raise HTTPException(404, "运行记录不存在")

    session_id = conversationId or str(uuid.uuid4())
    if not conversationId:
        with engine.begin() as conn:
            lock_agent(conn, parsed_agent_id)
            conn.execute(
                text(
                    "INSERT INTO chat_session (id, agent_id, title, status, is_pinned) "
                    "VALUES (:id, :aid, '新会话', 'active', 0)"
                ),
                {"id": session_id, "aid": parsed_agent_id},
            )

    is_resume = bool(humanFeedback and threadId)
    run_thread_id = threadId if is_resume and threadId else str(uuid.uuid4())

    coordinator = RunCoordinator(
        engine,
        request.app.state.redis,
        ttl_ms=request.app.state.settings.redis_lock_ttl_ms,
        runtime_request=request,
    )
    models = request.app.state.models
    saver = request.app.state.saver
    timeout = request.app.state.settings.model_timeout
    run_ready = asyncio.Event()

    async def run_events():
        handle: RunHandle | None = None
        try:
            if is_resume:
                handle = await run_in_threadpool(
                    coordinator.resume_run,
                    thread_id=run_thread_id,
                    agent_id=parsed_agent_id,
                    conversation_id=session_id,
                    feedback_revision=feedbackRevision,
                )
            else:
                snapshot, fingerprint = await run_in_threadpool(
                    _build_config_snapshot, engine, models, parsed_agent_id, request.app.state.settings
                )
                req_payload = {
                    "query": query,
                    "humanFeedback": humanFeedback,
                    "nl2sqlOnly": nl2sqlOnly,
                }
                handle = await run_in_threadpool(
                    coordinator.create_run,
                    thread_id=run_thread_id,
                    agent_id=parsed_agent_id,
                    conversation_id=session_id,
                    request_payload=req_payload,
                    config_snapshot=snapshot,
                    config_fingerprint=fingerprint,
                )
            run_ready.set()
        except (CoordinationUnavailableError, SessionBusyError, ValueError, HTTPException) as exc:
            msg = exc.detail if isinstance(exc, HTTPException) else str(exc)
            yield _sse("error", _error_payload(parsed_agent_id, run_thread_id, msg))
            return

        runnable = build_query_graph(
            engine=engine,
            models=models,
            coordinator=coordinator,
            saver=saver,
            model_timeout=timeout,
            knowledge=request.app.state.knowledge,
        )
        config: RunnableConfig = {"configurable": {"thread_id": run_thread_id},
                                  "recursion_limit": 200}

        try:
            await run_in_threadpool(coordinator.validate_configuration, run_thread_id)
            if is_resume:
                graph_input: Any = Command(
                    resume={
                        "accepted": not rejectedPlan,
                        "content": humanFeedbackContent or "",
                        "feedbackRevision": feedbackRevision,
                    }
                )
            else:
                initial_state: QueryGraphState = {
                    "schemaVersion": 1,
                    "agentId": parsed_agent_id,
                    "conversationId": session_id,
                    "threadId": run_thread_id,
                    "request": {
                        "query": query,
                        "humanFeedback": humanFeedback,
                        "nl2sqlOnly": nl2sqlOnly,
                        "humanFeedbackContent": humanFeedbackContent,
                        "rejectedPlan": rejectedPlan,
                    },
                    "planRevision": 0,
                    "attempts": {},
                }
                graph_input = initial_state

            async for mode, chunk in runnable.astream(
                graph_input, config, stream_mode=["updates", "custom"]
            ):
                if mode == "custom" and isinstance(chunk, dict):
                    yield _sse("message", chunk)

            snapshot_state = await runnable.aget_state(config)
            values = snapshot_state.values or {}

            if snapshot_state.next:
                plan = values.get("plan") or {}
                plan_rev = int(values.get("planRevision") or 1)
                cp_id = snapshot_state.config.get("configurable", {}).get("checkpoint_id")
                await run_in_threadpool(
                    coordinator.pause_for_feedback,
                    handle,
                    plan=plan,
                    plan_revision=plan_rev,
                    checkpoint_id=cp_id,
                )
                step_ids = values.get("lastStepIds") or {}
                yield _sse(
                    "message",
                    {
                        "agentId": str(parsed_agent_id),
                        "threadId": run_thread_id,
                        "eventType": "HUMAN_FEEDBACK_REQUIRED",
                        "stepId": step_ids.get("PlannerNode", f"PlannerNode:1:{run_thread_id[:8]}"),
                        "attempt": int((values.get("attempts") or {}).get("PlannerNode", 1)),
                        "nodeName": "PlannerNode",
                        "textType": "JSON",
                        "text": "",
                        "planRevision": plan_rev,
                        "plan": plan,
                        "error": False,
                        "complete": False,
                    },
                )
                yield _sse("complete", _complete_payload(parsed_agent_id, run_thread_id))
                return

            final_answer = str(values.get("finalAnswer") or "")
            await run_in_threadpool(
                coordinator.complete_run,
                handle,
                final_answer=final_answer,
                sql_text=values.get("sql"),
                result_ref=values.get("resultRef"),
                plan=values.get("plan"),
                plan_revision=int(values.get("planRevision") or 0),
                outcome=values.get('outcome') or 'SUCCESS',
                report=values.get('report'),
            )
            step_ids = values.get("lastStepIds") or {}
            yield _sse(
                "message",
                {
                    "agentId": str(parsed_agent_id),
                    "threadId": run_thread_id,
                    "eventType": "FINAL_ANSWER",
                    "stepId": step_ids.get("AnswerNode", f"AnswerNode:1:{run_thread_id[:8]}"),
                    "attempt": int((values.get("attempts") or {}).get("AnswerNode", 1)),
                    "nodeName": "AnswerNode",
                    "textType": "MARK_DOWN",
                    "text": final_answer,
                    "error": False,
                    "complete": False,
                },
            )
            yield _sse("complete", _complete_payload(parsed_agent_id, run_thread_id))
        except RunCancelledError as exc:
            await run_in_threadpool(coordinator.cancel_run, handle)
            yield _sse('error', _error_payload(parsed_agent_id, run_thread_id, str(exc)))
        except UncertainExecutionError as exc:
            await run_in_threadpool(coordinator.mark_recovery_required, handle, reason=str(exc))
            yield _sse("error", _error_payload(parsed_agent_id, run_thread_id, str(exc)))
        except Exception as exc:  # noqa: BLE001 - convert any graph failure to terminal SSE error event
            await run_in_threadpool(coordinator.fail_run, handle, reason=str(exc))
            yield _sse("error", _error_payload(parsed_agent_id, run_thread_id, str(exc)))

    async def event_generator():
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        detached = False

        async def produce():
            try:
                async for event in run_events():
                    if not detached:
                        queue.put_nowait(event)
            finally:
                run_ready.set()
                queue.put_nowait(None)

        tasks = request.app.state.stream_tasks
        producer = asyncio.create_task(produce())
        tasks.add(producer)
        producer.add_done_callback(tasks.discard)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    await producer
                    return
                yield event
        finally:
            detached = True
            if not producer.done():
                # Preserve the execution task until native SQL has actually returned.
                # Cancelling its coroutine would leave its worker thread unobserved.
                async def stop_detached():
                    try:
                        await run_ready.wait()
                        if producer.done():
                            return
                        await run_in_threadpool(
                            stop_run, request, parsed_agent_id, session_id, run_thread_id,
                        )
                    except HTTPException:
                        pass  # Stop already persisted uncertainty; startup/CLI will reconcile.

                cleanup = asyncio.create_task(stop_detached())
                tasks.add(cleanup)
                cleanup.add_done_callback(tasks.discard)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
