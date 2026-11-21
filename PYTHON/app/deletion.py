"""Atomic session tombstones and durable cleanup intent under the run lifecycle gate."""

import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from app.agents import authorize_agent, lock_agent, response
from app.history import owned_session
from app.local_files import file_references

router = APIRouter()


def delete_sessions(conn, aid, session_ids):
    # The Agent row is already locked: create/resume/delete use the same order.
    for sid in sorted(session_ids):
        active = conn.execute(text(
            "SELECT thread_id FROM agent_run WHERE agent_id=:aid AND conversation_id=:sid "
            "AND status NOT IN ('COMPLETED','FAILED','CANCELLED') LIMIT 1 FOR UPDATE"
        ), {'aid': aid, 'sid': sid}).first()
        if active:
            raise HTTPException(409, '范围内存在未结束运行，不能删除')
    for sid in sorted(session_ids):
        threads = list(conn.execute(text(
            'SELECT thread_id FROM agent_run WHERE agent_id=:aid AND conversation_id=:sid'
        ), {'aid': aid, 'sid': sid}).scalars())
        files = list(conn.execute(text(
            "SELECT JSON_UNQUOTE(JSON_EXTRACT(x.artifacts,'$.report.url')) "
            'FROM agent_run_result x JOIN agent_run r ON r.thread_id=x.thread_id '
            'WHERE r.agent_id=:aid AND r.conversation_id=:sid'
        ), {'aid': aid, 'sid': sid}).scalars())
        messages = conn.execute(text('SELECT content,metadata FROM chat_message WHERE session_id=:sid'),
                                {'sid': sid}).mappings()
        for message in messages:
            files.extend(file_references(message['content'], message['metadata']))
        files.extend(conn.execute(text(
            "SELECT JSON_UNQUOTE(JSON_EXTRACT(e.result_ref,'$.url')) FROM graph_effect e "
            "JOIN agent_run r ON r.thread_id=e.thread_id WHERE r.agent_id=:aid "
            "AND r.conversation_id=:sid AND e.effect_key='v1:report_file:main:0'"
        ), {'aid': aid, 'sid': sid}).scalars())
        conn.execute(text("UPDATE chat_session SET status='deleted' WHERE id=:sid"), {'sid': sid})
        conn.execute(text(
            "UPDATE agent_session_runtime SET lifecycle='DELETED',version=version+1 "
            'WHERE agent_id=:aid AND conversation_id=:sid'
        ), {'aid': aid, 'sid': sid})
        conn.execute(text(
            'INSERT INTO agent_cleanup_job(id,agent_id,conversation_id,target_ref) '
            'VALUES (:id,:aid,:sid,:target)'
        ), {'id': str(uuid.uuid4()), 'aid': aid, 'sid': sid,
            'target': json.dumps({'threadIds': threads, 'files': [f for f in files if f]})})


@router.delete('/api/sessions/{sid}')
def delete_session(sid: str, request: Request):
    with request.app.state.engine.begin() as conn:
        session = owned_session(conn, sid, request)
        lock_agent(conn, session['agent_id'])
        owned_session(conn, sid, request, lock=True)
        delete_sessions(conn, session['agent_id'], [sid])
    return response(message='会话已删除')


@router.delete('/api/agent/{aid}/sessions')
def clear_sessions(aid: int, request: Request):
    with request.app.state.engine.begin() as conn:
        lock_agent(conn, aid)
        authorize_agent(conn, aid, request)
        sessions = list(conn.execute(text(
            "SELECT id FROM chat_session WHERE agent_id=:aid AND status<>'deleted' "
            'ORDER BY id FOR UPDATE'
        ), {'aid': aid}).scalars())
        delete_sessions(conn, aid, sessions)
    return response(message='会话已清空')


@router.delete('/api/agent/{aid}')
def delete_agent(aid: int, request: Request):
    with request.app.state.engine.begin() as conn:
        lock_agent(conn, aid)
        authorize_agent(conn, aid, request)
        sessions = list(conn.execute(text(
            "SELECT id FROM chat_session WHERE agent_id=:aid AND status<>'deleted' "
            'ORDER BY id FOR UPDATE'
        ), {'aid': aid}).scalars())
        active = conn.execute(text(
            "SELECT thread_id FROM agent_run WHERE agent_id=:aid "
            "AND status NOT IN ('COMPLETED','FAILED','CANCELLED') LIMIT 1 FOR UPDATE"
        ), {'aid': aid}).first()
        if active:
            raise HTTPException(409, 'Agent 存在未结束运行，不能删除')
        delete_sessions(conn, aid, sessions)
        files = list(conn.execute(text(
            'SELECT file_path FROM agent_knowledge WHERE agent_id=:aid AND file_path IS NOT NULL '
            'UNION SELECT avatar FROM agent WHERE id=:aid AND avatar IS NOT NULL'
        ), {'aid': aid}).scalars())
        conn.execute(text("UPDATE agent_lifecycle SET lifecycle='DELETED',version=version+1 "
                          'WHERE agent_id=:aid'), {'aid': aid})
        conn.execute(text(
            'INSERT INTO agent_cleanup_job(id,agent_id,target_ref) VALUES (:id,:aid,:target)'
        ), {'id': str(uuid.uuid4()), 'aid': aid,
            'target': json.dumps({'deleteAgent': True, 'files': files})})
    return response(message='Agent 已删除')
