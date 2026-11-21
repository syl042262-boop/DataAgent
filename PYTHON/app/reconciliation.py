"""Conservative startup reconciliation: never replay uncertain external operations."""

import json
import socket

import psutil
from sqlalchemy import text

from app.query_graph import build_query_graph
from app.run_coordination import RunCoordinator


async def reconcile_runs(app):
    engine = app.state.engine
    graph = build_query_graph(
        engine=engine, models=app.state.models,
        coordinator=RunCoordinator(engine, app.state.redis),
        saver=app.state.saver, model_timeout=app.state.settings.model_timeout,
        knowledge=app.state.knowledge,
    )
    with engine.connect() as conn:
        runs = conn.execute(text(
            "SELECT * FROM agent_run WHERE status NOT IN ('COMPLETED','FAILED','CANCELLED')"
        )).mappings().all()
    for run in runs:
        snapshot = await graph.aget_state({'configurable': {'thread_id': run['thread_id']}})
        values = snapshot.values or {}
        interrupted = any(task.interrupts for task in snapshot.tasks)
        plan = json.loads(run['plan']) if isinstance(run['plan'], str) else run['plan']
        checkpoint_id = snapshot.config.get('configurable', {}).get('checkpoint_id')
        original = json.loads(run['request']) if isinstance(run['request'], str) else run['request']
        worker = original.get('_worker') or {}
        worker_stopped = False
        if worker.get('host') == socket.gethostname() and worker.get('pid') and worker.get('started'):
            try:
                worker_stopped = psutil.Process(worker['pid']).create_time() != worker['started']
            except psutil.NoSuchProcess:
                worker_stopped = True
            except psutil.AccessDenied:
                pass
        with engine.begin() as conn:
            uncertain = conn.execute(text(
                "SELECT COUNT(*) FROM graph_effect WHERE thread_id=:tid AND status='IN_FLIGHT'"
            ), {'tid': run['thread_id']}).scalar_one()
            result = conn.execute(text(
                'SELECT * FROM agent_run_result WHERE thread_id=:tid'
            ), {'tid': run['thread_id']}).mappings().first()
            terminal = {'SUCCESS': 'COMPLETED', 'UNSUPPORTED': 'COMPLETED', 'EARLY_END': 'COMPLETED',
                        'FAILED': 'FAILED', 'CANCELLED': 'CANCELLED'}
            if (worker_stopped and not uncertain and result
                    and result['outcome'] in terminal and result['result_version'] > 0
                    and (run['status'] != 'CANCELLING' or result['outcome'] == 'CANCELLED')):
                # A committed snapshot is the result authority. Repair lifecycle
                # metadata only after stopped-worker proof; never replay the graph.
                updated = conn.execute(text(
                    'UPDATE agent_run SET status=:status,result_version=:result_version,'
                    'finished_at=:finished,error=:error,version=version+1 '
                    'WHERE thread_id=:tid AND version=:version AND status=:previous'
                ), {'status': terminal[result['outcome']], 'result_version': result['result_version'],
                    'finished': result['created_at'], 'error': result['reason'],
                    'tid': run['thread_id'], 'version': run['version'], 'previous': run['status']})
                if updated.rowcount:
                    conn.execute(text(
                        'UPDATE agent_conversation_turn SET memory_status=:memory WHERE thread_id=:tid'
                    ), {'memory': 'COMMITTED' if result['outcome'] == 'SUCCESS' else 'DISCARDED',
                        'tid': run['thread_id']})
                    conn.execute(text(
                        'UPDATE agent_session_runtime SET active_thread_id=NULL,version=version+1 '
                        'WHERE agent_id=:aid AND conversation_id=:sid AND active_thread_id=:tid'
                    ), {'aid': run['agent_id'], 'sid': run['conversation_id'], 'tid': run['thread_id']})
                continue
            consistent = (
                interrupted and not uncertain and plan is not None
                and values.get('plan') == plan
                and values.get('planRevision') == run['plan_revision']
                and checkpoint_id == run['checkpoint_id']
                and run['status'] in {'WAITING_FEEDBACK', 'RUNNING', 'RESUMING'}
                and (run['status'] == 'WAITING_FEEDBACK' or worker_stopped)
            )
            status = 'WAITING_FEEDBACK' if consistent else 'RECOVERY_REQUIRED'
            conn.execute(text(
                'UPDATE agent_run SET status=:status,error=:error,version=version+1 '
                'WHERE thread_id=:tid AND version=:version AND status=:previous'
            ), {'status': status, 'error': None if consistent else
                '服务中断：缺少一致的审核 checkpoint 或执行停止证据，禁止自动重发',
                'tid': run['thread_id'], 'version': run['version'], 'previous': run['status']})
