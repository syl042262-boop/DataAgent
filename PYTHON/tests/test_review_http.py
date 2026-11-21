"""Versioned review behavior through the durable HTTP/SSE boundary."""

# ruff: noqa: F401, F811
import json
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_postgresql_http import _create_pg_model_server, business_pg_db
from test_stream_query_http import (
    _parse_sse,
    _setup_agent_and_model,
    business_mysql_db,
    controlled_chat_server,
)

from app.main import create_app


def test_configuration_change_does_not_release_uncertain_timed_out_sql(
    business_mysql_db, controlled_chat_server,
):
    url, provider = controlled_chat_server
    provider['mode'] = 'slow_sql'
    with TestClient(create_app()) as client, ThreadPoolExecutor() as pool:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        dsid = client.get('/api/datasource').json()[0]['id']
        source = business_mysql_db
        uri = f"mysql://{source['host']}:{source['port']}/{source['databaseName']}?socketTimeout=1000"
        assert client.put(f'/api/datasource/{dsid}', json={'connectionUrl': uri}).status_code == 200
        future = pool.submit(client.get, '/api/stream/search', params={
            'agentId': aid, 'conversationId': sid, 'query': '销售统计', 'nl2sqlOnly': True,
        })
        deadline = time.monotonic() + 8
        pid = None
        while time.monotonic() < deadline:
            with source['engine'].connect() as conn:
                pid = conn.execute(text(
                    'SELECT ID FROM information_schema.PROCESSLIST '
                    "WHERE DB=:db AND INFO LIKE 'SELECT amount, SLEEP(12)%'"
                ), {'db': source['databaseName']}).scalar()
            if pid:
                break
            time.sleep(0.02)
        assert pid
        try:
            client.put(f'/api/agent/{aid}', json={'prompt': 'changed while SQL is running'})
            events = _parse_sse(future.result(timeout=5).text)
            assert events[-1][0] == 'error'
            active = client.get(f'/api/sessions/{sid}/active-run').json()['data']
            assert active['status'] == 'RECOVERY_REQUIRED'
            assert client.delete(f'/api/sessions/{sid}').status_code == 409
        finally:
            with source['engine'].connect() as conn:
                exists = conn.execute(text('SELECT COUNT(*) FROM information_schema.PROCESSLIST '
                                           'WHERE ID=:pid'), {'pid': pid}).scalar_one()
                if exists:
                    conn.execute(text(f'KILL CONNECTION {int(pid)}'))


def test_crashed_worker_requires_evidence_and_version_before_cli_resolution(
    business_mysql_db, controlled_chat_server,
):
    url, provider = controlled_chat_server
    provider['mode'] = 'slow_sql'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen([
        sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=20) as client:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    if client.get('/echo/ok').status_code == 200:
                        break
                except httpx.TransportError:
                    time.sleep(0.1)
            aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
            with client.stream('GET', '/api/stream/search', params={
                'agentId': aid, 'conversationId': sid, 'query': '销售统计', 'nl2sqlOnly': True,
            }) as response:
                lines = response.iter_lines()
                for line in lines:
                    if '"nodeName": "SqlGenerateNode"' in line:
                        break
                deadline = time.monotonic() + 5
                pid = None
                while time.monotonic() < deadline:
                    with business_mysql_db['engine'].connect() as conn:
                        pid = conn.execute(text(
                            'SELECT ID FROM information_schema.PROCESSLIST '
                            "WHERE DB=:db AND INFO LIKE 'SELECT amount, SLEEP(12)%'"
                        ), {'db': business_mysql_db['databaseName']}).scalar()
                    if pid:
                        break
                    time.sleep(0.05)
                assert pid
                process.kill()
                process.wait(timeout=5)
            # A dead worker alone is insufficient while its database connection remains.
            with business_mysql_db['engine'].connect() as conn:
                exists = conn.execute(text('SELECT COUNT(*) FROM information_schema.PROCESSLIST '
                                           'WHERE ID=:pid'), {'pid': pid}).scalar_one()
                if exists:
                    conn.execute(text(f'KILL CONNECTION {int(pid)}'))
        with TestClient(create_app()) as client:
            active = client.get(f'/api/sessions/{sid}/active-run').json()['data']
            assert active['status'] == 'RECOVERY_REQUIRED'
            tid = active['threadId']
            version = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']['version']
            command = [sys.executable, '-m', 'app.operations', 'resolve-failed', '--thread-id', tid,
                       '--operator', 'test-operator', '--reason', 'verified-stopped',
                       '--expected-version']
            stale = subprocess.run([*command, str(version - 1)], capture_output=True, check=False)
            assert stale.returncode != 0
            resolved = subprocess.run([*command, str(version)], capture_output=True, check=False)
            assert resolved.returncode == 0, resolved.stderr
            repeated = subprocess.run([*command, str(version)], capture_output=True, check=False)
            assert repeated.returncode == 0, repeated.stderr
            result = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']
            assert result['status'] == 'FAILED'
            assert client.get(f'/api/sessions/{sid}/active-run').json()['data'] is None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_disconnected_sse_query_is_stopped_and_session_is_released(
    business_mysql_db, controlled_chat_server,
):
    url, provider = controlled_chat_server
    provider['mode'] = 'slow_sql'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), host='127.0.0.1', port=port,
                                           log_level='error'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        assert server.started
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=20) as client:
            aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
            with client.stream('GET', '/api/stream/search', params={
                'agentId': aid, 'conversationId': sid, 'query': '销售统计', 'nl2sqlOnly': True,
            }) as response:
                lines = response.iter_lines()
                for line in lines:
                    if '"nodeName": "SqlGenerateNode"' in line:
                        break
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    with business_mysql_db['engine'].connect() as conn:
                        running = conn.execute(text(
                            'SELECT COUNT(*) FROM information_schema.PROCESSLIST '
                            "WHERE DB=:db AND INFO LIKE 'SELECT amount, SLEEP(12)%'"
                        ), {'db': business_mysql_db['databaseName']}).scalar_one()
                    if running:
                        break
                    time.sleep(0.05)
                assert running
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                active = client.get(f'/api/sessions/{sid}/active-run').json()['data']
                if active is None:
                    break
                time.sleep(0.05)
            assert active is None, 'Disconnected run still occupies the session'
    finally:
        server.should_exit = True
        thread.join(timeout=20)


def test_session_deletion_is_atomic_and_late_messages_cannot_recreate_it(
    business_mysql_db, controlled_chat_server,
):
    url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        other = client.post(f'/api/agent/{aid}/sessions', json={}).json()['id']
        events = _parse_sse(client.get('/api/stream/search', params={
            'agentId': aid, 'conversationId': sid, 'query': '销售统计', 'humanFeedback': True,
        }).text)
        assert client.delete(f'/api/sessions/{sid}').status_code == 409
        assert client.delete(f'/api/agent/{aid}/sessions').status_code == 409
        assert client.delete(f'/api/agent/{aid}').status_code == 409
        assert client.get(f'/api/sessions/{other}/messages').status_code == 200
        assert client.post('/api/stream/stop', params={
            'agentId': aid, 'conversationId': sid,
        }).status_code == 204
        assert client.delete(f'/api/sessions/{sid}').status_code == 200
        assert client.post(f'/api/sessions/{sid}/messages', json={
            'role': 'assistant', 'content': 'late',
        }).status_code == 404
        assert client.get(f'/api/sessions/{sid}/runs').status_code == 404
        assert events[-1][0] == 'complete'
        assert client.delete(f'/api/agent/{aid}').status_code == 200
        assert client.get(f'/api/agent/{aid}').status_code == 404
        assert all(a['id'] != aid for a in client.get('/api/agent/list').json())
    with TestClient(create_app()) as client:
        assert client.get(f'/api/agent/{aid}').status_code == 404
        assert client.get(f'/api/sessions/{sid}/messages').status_code == 404


def test_running_mysql_query_is_stopped_before_session_is_released(
    business_mysql_db, controlled_chat_server,
):
    url, provider = controlled_chat_server
    provider['mode'] = 'slow_sql'
    with TestClient(create_app()) as client, ThreadPoolExecutor() as pool:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        future = pool.submit(client.get, '/api/stream/search', params={
            'agentId': aid, 'conversationId': sid, 'query': '销售统计', 'nl2sqlOnly': True,
        })
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            with business_mysql_db['engine'].connect() as conn:
                running = conn.execute(text(
                    'SELECT COUNT(*) FROM information_schema.PROCESSLIST '
                    "WHERE DB=:db AND INFO LIKE 'SELECT amount, SLEEP(12)%'"
                ), {'db': business_mysql_db['databaseName']}).scalar_one()
            if running:
                break
            time.sleep(0.05)
        assert running, 'Real MySQL query did not start'
        assert client.post('/api/stream/stop', params={
            'agentId': aid, 'conversationId': sid,
        }).status_code == 204
        response = future.result(timeout=4)
        events = _parse_sse(response.text)
        assert events[-1][0] == 'error'
        tid = events[-1][1]['threadId']
        detail = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']
        assert detail['status'] == 'CANCELLED'


def test_cosmetic_edit_and_credential_rotation_keep_review_valid_with_current_key(
    business_mysql_db, controlled_chat_server,
):
    url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, key = _setup_agent_and_model(client, url, business_mysql_db,
                                              api_key_enabled=True)
        client.headers['X-API-Key'] = key
        params = {'agentId': aid, 'conversationId': sid, 'query': '销售统计',
                  'humanFeedback': True}
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        card = next(d for _, d in events if d.get('eventType') == 'HUMAN_FEEDBACK_REQUIRED')
        client.put(f'/api/agent/{aid}', json={'name': '新名字', 'avatar': '/avatar.png'})
        params.update(threadId=card['threadId'], feedbackRevision=card['planRevision'],
                      rejectedPlan=True, humanFeedbackContent='保持原计划')
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        card = next(d for _, d in events if d.get('eventType') == 'HUMAN_FEEDBACK_REQUIRED')
        rotated = client.post(f'/api/agent/{aid}/api-key/reset').json()['data']['apiKey']
        assert client.get('/api/stream/search', params=params).status_code == 401
        client.headers['X-API-Key'] = rotated
        params.update(feedbackRevision=card['planRevision'], rejectedPlan=False)
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        assert events[-1][0] == 'complete'


def test_stop_waiting_run_releases_session_and_refuses_feedback(
    business_mysql_db, controlled_chat_server,
):
    url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        params = {'agentId': aid, 'conversationId': sid, 'query': '销售统计',
                  'humanFeedback': True}
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        card = next(d for _, d in events if d.get('eventType') == 'HUMAN_FEEDBACK_REQUIRED')
        assert client.post('/api/stream/stop', params={'conversationId': sid}).status_code == 400
        stopped = client.post('/api/stream/stop', params={
            'agentId': aid, 'conversationId': sid, 'threadId': card['threadId'],
        })
        assert stopped.status_code == 204
        detail = client.get(f'/api/sessions/{sid}/runs/{card["threadId"]}').json()['data']
        assert detail['status'] == 'CANCELLED'
        params.update(threadId=card['threadId'], feedbackRevision=card['planRevision'])
        assert _parse_sse(client.get('/api/stream/search', params=params).text)[-1][0] == 'error'


def test_changed_configuration_invalidates_waiting_plan(business_mysql_db, controlled_chat_server):
    url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        params = {'agentId': aid, 'conversationId': sid, 'query': '销售统计',
                  'humanFeedback': True}
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        card = next(d for _, d in events if d.get('eventType') == 'HUMAN_FEEDBACK_REQUIRED')
        client.put(f'/api/agent/{aid}', json={'prompt': '新的业务规则'})
        params.update(threadId=card['threadId'], feedbackRevision=card['planRevision'])
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        assert events[-1][0] == 'error'
        assert 'CONFIG_CHANGED' in events[-1][1]['text']
        detail = client.get(f'/api/sessions/{sid}/runs/{card["threadId"]}').json()['data']
        assert detail['status'] == 'FAILED'
        assert detail['result']['reason'].startswith('CONFIG_CHANGED')


def test_rejected_review_replans_without_recalling_and_rejects_stale_feedback(
    business_mysql_db, controlled_chat_server,
):
    url, provider = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        params = {'agentId': aid, 'conversationId': sid, 'query': '销售统计',
                  'humanFeedback': True}
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        card = next(d for _, d in events if d.get('eventType') == 'HUMAN_FEEDBACK_REQUIRED')
        params.update(threadId=card['threadId'], feedbackRevision=card['planRevision'],
                      rejectedPlan=True, humanFeedbackContent='只看 East')
        events = _parse_sse(client.get('/api/stream/search', params=params).text)
        replacement = next(d for _, d in events
                           if d.get('eventType') == 'HUMAN_FEEDBACK_REQUIRED')
        assert replacement['planRevision'] == card['planRevision'] + 1
        assert replacement['threadId'] == card['threadId']
        assert sum(r['messages'][0]['content'].startswith('[SchemaRecallNode]')
                   for r in provider['requests']) == 1
        planners = [r for r in provider['requests']
                    if r['messages'][0]['content'].startswith('[PlannerNode]')]
        assert len(planners) == 2
        assert '只看 East' in str(planners[-1])
        stale = _parse_sse(client.get('/api/stream/search', params=params).text)
        assert stale[-1][0] == 'error'
        assert '版本已过期' in stale[-1][1]['text']
    with TestClient(create_app()) as client:
        active = client.get(f'/api/sessions/{sid}/active-run').json()['data']
        assert active['threadId'] == card['threadId']
        assert active['planRevision'] == replacement['planRevision']
        assert active['recoverable'] is True
        params.update(feedbackRevision=replacement['planRevision'], rejectedPlan=False)
        accepted = _parse_sse(client.get('/api/stream/search', params=params).text)
        assert accepted[-1][0] == 'complete'
        detail = client.get(f'/api/sessions/{sid}/runs/{card["threadId"]}').json()['data']
        assert detail['status'] == 'COMPLETED'

def test_postgresql_native_stop_finishes_before_occupancy_release(business_pg_db):
    server, worker, url = _create_pg_model_server(
        [], 'SELECT "amount", pg_sleep(12) AS waited FROM "OrderItems" LIMIT 1'
    )
    try:
        with TestClient(create_app()) as client, ThreadPoolExecutor() as pool:
            client.post('/api/model-config/add', json={
                'provider': 'custom', 'baseUrl': url, 'modelType': 'CHAT', 'modelName': 'pg-stop',
            })
            mid = client.get('/api/model-config/list').json()['data'][0]['id']
            client.post(f'/api/model-config/activate/{mid}')
            aid = client.post('/api/agent', json={'name': 'PG stop'}).json()['id']
            source = {key: value for key, value in business_pg_db.items() if key not in {'schema', 'engine'}}
            dsid = client.post('/api/datasource', json=source).json()['id']
            path = f'/api/agent/{aid}/datasources'
            client.post(path + f'/{dsid}')
            client.post(path + '/tables', json={'datasourceId': dsid, 'tables': ['OrderItems']})
            client.post(path + '/init')
            sid = client.post(f'/api/agent/{aid}/sessions', json={}).json()['id']
            future = pool.submit(client.get, '/api/stream/search', params={
                'agentId': aid, 'conversationId': sid, 'query': '查询金额', 'nl2sqlOnly': True,
            })
            pid = None
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                with business_pg_db['engine'].connect() as conn:
                    pid = conn.execute(text(
                        "SELECT pid FROM pg_stat_activity WHERE state='active' "
                        "AND query LIKE 'SELECT \"amount\", pg_sleep(12)%'"
                    )).scalar()
                if pid:
                    break
                time.sleep(0.05)
            assert pid, 'Real PostgreSQL sleep query did not start'
            assert client.delete(f'/api/sessions/{sid}').status_code == 409
            assert client.post('/api/stream/stop', params={
                'agentId': aid, 'conversationId': sid,
            }).status_code == 204
            events = _parse_sse(future.result(timeout=5).text)
            assert events[-1][0] == 'error'
            tid = events[-1][1]['threadId']
            detail = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']
            assert detail['status'] == 'CANCELLED'
            assert client.get(f'/api/sessions/{sid}/active-run').json()['data'] is None
            with business_pg_db['engine'].connect() as conn:
                assert not conn.execute(text('SELECT 1 FROM pg_stat_activity WHERE pid=:pid'),
                                        {'pid': pid}).first()
            assert client.delete(f'/api/sessions/{sid}').status_code == 200
    finally:
        server.shutdown()
        worker.join()
        server.server_close()

@pytest.mark.parametrize('mode,outcome', [('normal', 'SUCCESS'), ('chat', 'EARLY_END'), ('forecast', 'UNSUPPORTED')])
def test_startup_finishes_a_committed_snapshot_without_replaying_sql(
    business_mysql_db, controlled_chat_server, mode, outcome,
):
    url, provider = controlled_chat_server
    provider['mode'] = mode
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        trace = _parse_sse(client.get('/api/stream/search', params={
            'agentId': aid, 'conversationId': sid, 'query': '销售统计', 'nl2sqlOnly': True,
        }).text)
        assert trace[-1][0] == 'complete'
        tid = trace[-1][1]['threadId']
        expected = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']['result']
        assert expected['outcome'] == outcome
        # Fault-injection setup: restore a nonterminal lifecycle around the
        # already committed result, with positive evidence of a stopped worker.
        probe = subprocess.run([sys.executable, '-c',
            ('import os,json,socket,psutil; print(json.dumps(dict(pid=os.getpid(),'
            'started=psutil.Process().create_time(),host=socket.gethostname())))')],
            check=True, capture_output=True, text=True)
        with client.app.state.engine.begin() as conn:
            conn.execute(text("UPDATE agent_run SET status='RUNNING',result_version=NULL,"
                              "finished_at=NULL,version=version+1,owner='stopped-worker',"
                              "request=JSON_SET(request,'$._worker',JSON_EXTRACT(:worker,'$')) "
                              "WHERE thread_id=:tid"),
                         {'worker': probe.stdout.strip(), 'tid': tid})
            conn.execute(text('UPDATE agent_session_runtime SET active_thread_id=:tid '
                              'WHERE agent_id=:aid AND conversation_id=:sid'),
                         {'tid': tid, 'aid': aid, 'sid': sid})
            conn.execute(text("UPDATE agent_conversation_turn SET memory_status='STAGED' WHERE thread_id=:tid"),
                         {'tid': tid})
    calls = provider['chat_calls']
    with TestClient(create_app()) as client:
        actual = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']
        assert actual['status'] == 'COMPLETED'
        assert actual['result'] == expected
        assert client.get(f'/api/sessions/{sid}/active-run').json()['data'] is None
        assert provider['chat_calls'] == calls

def test_history_only_file_references_survive_until_the_last_session_is_deleted(
    business_mysql_db, controlled_chat_server,
):
    url, provider = controlled_chat_server
    provider['mode'] = 'stream_report'
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        trace = _parse_sse(client.get('/api/stream/search', params={
            'agentId': aid, 'conversationId': sid, 'query': '销售统计和报告',
        }).text)
        assert trace[-1][0] == 'complete'
        tid = trace[-1][1]['threadId']
        detail = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']
        report_url = detail['result']['artifacts']['report']['url']
        raw = client.get(report_url).content
        other = client.post('/api/agent', json={'name': 'History references'}).json()['id']
        metadata_session = client.post(f'/api/agent/{other}/sessions', json={}).json()['id']
        content_session = client.post(f'/api/agent/{other}/sessions', json={}).json()['id']
        client.post(f'/api/sessions/{metadata_session}/messages', json={
            'role': 'assistant', 'content': 'Historical report',
            'metadata': {'artifacts': [{'fileUrl': report_url}]},
        })
        client.post(f'/api/sessions/{content_session}/messages', json={
            'role': 'assistant', 'content': f'<a href="{report_url}">Historical report</a>',
        })
        assert client.delete(f'/api/agent/{aid}').status_code == 200
    with TestClient(create_app()) as client:
        assert client.get(report_url).content == raw
        assert client.delete(f'/api/sessions/{metadata_session}').status_code == 200
    with TestClient(create_app()) as client:
        assert client.get(report_url).content == raw
        assert client.delete(f'/api/sessions/{content_session}').status_code == 200
    with TestClient(create_app()) as client:
        assert client.get(report_url).status_code == 404
        fresh = client.post(f'/api/agent/{other}/sessions', json={}).json()['id']
        assert client.post(f'/api/sessions/{fresh}/messages', json={
            'role': 'assistant', 'content': 'late file reference', 'metadata': {'url': report_url},
        }).status_code == 400
        assert client.put(f'/api/agent/{other}', json={'avatar': report_url}).status_code == 400
