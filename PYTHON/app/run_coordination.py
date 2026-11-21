"""Redis short-lock + MySQL session occupancy, run state machine, and graph_effect ledger."""

import json
import os
import secrets
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import psutil
import redis
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.agents import authorize_agent, lock_agent
from app.effective_config import read_effective_config
from app.sessions import require_session

_LUA_RENEW = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""

_LUA_RELEASE = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class CoordinationUnavailableError(RuntimeError):
    """Raised when Redis coordination storage is unreachable."""


class SessionBusyError(RuntimeError):
    """Raised when the conversation already has an active non-terminal run."""


class UncertainExecutionError(RuntimeError):
    """Raised when an IN_FLIGHT effect cannot be safely re-run."""


class RunCancelledError(RuntimeError):
    """Cooperative cancellation observed before another external operation."""


class RedisLock:
    def __init__(self, client: redis.Redis):
        self._client = client

    def acquire(self, key: str, ttl_ms: int) -> str:
        token = secrets.token_hex(16)
        try:
            acquired = self._client.set(key, token, nx=True, px=ttl_ms)
        except redis.RedisError as exc:
            raise CoordinationUnavailableError("协调存储不可用，无法创建或恢复运行") from exc
        if not acquired:
            raise SessionBusyError("当前会话已有运行中的任务")
        return token

    def renew(self, key: str, token: str, ttl_ms: int) -> bool:
        try:
            return bool(self._client.eval(_LUA_RENEW, 1, key, token, str(ttl_ms)))
        except redis.RedisError as exc:
            raise CoordinationUnavailableError("协调存储不可用") from exc

    def release(self, key: str, token: str) -> bool:
        try:
            return bool(self._client.eval(_LUA_RELEASE, 1, key, token))
        except redis.RedisError:
            return False


@dataclass
class RunHandle:
    thread_id: str
    agent_id: int
    conversation_id: str
    version: int
    owner: str


def _lock_key(agent_id: int, conversation_id: str) -> str:
    return f"dataagent:run:{agent_id}:{conversation_id}"


def worker_identity():
    return {'pid': os.getpid(), 'started': psutil.Process().create_time(),
            'host': socket.gethostname()}


class RunCoordinator:
    def __init__(self, engine: Engine, redis_client: redis.Redis, ttl_ms: int = 30000,
                 runtime_request: Any | None = None):
        self._engine = engine
        self._lock = RedisLock(redis_client)
        self._ttl_ms = ttl_ms
        self._runtime_request = runtime_request

    def validate_configuration(self, thread_id: str) -> None:
        with self._engine.connect() as conn:
            run = conn.execute(text(
                'SELECT agent_id,status,config_fingerprint FROM agent_run WHERE thread_id=:tid'
            ), {'tid': thread_id}).mappings().one()
            if run['status'] == 'CANCELLING':
                raise RunCancelledError('运行已取消')
            if run['status'] == 'RECOVERY_REQUIRED':
                raise UncertainExecutionError('运行需要对账，禁止继续外部操作')
            if self._runtime_request is not None:
                authorize_agent(conn, run['agent_id'], self._runtime_request)
            try:
                settings = (self._runtime_request.app.state.settings
                            if self._runtime_request is not None else None)
                current = read_effective_config(conn, run['agent_id'], settings)['configFingerprint']
            except Exception as exc:
                raise ValueError('CONFIG_CHANGED: 无法确认当前配置，请重新提问') from exc
            if current != run['config_fingerprint']:
                raise ValueError('CONFIG_CHANGED: 运行配置已变化，请重新提问')

    @contextmanager
    def _session_lock(self, agent_id: int, conversation_id: str):
        key = _lock_key(agent_id, conversation_id)
        token = self._lock.acquire(key, self._ttl_ms)
        try:
            with self._engine.begin() as conn:
                lock_agent(conn, agent_id)
                require_session(conn, agent_id, conversation_id)
                yield conn, token
        finally:
            self._lock.release(key, token)

    def create_run(
        self,
        *,
        thread_id: str,
        agent_id: int,
        conversation_id: str,
        request_payload: dict[str, Any],
        config_snapshot: dict[str, Any],
        config_fingerprint: str,
    ) -> RunHandle:
        with self._session_lock(agent_id, conversation_id) as (conn, token):
            conn.execute(
                text(
                    "INSERT IGNORE INTO agent_session_runtime (agent_id, conversation_id) "
                    "VALUES (:aid, :cid)"
                ),
                {"aid": agent_id, "cid": conversation_id},
            )
            runtime = (
                conn.execute(
                    text(
                        "SELECT active_thread_id, lifecycle FROM agent_session_runtime "
                        "WHERE agent_id=:aid AND conversation_id=:cid FOR UPDATE"
                    ),
                    {"aid": agent_id, "cid": conversation_id},
                )
                .mappings()
                .one()
            )
            if runtime["lifecycle"] != "OPEN":
                raise SessionBusyError("当前会话正在清理中")
            if runtime["active_thread_id"] is not None:
                raise SessionBusyError("当前会话已有运行中的任务")

            conn.execute(
                text(
                    "INSERT INTO agent_run "
                    "(thread_id, agent_id, conversation_id, request, status, plan_revision, "
                    "version, owner, config_snapshot, config_fingerprint) "
                    "VALUES (:tid, :aid, :cid, :req, 'RUNNING', 0, 1, :owner, :snap, :fp)"
                ),
                {
                    "tid": thread_id,
                    "aid": agent_id,
                    "cid": conversation_id,
                    "req": json.dumps({**request_payload, '_worker': worker_identity()}, ensure_ascii=False),
                    "owner": token,
                    "snap": json.dumps(config_snapshot, ensure_ascii=False),
                    "fp": config_fingerprint,
                },
            )
            conn.execute(
                text(
                    "INSERT INTO agent_conversation_turn "
                    "(agent_id, conversation_id, thread_id, question, plan_revision, memory_status) "
                    "VALUES (:aid, :cid, :tid, :q, 0, 'STAGED')"
                ),
                {
                    "aid": agent_id,
                    "cid": conversation_id,
                    "tid": thread_id,
                    "q": str(request_payload.get("query") or ""),
                },
            )
            updated = conn.execute(
                text(
                    "UPDATE agent_session_runtime "
                    "SET active_thread_id=:tid, version=version+1 "
                    "WHERE agent_id=:aid AND conversation_id=:cid AND active_thread_id IS NULL"
                ),
                {"tid": thread_id, "aid": agent_id, "cid": conversation_id},
            )
            if updated.rowcount != 1:
                raise SessionBusyError("当前会话已有运行中的任务")
        return RunHandle(
            thread_id=thread_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            version=1,
            owner=token,
        )

    def resume_run(
        self,
        *,
        thread_id: str,
        agent_id: int,
        conversation_id: str,
        feedback_revision: int | None = None,
    ) -> RunHandle:
        with self._session_lock(agent_id, conversation_id) as (conn, token):
            runtime = (
                conn.execute(
                    text(
                        "SELECT active_thread_id FROM agent_session_runtime "
                        "WHERE agent_id=:aid AND conversation_id=:cid FOR UPDATE"
                    ),
                    {"aid": agent_id, "cid": conversation_id},
                )
                .mappings()
                .first()
            )
            if runtime is None or runtime["active_thread_id"] != thread_id:
                raise ValueError("当前运行未占用该会话或已结束")
            run_row = (
                conn.execute(
                    text(
                        "SELECT status, version, plan_revision FROM agent_run "
                        "WHERE thread_id=:tid AND agent_id=:aid AND conversation_id=:cid FOR UPDATE"
                    ),
                    {"tid": thread_id, "aid": agent_id, "cid": conversation_id},
                )
                .mappings()
                .first()
            )
            if run_row is None or run_row["status"] != "WAITING_FEEDBACK":
                raise ValueError("当前运行不处于待审核状态")
            plan_rev = int(run_row["plan_revision"] or 0)
            if feedback_revision is not None and feedback_revision != plan_rev:
                raise ValueError("计划版本已过期，请刷新后重试")
            if feedback_revision is None and plan_rev > 1:
                raise ValueError("缺少 feedbackRevision，请刷新页面后重试")

            expected_version = int(run_row["version"])
            resuming = conn.execute(
                text(
                    "UPDATE agent_run SET status='RESUMING', owner=:owner, version=version+1, "
                    "request=JSON_SET(request,'$._worker',JSON_OBJECT('pid',:pid,'started',:started,'host',:host)) "
                    "WHERE thread_id=:tid AND status='WAITING_FEEDBACK' AND version=:ver"
                ),
                {"owner": token, "tid": thread_id, "ver": expected_version, **worker_identity()},
            )
            if resuming.rowcount != 1:
                raise SessionBusyError("运行状态已被并发修改")
            running = conn.execute(
                text(
                    "UPDATE agent_run SET status='RUNNING', version=version+1 "
                    "WHERE thread_id=:tid AND status='RESUMING' AND version=:ver"
                ),
                {"tid": thread_id, "ver": expected_version + 1},
            )
            if running.rowcount != 1:
                raise SessionBusyError("运行状态已被并发修改")
        return RunHandle(
            thread_id=thread_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            version=expected_version + 2,
            owner=token,
        )

    def pause_for_feedback(
        self,
        handle: RunHandle,
        *,
        plan: dict[str, Any],
        plan_revision: int,
        checkpoint_id: str | None,
    ) -> None:
        with self._engine.begin() as conn:
            paused = conn.execute(
                text(
                    "UPDATE agent_run SET status='WAITING_FEEDBACK', plan=:plan, "
                    "plan_revision=:rev, checkpoint_id=:cp, version=version+1 "
                    "WHERE thread_id=:tid AND status='RUNNING' AND owner=:owner"
                ),
                {
                    "plan": json.dumps(plan, ensure_ascii=False),
                    "rev": plan_revision,
                    "cp": checkpoint_id,
                    "tid": handle.thread_id,
                    "owner": handle.owner,
                },
            )
            if paused.rowcount != 1:
                raise RunCancelledError('运行已停止，不能发布审核计划')
            conn.execute(
                text(
                    "UPDATE agent_conversation_turn SET plan=:plan, plan_revision=:rev "
                    "WHERE thread_id=:tid"
                ),
                {
                    "plan": json.dumps(plan, ensure_ascii=False),
                    "rev": plan_revision,
                    "tid": handle.thread_id,
                },
            )

    def get_effect(self, thread_id: str, effect_key: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT status, result_ref, query_id FROM graph_effect "
                        "WHERE thread_id=:tid AND effect_key=:ek"
                    ),
                    {"tid": thread_id, "ek": effect_key},
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            result_ref = row["result_ref"]
            if isinstance(result_ref, str):
                result_ref = json.loads(result_ref)
            return {
                "status": row["status"],
                "result_ref": result_ref,
                "query_id": row["query_id"],
            }

    def prepare_effect(self, thread_id: str, effect_key: str, owner: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT IGNORE INTO graph_effect (thread_id, effect_key, status, owner) "
                    "VALUES (:tid, :ek, 'PREPARED', :owner)"
                ),
                {"tid": thread_id, "ek": effect_key, "owner": owner},
            )

    def mark_effect_in_flight(self, thread_id: str, effect_key: str, query_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE graph_effect SET status='IN_FLIGHT', query_id=:qid, "
                    "updated_at=CURRENT_TIMESTAMP(6) "
                    "WHERE thread_id=:tid AND effect_key=:ek"
                ),
                {"qid": query_id, "tid": thread_id, "ek": effect_key},
            )

    def commit_effect(
        self, thread_id: str, effect_key: str, result_ref: dict[str, Any]
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE graph_effect SET status='COMMITTED', result_ref=:ref, "
                    "updated_at=CURRENT_TIMESTAMP(6) "
                    "WHERE thread_id=:tid AND effect_key=:ek"
                ),
                {
                    "ref": json.dumps(result_ref, ensure_ascii=False),
                    "tid": thread_id,
                    "ek": effect_key,
                },
            )

    def fail_effect(self, thread_id: str, effect_key: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE graph_effect SET status='FAILED', updated_at=CURRENT_TIMESTAMP(6) "
                    "WHERE thread_id=:tid AND effect_key=:ek"
                ),
                {"tid": thread_id, "ek": effect_key},
            )

    def _finish_run(
        self,
        handle: RunHandle,
        *,
        run_status: str,
        outcome: str,
        memory_status: str,
        final_answer: str | None,
        artifacts: dict[str, Any] | None,
        messages: list[dict[str, Any]],
        reason: str | None,
        plan: dict[str, Any] | None = None,
        plan_revision: int | None = None,
    ) -> None:
        with self._engine.begin() as conn:
            row = conn.execute(
                text("SELECT status,owner FROM agent_run WHERE thread_id=:tid FOR UPDATE"),
                {"tid": handle.thread_id},
            ).mappings().one()
            status = row['status']
            if row['owner'] != handle.owner:
                raise SessionBusyError('运行归属已变化')
            if status in {"COMPLETED", "FAILED", "CANCELLED"}:
                return
            if status == 'CANCELLING':
                run_status = outcome = 'CANCELLED'
                memory_status = 'DISCARDED'
                final_answer = artifacts = None
                messages = []
                reason = '用户取消运行'
            conn.execute(
                text(
                    "REPLACE INTO agent_run_result "
                    "(thread_id, result_version, outcome, final_answer, artifacts, messages, reason) "
                    "VALUES (:tid, 1, :outcome, :ans, :art, :msgs, :reason)"
                ),
                {
                    "tid": handle.thread_id,
                    "outcome": outcome,
                    "ans": final_answer,
                    "art": (
                        json.dumps(artifacts, ensure_ascii=False)
                        if artifacts is not None
                        else None
                    ),
                    "msgs": json.dumps(messages, ensure_ascii=False),
                    "reason": reason,
                },
            )
            if plan_revision is not None:
                conn.execute(
                    text(
                        "UPDATE agent_conversation_turn "
                        "SET plan=:plan, plan_revision=:rev, memory_status=:mem "
                        "WHERE thread_id=:tid"
                    ),
                    {
                        "plan": json.dumps(plan, ensure_ascii=False) if plan is not None else None,
                        "rev": plan_revision,
                        "mem": memory_status,
                        "tid": handle.thread_id,
                    },
                )
            else:
                conn.execute(
                    text(
                        "UPDATE agent_conversation_turn SET memory_status=:mem "
                        "WHERE thread_id=:tid"
                    ),
                    {"mem": memory_status, "tid": handle.thread_id},
                )
            conn.execute(
                text(
                    "UPDATE agent_run SET status=:status, error=:err, result_version=1, "
                    "finished_at=CURRENT_TIMESTAMP(6), version=version+1 "
                    "WHERE thread_id=:tid"
                ),
                {"status": run_status, "err": reason, "tid": handle.thread_id},
            )
            conn.execute(
                text(
                    "UPDATE agent_session_runtime "
                    "SET active_thread_id=NULL, version=version+1 "
                    "WHERE agent_id=:aid AND conversation_id=:cid AND active_thread_id=:tid"
                ),
                {
                    "aid": handle.agent_id,
                    "cid": handle.conversation_id,
                    "tid": handle.thread_id,
                },
            )

    def complete_run(
        self,
        handle: RunHandle,
        *,
        final_answer: str,
        sql_text: str | None,
        result_ref: dict[str, Any] | None,
        plan: dict[str, Any] | None,
        plan_revision: int,
        outcome: str = 'SUCCESS',
        report: dict[str, Any] | None = None,
    ) -> None:
        messages = [
            {
                "messageKey": f"v1:{handle.thread_id}:answer:0",
                "messageType": "text",
                "role": "assistant",
                "content": final_answer,
                "metadata": {"threadId": handle.thread_id, "resultVersion": 1},
            }
        ]
        artifacts: dict[str, Any] = {}
        if sql_text:
            artifacts["sql"] = sql_text
        if result_ref is not None:
            artifacts["resultSet"] = result_ref
        if report:
            artifacts['report'] = report
            messages.clear()
            messages.append({
                'messageKey': f'v1:{handle.thread_id}:report:0',
                'messageType': 'html', 'role': 'assistant', 'content': report['content'],
                'metadata': {'threadId': handle.thread_id, 'resultVersion': 1,
                             'reportUrl': report['url']},
            })
        self._finish_run(
            handle,
            run_status="COMPLETED",
            outcome=outcome,
            memory_status="COMMITTED" if outcome == 'SUCCESS' else 'DISCARDED',
            final_answer=final_answer,
            artifacts=artifacts,
            messages=messages,
            reason=None,
            plan=plan,
            plan_revision=plan_revision,
        )
        with self._engine.connect() as conn:
            status = conn.execute(text('SELECT status FROM agent_run WHERE thread_id=:tid'),
                                  {'tid': handle.thread_id}).scalar_one()
        if status == 'CANCELLED':
            raise RunCancelledError('运行已取消')

    def fail_run(self, handle: RunHandle, *, reason: str) -> None:
        messages = [
            {
                "messageKey": f"v1:{handle.thread_id}:error:0",
                "messageType": "error",
                "role": "assistant",
                "content": reason,
                "metadata": {"threadId": handle.thread_id, "resultVersion": 1},
            }
        ]
        self._finish_run(
            handle,
            run_status="FAILED",
            outcome="FAILED",
            memory_status="DISCARDED",
            final_answer=None,
            artifacts=None,
            messages=messages,
            reason=reason,
        )

    def cancel_run(self, handle: RunHandle) -> None:
        self._finish_run(
            handle, run_status='CANCELLED', outcome='CANCELLED', memory_status='DISCARDED',
            final_answer=None, artifacts=None, messages=[], reason='用户取消运行',
        )

    def mark_recovery_required(self, handle: RunHandle, *, reason: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE agent_run SET status='RECOVERY_REQUIRED', error=:err, "
                    "version=version+1 WHERE thread_id=:tid AND owner=:owner "
                    "AND status NOT IN ('COMPLETED','FAILED','CANCELLED')"
                ),
                {"err": reason, "tid": handle.thread_id, "owner": handle.owner},
            )
