"""HTTP/SSE tests for PostgreSQL datasource configuration, metadata, dialect SQL, and error handling."""

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from workflow_provider import workflow_reply

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
def business_pg_db():
    pg_url_raw = os.environ.get(
        "DATAAGENT_TEST_POSTGRES_URL",
        "postgresql+psycopg://dataagent:dataagent_pg@127.0.0.1:15432/dataagent_pg",
    )
    url = make_url(pg_url_raw)
    schema = "biz_" + uuid.uuid4().hex[:12]
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        conn.exec_driver_sql(
            f'CREATE TABLE "{schema}"."OrderItems" ('
            '"itemId" UUID PRIMARY KEY, '
            '"productName" VARCHAR(100) NOT NULL, '
            '"amount" NUMERIC(12,2) NOT NULL, '
            '"meta" JSONB NOT NULL, '
            '"createdAt" TIMESTAMPTZ NOT NULL DEFAULT NOW()'
            ")"
        )
        conn.exec_driver_sql(
            f'INSERT INTO "{schema}"."OrderItems" ("itemId", "productName", "amount", "meta") VALUES '
            "('11111111-1111-1111-1111-111111111111', 'Widget', 42.50, '{\"tier\": \"pro\"}'), "
            "('22222222-2222-2222-2222-222222222222', 'Gadget', 17.50, '{\"tier\": \"basic\"}')"
        )
    try:
        yield {
            "name": "PG Analytics",
            "type": "postgresql",
            "host": url.host,
            "port": url.port or 5432,
            "databaseName": url.database,
            "schemaName": schema,
            "username": url.username,
            "password": url.password,
            "schema": schema,
            "engine": engine,
        }
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        engine.dispose()


def _create_pg_model_server(captured_messages: list[list[dict]], sql_to_return: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            messages = payload.get("messages") or []
            captured_messages.append(messages)
            system_text = messages[0]["content"] if messages else ""
            structured_reply = workflow_reply(messages)
            if structured_reply is not None:
                content = structured_reply
            elif "数据库 Schema" in system_text:
                content = sql_to_return
            else:
                content = "PostgreSQL 查询完成，共返回 2 条记录。"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def test_postgresql_metadata_binding_and_real_query(business_pg_db):
    captured: list[list[dict]] = []
    sql_reply = (
        'SELECT "itemId", "productName", "amount", "meta" '
        'FROM "OrderItems" ORDER BY "amount" DESC'
    )
    server, thread, base_url = _create_pg_model_server(captured, sql_reply)
    try:
        with TestClient(create_app()) as client:
            assert client.post(
                "/api/model-config/add",
                json={
                    "provider": "openai",
                    "baseUrl": base_url,
                    "apiKey": "pg-key",
                    "modelName": "gpt-test",
                    "modelType": "CHAT",
                },
            ).json()["success"]
            model_id = client.get("/api/model-config/list").json()["data"][0]["id"]
            assert client.post(f"/api/model-config/activate/{model_id}").json()["success"]

            source_payload = {
                k: v for k, v in business_pg_db.items() if k not in ("schema", "engine")
            }
            datasource = client.post("/api/datasource", json=source_payload).json()
            assert datasource["type"] == "postgresql"
            assert datasource["password"] == "******"

            ds_path = f"/api/datasource/{datasource['id']}"
            assert client.post(ds_path + "/test").json()["success"] is True
            assert client.get(ds_path + "/tables").json() == ["OrderItems"]
            assert client.get(ds_path + "/tables/OrderItems/columns").json()["data"] == [
                "itemId",
                "productName",
                "amount",
                "meta",
                "createdAt",
            ]

            agent = client.post("/api/agent", json={"name": "PG Analyst"}).json()
            bindings = f"/api/agent/{agent['id']}/datasources"
            assert client.post(bindings + f"/{datasource['id']}").json()["success"]
            assert client.post(
                bindings + "/tables",
                json={"datasourceId": datasource["id"], "tables": ["OrderItems"]},
            ).json()["success"]
            assert client.post(bindings + "/init").json()["success"]

            session = client.post(
                f"/api/agent/{agent['id']}/sessions", json={"title": "PG 查询"}
            ).json()

            resp = client.get(
                "/api/stream/search",
                params={
                    "agentId": agent["id"],
                    "conversationId": session["id"],
                    "query": "列出所有订单项",
                },
            )
            assert resp.status_code == 200
            events = _parse_sse(resp.text)
            names = [e[0] for e in events]
            assert names[-1] == "complete"
            assert "error" not in names

            # Verify PostgreSQL dialect prompt reached the model
            sql_gen_calls = [
                m for m in captured if m and ("数据库 Schema" in m[0]["content"])
            ]
            assert sql_gen_calls
            assert "PostgreSQL" in sql_gen_calls[0][0]["content"]
            assert "双引号" in sql_gen_calls[0][0]["content"]

            # Verify PostgreSQL types (UUID, NUMERIC, JSONB) serialized cleanly
            result_events = [e[1] for e in events if e[1].get("textType") == "RESULT_SET"]
            assert len(result_events) == 1
            result_set = json.loads(result_events[0]["text"])["resultSet"]
            assert result_set["column"] == ["itemId", "productName", "amount", "meta"]
            assert result_set["data"][0]["itemId"] == "11111111-1111-1111-1111-111111111111"
            assert result_set["data"][0]["amount"] == 42.5
            assert result_set["data"][0]["meta"] == {"tier": "pro"}

            # Reopen session / verify persisted result snapshot is readable
            sessions_list = client.get(f"/api/agent/{agent['id']}/sessions").json()
            assert any(s["id"] == session["id"] for s in sessions_list)
            with client.app.state.engine.connect() as conn:
                persisted = conn.execute(
                    text(
                        "SELECT r.final_answer, r.artifacts, r.messages FROM agent_run_result r "
                        "JOIN agent_run ar ON ar.thread_id = r.thread_id "
                        "WHERE ar.conversation_id = :cid"
                    ),
                    {"cid": session["id"]},
                ).mappings().first()
            assert persisted is not None
            assert "PostgreSQL 查询完成" in persisted["final_answer"]
            assert "11111111-1111-1111-1111-111111111111" in str(persisted["artifacts"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_postgresql_url_credentials_and_errors(business_pg_db):
    with TestClient(create_app()) as client:
        bad_url_payload = {
            **{k: v for k, v in business_pg_db.items() if k not in ("schema", "engine")},
            "connectionUrl": "jdbc:postgresql://dataagent:secret@127.0.0.1:15432/dataagent_pg",
        }
        res = client.post("/api/datasource", json=bad_url_payload)
        assert res.json()["success"] is False

        bad_cred_payload = {
            **{k: v for k, v in business_pg_db.items() if k not in ("schema", "engine")},
            "password": "wrong_password",
        }
        ds = client.post("/api/datasource", json=bad_cred_payload).json()
        test_res = client.post(f"/api/datasource/{ds['id']}/test").json()
        assert test_res["success"] is False


def test_postgresql_query_error_timeout_and_connection_release(business_pg_db):
    captured: list[list[dict]] = []
    # 1st call: SQL error; 2nd call: timeout via pg_sleep; 3rd call: valid query
    iter(
        [
            'SELECT "nonexistent_col" FROM "OrderItems"',
            "SELECT pg_sleep(2) AS slept",
            'SELECT COUNT(*) AS cnt FROM "OrderItems"',
        ]
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            messages = payload.get("messages") or []
            captured.append(messages)
            sys_msg = messages[0]["content"] if messages else ""
            content = workflow_reply(messages)
            if content is None:
                if "数据库 Schema" in sys_msg:
                    question = messages[-1]['content']
                    content = ('SELECT * FROM nonexistent_table_xyz' if question == 'bad' else
                               'SELECT pg_sleep(3)' if question == 'slow' else
                               'SELECT COUNT(*) AS count FROM "OrderItems"')
                else:
                    content = '完成' 
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": content}}]}).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with TestClient(create_app()) as client:
            client.post(
                "/api/model-config/add",
                json={
                    "provider": "openai",
                    "baseUrl": f"http://127.0.0.1:{server.server_port}",
                    "apiKey": "pg-key",
                    "modelName": "gpt-test",
                    "modelType": "CHAT",
                },
            )
            model_id = client.get("/api/model-config/list").json()["data"][0]["id"]
            assert client.post(f"/api/model-config/activate/{model_id}").json()["success"]

            source_payload = {
                k: v for k, v in business_pg_db.items() if k not in ("schema", "engine")
            }
            source_payload["connectionUrl"] = (
                f"jdbc:postgresql://{business_pg_db['host']}:{business_pg_db['port']}"
                f"/{business_pg_db['databaseName']}?socketTimeout=1"
            )
            ds = client.post("/api/datasource", json=source_payload).json()
            agent = client.post("/api/agent", json={"name": "PG Error Agent"}).json()
            client.post(f"/api/agent/{agent['id']}/datasources/{ds['id']}")
            client.post(
                f"/api/agent/{agent['id']}/datasources/tables",
                json={"datasourceId": ds["id"], "tables": ["OrderItems"]},
            )
            client.post(f"/api/agent/{agent['id']}/datasources/init")

            s1 = client.post(f"/api/agent/{agent['id']}/sessions", json={"title": "Err"}).json()
            r1 = client.get(
                "/api/stream/search",
                params={"agentId": agent["id"], "conversationId": s1["id"], "query": "bad"},
            )
            events1 = _parse_sse(r1.text)
            assert [e[0] for e in events1][-1] == "error"

            s2 = client.post(f"/api/agent/{agent['id']}/sessions", json={"title": "Timeout"}).json()
            r2 = client.get(
                "/api/stream/search",
                params={"agentId": agent["id"], "conversationId": s2["id"], "query": "slow"},
            )
            events2 = _parse_sse(r2.text)
            assert [e[0] for e in events2][-1] == "error"

            # After error and timeout, new query succeeds and no connections remain leaked
            s3 = client.post(f"/api/agent/{agent['id']}/sessions", json={"title": "Ok"}).json()
            r3 = client.get(
                "/api/stream/search",
                params={"agentId": agent["id"], "conversationId": s3["id"], "query": "count"},
            )
            events3 = _parse_sse(r3.text)
            assert [e[0] for e in events3][-1] == "complete"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
