"""Retryable cleanup of tombstoned resources; no identifier is reopened on failure."""

import json

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.local_files import cleanup_unreferenced_file


def pending_jobs(engine):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT * FROM agent_cleanup_job WHERE status<>'COMPLETED' ORDER BY created_at,id"
        )).mappings().all()


def failed_job(engine, identifier, error):
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE agent_cleanup_job SET status='FAILED',attempts=attempts+1,error=:error WHERE id=:id"
        ), {'id': identifier, 'error': error})


def cleanup_storage(app, job, target):
    engine = app.state.engine
    with app.state.knowledge.lock:
        if target.get('deleteAgent'):
            app.state.knowledge.delete_agent_vectors(job['agent_id'])
        with engine.begin() as conn:
            aid, sid = job['agent_id'], job['conversation_id']
            if target.get('deleteAgent'):
                lifecycle = conn.execute(text(
                    'SELECT lifecycle FROM agent_lifecycle WHERE agent_id=:aid FOR UPDATE'
                ), {'aid': aid}).scalar_one()
                if lifecycle != 'DELETED':
                    raise ValueError('Cleanup requires an Agent tombstone')
                # Cascade only this Agent's business resources; keep its tombstone.
                conn.execute(text('DELETE FROM user_prompt_config WHERE agent_id=:aid'), {'aid': aid})
                conn.execute(text('DELETE FROM agent WHERE id=:aid'), {'aid': aid})
                with app.state.knowledge.index() as index:
                    index.execute('DELETE FROM chunks WHERE agent_id=?', (aid,))
            else:
                status = conn.execute(text(
                    'SELECT status FROM chat_session WHERE id=:sid FOR UPDATE'
                ), {'sid': sid}).scalar()
                if status not in {None, 'deleted'}:
                    raise ValueError('Cleanup requires a session tombstone')
                for tid in target.get('threadIds', []):
                    for table in ('graph_effect', 'agent_run_result', 'agent_conversation_turn', 'agent_run'):
                        conn.execute(text(f'DELETE FROM {table} WHERE thread_id=:tid'), {'tid': tid})
                conn.execute(text('DELETE FROM chat_message WHERE session_id=:sid'), {'sid': sid})
        for path in target.get('files', []):
            relative = path.removeprefix('/api/upload/files/')
            if not relative.startswith(('knowledge/', 'avatars/', 'reports/')):
                continue
            cleanup_unreferenced_file(engine, app.state.settings, relative)
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE agent_cleanup_job SET status='COMPLETED',error=NULL,attempts=attempts+1 "
                'WHERE id=:id'
            ), {'id': job['id']})


async def cleanup_jobs(app):
    jobs = await run_in_threadpool(pending_jobs, app.state.engine)
    for job in jobs:
        target = json.loads(job['target_ref']) if isinstance(job['target_ref'], str) else job['target_ref']
        try:
            # Checkpoint deletion precedes the retryable MySQL/file/vector work.
            for tid in target.get('threadIds', []):
                await app.state.saver.adelete_thread(tid)
            await run_in_threadpool(cleanup_storage, app, job, target)
        except Exception as exc:  # noqa: BLE001 -- persist errors for retry
            await run_in_threadpool(failed_job, app.state.engine, job['id'], type(exc).__name__)
