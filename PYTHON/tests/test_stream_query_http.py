"""HTTP/SSE tests for durable MySQL query, Redis/MySQL coordination, and restart recovery."""

import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from workflow_provider import workflow_reply

from app.config import Settings
from app.main import create_app


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        if not block.strip():
            continue
        event_name = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line.partition(":")[2].strip()
            elif line.startswith("data:"):
                data_lines.append(line.partition(":")[2].lstrip())
        if data_lines:
            events.append((event_name, json.loads("\n".join(data_lines))))
    return events


@pytest.fixture
def business_mysql_db():
    configured = os.environ["DATAAGENT_TEST_DATABASE_URL"]
    url = make_url(configured)
    db_name = "dataagent_biz_" + uuid.uuid4().hex
    engine = create_engine(url.set(database=None))
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        )
        conn.exec_driver_sql(
            f"CREATE TABLE `{db_name}`.sales ("
            "id INT AUTO_INCREMENT PRIMARY KEY, "
            "region VARCHAR(50) NOT NULL, "
            "amount DECIMAL(12,2) NOT NULL, "
            "sale_date DATE NOT NULL)"
        )
        conn.exec_driver_sql(
            f"INSERT INTO `{db_name}`.sales (region, amount, sale_date) VALUES "
            "('East', 120.50, '2026-11-01'), "
            "('East', 79.50, '2026-11-02'), "
            "('West', 50.00, '2026-11-03')"
        )
    try:
        yield {
            "host": url.host or "127.0.0.1",
            "port": url.port or 3306,
            "databaseName": db_name,
            "username": url.username or "root",
            "password": url.password or "",
            "engine": engine,
        }
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"DROP DATABASE `{db_name}`")
        engine.dispose()


@pytest.fixture
def controlled_chat_server():
    state = {"mode": "normal", "delay_answer": 0.0, "chat_calls": 0, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            state["requests"].append(payload)
            state["chat_calls"] += 1
            messages = payload.get("messages", [])
            system_text = messages[0]["content"] if messages else ""

            if state["mode"] == "provider_error":
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b'{"error":"upstream failed"}')
                return
            if state['mode'] == 'report_error' and payload.get('stream'):
                self.send_response(500)
                self.end_headers()
                return

            structured_reply = workflow_reply(messages)
            if system_text.startswith('[PlannerNode]') and state['mode'] == 'repair_plan':
                calls = sum(r['messages'][0]['content'].startswith('[PlannerNode]')
                            for r in state['requests'])
                if calls == 1:
                    plan = json.loads(structured_reply)
                    for step in plan['execution_plan']:
                        step['tool'] = step.pop('tool_to_use')
                    structured_reply = json.dumps(plan)
            if system_text.startswith('[SchemaRecallNode]') and state['mode'] == 'empty_schema':
                structured_reply = json.dumps({'tableNames': []})
            if system_text.startswith('[QueryEnhanceNode]') and state['mode'] == 'empty_enhance':
                structured_reply = json.dumps({'canonicalQuery': '', 'expandedQueries': []})
            if system_text.startswith('[TableRelationNode]') and state['mode'] == 'invalid_relation':
                structured_reply = json.dumps({'tableNames': ['not_authorized']})
            if system_text.startswith('[PlannerNode]') and state['mode'] == 'many_steps':
                plan = json.loads(structured_reply)
                step = plan['execution_plan'][0]
                plan['execution_plan'] = [{**step, 'step': n} for n in range(1, 12)] + [
                    {**plan['execution_plan'][-1], 'step': 12}]
                structured_reply = json.dumps(plan)
            if system_text.startswith('[IntentRecognitionNode]') and state['mode'] == 'chat':
                structured_reply = json.dumps({'classification': 'chat', 'response': '你好'})
            if system_text.startswith('[FeasibilityAssessmentNode]') and state['mode'] == 'forecast':
                structured_reply = json.dumps({'feasible': False,
                    'response': '无法训练预测模型；可以查询历史销售趋势。'})
            if system_text.startswith('[PlannerNode]') and state['mode'] == 'unknown_tool':
                structured_reply = json.dumps({'execution_plan': [
                    {'step': 1, 'tool_to_use': 'PYTHON_GENERATE_NODE', 'tool_parameters': {}}]})
            if system_text.startswith('[SemanticConsistencyNode]') and state['mode'] == 'inconsistent':
                structured_reply = json.dumps({'consistent': False, 'reason': '缺少区域过滤'})
            if structured_reply is not None:
                content = structured_reply
            elif state['mode'] == 'empty_result' and '数据库 Schema' in system_text:
                content = 'SELECT region, amount FROM sales WHERE 1=0'
            elif state['mode'] == 'slow_sql' and '数据库 Schema' in system_text:
                content = 'SELECT amount, SLEEP(12) AS waited FROM sales LIMIT 1'
            elif state['mode'] == 'empty_result' and payload.get('stream'):
                content = '<p>查询没有数据，无法据此作出金额结论。</p>'
            elif "SQL" in system_text and "结果" not in system_text:
                if state["mode"] == "bad_sql" or (
                    state['mode'] == 'repair_sql' and
                    sum('数据库 Schema' in r['messages'][0]['content']
                        for r in state['requests']) == 1
                ):
                    content = "SELECT * FROM nonexistent_table_xyz"
                else:
                    content = (
                        "```sql\n"
                        "SELECT region, SUM(amount) AS total_amount "
                        "FROM sales GROUP BY region ORDER BY region\n"
                        "```"
                    )
            else:
                if state["delay_answer"] > 0:
                    time.sleep(state["delay_answer"])
                content = "East 总销售额为 200.00，West 为 50.00。"

            self.send_response(200)
            if state['mode'] == 'stream_report' and payload.get('stream'):
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                for fragment in ('<h1>销售额</h1>', '<p>East 200，West 50。</p>'):
                    chunk = {'choices': [{'delta': {'content': fragment}}]}
                    self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                    self.wfile.flush()
                self.wfile.write(b'data: [DONE]\n\n')
                return
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _setup_agent_and_model(
    client: TestClient,
    model_url: str,
    biz: dict,
    *,
    api_key_enabled: bool = False,
) -> tuple[int, str, str | None]:
    add_model = client.post(
        "/api/model-config/add",
        json={
            "provider": "openai",
            "baseUrl": model_url,
            "apiKey": "fixture-key",
            "modelName": "test-chat",
            "modelType": "CHAT",
        },
    )
    assert add_model.status_code == 200
    model_id = client.get("/api/model-config/list").json()["data"][0]["id"]
    assert client.post(f"/api/model-config/activate/{model_id}").json()["success"] is True

    agent = client.post("/api/agent", json={"name": "Query Agent", "status": "published"}).json()
    agent_id = agent["id"]

    api_key = None
    if api_key_enabled:
        generated = client.post(f"/api/agent/{agent_id}/api-key/generate").json()["data"]
        api_key = generated["apiKey"]
        client.put(f"/api/agent/{agent_id}/api-key/toggle", params={"enabled": "true"})

    ds = client.post(
        "/api/datasource",
        json={
            "name": "Biz MySQL",
            "type": "mysql",
            "host": biz["host"],
            "port": biz["port"],
            "databaseName": biz["databaseName"],
            "username": biz["username"],
            "password": biz["password"],
        },
    ).json()
    ds_id = ds["id"]
    assert client.post(f"/api/agent/{agent_id}/datasources/{ds_id}").json()["success"] is True
    assert (
        client.post(
            f"/api/agent/{agent_id}/datasources/tables",
            json={"datasourceId": ds_id, "tables": ["sales"]},
        ).json()["success"]
        is True
    )
    assert client.post(f"/api/agent/{agent_id}/datasources/init").json()["success"] is True

    session = client.post(f"/api/agent/{agent_id}/sessions", json={"title": "查询测试"}).json()
    return agent_id, session["id"], api_key


def test_real_mysql_query_sse_auth_and_cross_agent_isolation(
    business_mysql_db, controlled_chat_server
):
    model_url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        agent_id, session_id, api_key = _setup_agent_and_model(
            client, model_url, business_mysql_db, api_key_enabled=True
        )
        other_agent = client.post("/api/agent", json={"name": "Other"}).json()

        # 401 before SSE stream when key is missing or wrong
        unauth = client.get(
            "/api/stream/search",
            params={"agentId": str(agent_id), "conversationId": session_id, "query": "销售额"},
        )
        assert unauth.status_code == 401

        # Cross-agent session returns 404
        cross = client.get(
            "/api/stream/search",
            params={
                "agentId": str(other_agent["id"]),
                "conversationId": session_id,
                "query": "销售额",
            },
        )
        assert cross.status_code == 404

        # Valid X-API-Key streams SQL, RESULT_SET, FINAL_ANSWER, and single complete
        resp = client.get(
            "/api/stream/search",
            params={"agentId": str(agent_id), "conversationId": session_id, "query": "按地区统计销售额"},
            headers={"X-API-Key": api_key or ""},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events[-1][0] == "complete", resp.text
        assert sum(1 for name, _ in events if name in ("complete", "error")) == 1

        sql_events = [d for name, d in events if name == "message" and d.get("textType") == "SQL"]
        assert sql_events and "SELECT" in sql_events[0]["text"]

        rs_events = [
            d for name, d in events if name == "message" and d.get("textType") == "RESULT_SET"
        ]
        assert rs_events
        rs_payload = json.loads(rs_events[0]["text"])["resultSet"]
        assert rs_payload["column"] == ["region", "total_amount"]
        assert rs_payload["data"] == [
            {"region": "East", "total_amount": 200.0},
            {"region": "West", "total_amount": 50.0},
        ]

        final_events = [
            d for name, d in events if name == "message" and d.get("eventType") == "FINAL_ANSWER"
        ]
        assert final_events and "200.00" in final_events[0]["text"]
        thread_id = final_events[0]["threadId"]
        assert thread_id

        # Verify persisted run, result snapshot, committed turn, and released occupancy
        with client.app.state.engine.connect() as conn:
            run_row = conn.execute(
                text("SELECT status, result_version FROM agent_run WHERE thread_id=:tid"),
                {"tid": thread_id},
            ).mappings().one()
            assert run_row["status"] == "COMPLETED"
            assert run_row["result_version"] == 1

            res_row = conn.execute(
                text("SELECT outcome, final_answer FROM agent_run_result WHERE thread_id=:tid"),
                {"tid": thread_id},
            ).mappings().one()
            assert res_row["outcome"] == "SUCCESS"
            assert "200.00" in res_row["final_answer"]

            turn_status = conn.execute(
                text("SELECT memory_status FROM agent_conversation_turn WHERE thread_id=:tid"),
                {"tid": thread_id},
            ).scalar_one()
            assert turn_status == "COMMITTED"

            active_tid = conn.execute(
                text(
                    "SELECT active_thread_id FROM agent_session_runtime "
                    "WHERE agent_id=:aid AND conversation_id=:cid"
                ),
                {"aid": agent_id, "cid": session_id},
            ).scalar_one()
            assert active_tid is None


def test_redis_unavailable_and_lock_expiry_do_not_allow_concurrent_execution(
    business_mysql_db, controlled_chat_server
):
    model_url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        agent_id, session_id, _ = _setup_agent_and_model(
            client, model_url, business_mysql_db, api_key_enabled=False
        )
        # Simulate an occupied MySQL session even with no Redis key (e.g., lock expired)
        occupied_tid = str(uuid.uuid4())
        with client.app.state.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agent_session_runtime (agent_id, conversation_id, active_thread_id) "
                    "VALUES (:aid, :cid, :tid)"
                ),
                {"aid": agent_id, "cid": session_id, "tid": occupied_tid},
            )

        # Even though Redis has no lock, MySQL occupancy rejects a second execution
        busy_resp = client.get(
            "/api/stream/search",
            params={"agentId": str(agent_id), "conversationId": session_id, "query": "新问题"},
        )
        assert busy_resp.status_code == 200
        busy_events = _parse_sse(busy_resp.text)
        assert busy_events[-1][0] == "error"
        assert not any(name == "complete" for name, _ in busy_events)

    # Redis unavailable rejects new run and preserves existing MySQL occupancy
    unavailable_settings = Settings(redis_url="redis://127.0.0.1:1/0")
    with TestClient(create_app(unavailable_settings)) as client_no_redis:
        no_redis_resp = client_no_redis.get(
            "/api/stream/search",
            params={"agentId": str(agent_id), "conversationId": session_id, "query": "新问题"},
        )
        assert no_redis_resp.status_code == 200
        no_redis_events = _parse_sse(no_redis_resp.text)
        assert no_redis_events[-1][0] == "error"
        assert not any(name == "complete" for name, _ in no_redis_events)
        with client_no_redis.app.state.engine.connect() as conn:
            still_occupied = conn.execute(
                text(
                    "SELECT active_thread_id FROM agent_session_runtime "
                    "WHERE agent_id=:aid AND conversation_id=:cid"
                ),
                {"aid": agent_id, "cid": session_id},
            ).scalar_one()
            assert still_occupied == occupied_tid


def test_wrong_redis_token_cannot_release_and_different_sessions_run_in_parallel(
    business_mysql_db, controlled_chat_server
):
    from app.run_coordination import RedisLock

    lock_client = redis.Redis.from_url(Settings().redis_url, decode_responses=True)
    lock = RedisLock(lock_client)
    key = f"dataagent:test:{uuid.uuid4().hex}"
    token = lock.acquire(key, 10000)
    assert lock.renew(key, "wrong-token", 10000) is False
    assert lock.release(key, "wrong-token") is False
    assert lock.renew(key, token, 10000) is True
    assert lock.release(key, token) is True

    model_url, state = controlled_chat_server
    state["delay_answer"] = 0.25
    with TestClient(create_app()) as client:
        agent_id, session_1, _ = _setup_agent_and_model(client, model_url, business_mysql_db)
        session_2 = client.post(f"/api/agent/{agent_id}/sessions", json={"title": "并行2"}).json()[
            "id"
        ]

        results: dict[str, list[tuple[str, dict]]] = {}

        def run_query(cid: str):
            r = client.get(
                "/api/stream/search",
                params={"agentId": str(agent_id), "conversationId": cid, "query": "并行查询"},
            )
            results[cid] = _parse_sse(r.text)

        t1 = threading.Thread(target=run_query, args=(session_1,))
        t2 = threading.Thread(target=run_query, args=(session_2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results[session_1][-1][0] == "complete"
        assert results[session_2][-1][0] == "complete"


def test_restart_recovery_resumes_same_thread_without_reexecuting_committed_sql(
    business_mysql_db, controlled_chat_server
):
    model_url, provider_state = controlled_chat_server
    # App 1: run with humanFeedback=True -> interrupts at PlannerNode after SQL or before SQL;
    # here we verify interrupt + restart + resume with same threadId, and verify SQL effect is not re-executed.
    with TestClient(create_app()) as client1:
        agent_id, session_id, _ = _setup_agent_and_model(client1, model_url, business_mysql_db)
        paused = client1.get(
            "/api/stream/search",
            params={
                "agentId": str(agent_id),
                "conversationId": session_id,
                "query": "销售统计",
                "humanFeedback": "true",
            },
        )
        assert paused.status_code == 200
        paused_events = _parse_sse(paused.text)
        feedback_events = [
            d
            for name, d in paused_events
            if name == "message" and d.get("eventType") == "HUMAN_FEEDBACK_REQUIRED"
        ]
        assert feedback_events
        thread_id = feedback_events[0]["threadId"]
        assert paused_events[-1][0] == "complete"
        assert feedback_events[0]["plan"]["execution_plan"]

        with client1.app.state.engine.connect() as conn:
            status = conn.execute(
                text("SELECT status FROM agent_run WHERE thread_id=:tid"),
                {"tid": thread_id},
            ).scalar_one()
            assert status == "WAITING_FEEDBACK"

    # App 2 (simulated process restart): resume same threadId
    with TestClient(create_app()) as client2:
        resumed = client2.get(
            "/api/stream/search",
            params={
                "agentId": str(agent_id),
                "conversationId": session_id,
                "threadId": thread_id,
                "query": "销售统计",
                "humanFeedback": "true",
                "humanFeedbackContent": "Accept",
            },
        )
        assert resumed.status_code == 200
        resumed_events = _parse_sse(resumed.text)
        assert resumed_events[-1][0] == "complete"
        final_events = [
            d
            for name, d in resumed_events
            if name == "message" and d.get("eventType") == "FINAL_ANSWER"
        ]
        assert final_events and final_events[0]["threadId"] == thread_id

        with client2.app.state.engine.connect() as conn:
            effect_status = conn.execute(
                text(
                    "SELECT status FROM graph_effect WHERE thread_id=:tid "
                    "AND effect_key='v1:sql_execute:main:0'"
                ),
                {"tid": thread_id},
            ).scalar_one()
            assert effect_status == "COMMITTED"


    assert sum(r['messages'][0]['content'].startswith('[PlannerNode]')
               for r in provider_state['requests']) == 1

def test_committed_sql_effect_reentry_does_not_reexecute_mysql(
    business_mysql_db, controlled_chat_server
):
    model_url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        agent_id, session_id, _ = _setup_agent_and_model(client, model_url, business_mysql_db)
        paused = client.get(
            "/api/stream/search",
            params={
                "agentId": str(agent_id),
                "conversationId": session_id,
                "query": "销售统计",
                "humanFeedback": "true",
            },
        )
        feedback_events = [
            d
            for name, d in _parse_sse(paused.text)
            if name == "message" and d.get("eventType") == "HUMAN_FEEDBACK_REQUIRED"
        ]
        thread_id = feedback_events[0]["threadId"]

        # Pre-commit the SQL effect and drop the business table: resume must use committed result_ref
        with client.app.state.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO graph_effect (thread_id, effect_key, status, result_ref) "
                    "VALUES (:tid, 'v1:sql_execute:main:0', 'COMMITTED', :ref)"
                ),
                {
                    "tid": thread_id,
                    "ref": json.dumps(
                        {
                            "column": ["region", "total_amount"],
                            "data": [{"region": "East", "total_amount": 200.0}],
                        }
                    ),
                },
            )
        with business_mysql_db["engine"].begin() as biz_conn:
            biz_conn.exec_driver_sql(f"DROP TABLE `{business_mysql_db['databaseName']}`.sales")

        resumed = client.get(
            "/api/stream/search",
            params={
                "agentId": str(agent_id),
                "conversationId": session_id,
                "threadId": thread_id,
                "query": "销售统计",
                "humanFeedback": "true",
                "humanFeedbackContent": "Accept",
            },
        )
        events = _parse_sse(resumed.text)
        assert events[-1][0] == "complete", resumed.text
        rs_events = [
            d for name, d in events if name == "message" and d.get("textType") == "RESULT_SET"
        ]
        assert rs_events
        assert json.loads(rs_events[0]["text"])["resultSet"]["data"] == [
            {"region": "East", "total_amount": 200.0}
        ]


def test_sql_or_model_error_emits_error_without_complete_and_releases_occupancy(
    business_mysql_db, controlled_chat_server
):
    model_url, state = controlled_chat_server
    state["mode"] = "bad_sql"
    with TestClient(create_app()) as client:
        agent_id, session_id, _ = _setup_agent_and_model(client, model_url, business_mysql_db)
        resp = client.get(
            "/api/stream/search",
            params={"agentId": str(agent_id), "conversationId": session_id, "query": "坏SQL"},
        )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events[-1][0] == "error"
        assert events[-1][1]["error"] is True
        assert events[-1][1]["complete"] is False
        assert events[-1][1]["text"]
        assert not any(name == "complete" for name, _ in events)

        with client.app.state.engine.connect() as conn:
            active_tid = conn.execute(
                text(
                    "SELECT active_thread_id FROM agent_session_runtime "
                    "WHERE agent_id=:aid AND conversation_id=:cid"
                ),
                {"aid": agent_id, "cid": session_id},
            ).scalar_one()
            assert active_tid is None
