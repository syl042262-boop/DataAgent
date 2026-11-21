"""HTTP/SSE tests for logical relations CRUD, column validation, two-table query context, and config fingerprint."""

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from workflow_provider import workflow_reply

from app.effective_config import read_effective_config
from app.main import create_app


@pytest.fixture
def two_table_mysql_db():
    configured = os.environ["DATAAGENT_TEST_DATABASE_URL"]
    url = make_url(configured)
    db_name = "dataagent_rel_" + uuid.uuid4().hex
    engine = create_engine(url.set(database=None))
    with engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE DATABASE `{db_name}`")
        conn.exec_driver_sql(
            f"CREATE TABLE `{db_name}`.t_user (id INT PRIMARY KEY, username VARCHAR(50))"
        )
        conn.exec_driver_sql(
            f"CREATE TABLE `{db_name}`.t_order (id INT PRIMARY KEY, buyer_uid INT, amount DECIMAL(10,2))"
        )
        conn.exec_driver_sql(f"INSERT INTO `{db_name}`.t_user VALUES (10, 'Alice')")
        conn.exec_driver_sql(f"INSERT INTO `{db_name}`.t_order VALUES (1, 10, 88.50)")
    try:
        yield {
            "name": "Two Table DB",
            "type": "mysql",
            "host": url.host,
            "port": url.port or 3306,
            "databaseName": db_name,
            "username": url.username,
            "password": url.password,
        }
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"DROP DATABASE `{db_name}`")
        engine.dispose()


def test_logical_relations_crud_validation_two_table_query_and_fingerprint(two_table_mysql_db):
    captured_systems: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            messages = payload.get("messages") or []
            sys_msg = messages[0]["content"] if messages else ""
            captured_systems.append(sys_msg)
            structured_reply = workflow_reply(messages)
            if structured_reply is not None:
                reply = structured_reply
            elif "数据库 Schema" in sys_msg:
                if "t_order.buyer_uid -> t_user.id" in sys_msg:
                    reply = (
                        "SELECT u.username, o.amount FROM t_order o "
                        "JOIN t_user u ON o.buyer_uid = u.id"
                    )
                else:
                    reply = "SELECT buyer_uid, amount FROM t_order"
            else:
                reply = "已完成双表查询。"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"choices": [{"message": {"content": reply}}]}).encode())

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
                    "apiKey": "secret-model-key",
                    "modelName": "m",
                    "modelType": "CHAT",
                },
            )
            model_id = client.get("/api/model-config/list").json()["data"][0]["id"]
            assert client.post(f"/api/model-config/activate/{model_id}").json()["success"]
            ds = client.post("/api/datasource", json=two_table_mysql_db).json()
            ds_id = ds["id"]
            agent = client.post("/api/agent", json={"name": "Join Agent"}).json()
            client.post(f"/api/agent/{agent['id']}/datasources/{ds_id}")
            client.post(
                f"/api/agent/{agent['id']}/datasources/tables",
                json={"datasourceId": ds_id, "tables": ["t_user", "t_order"]},
            )
            client.post(f"/api/agent/{agent['id']}/datasources/init")

            # Invalid column mapping rejected
            bad_rel = client.post(
                f"/api/datasource/{ds_id}/logical-relations",
                json={
                    "sourceTableName": "t_order",
                    "sourceColumnName": "missing_col",
                    "targetTableName": "t_user",
                    "targetColumnName": "id",
                },
            ).json()
            assert bad_rel["success"] is False

            # Baseline query BEFORE logical relation
            s1 = client.post(f"/api/agent/{agent['id']}/sessions", json={"title": "Before"}).json()
            r1 = client.get(
                "/api/stream/search",
                params={"agentId": agent["id"], "conversationId": s1["id"], "query": "查订单用户名"},
            )
            assert "SELECT buyer_uid, amount FROM t_order" in r1.text

            with client.app.state.engine.connect() as conn:
                fp_before = read_effective_config(conn, agent["id"])
                assert "secret-model-key" not in json.dumps(fp_before)
                assert two_table_mysql_db["password"] not in json.dumps(fp_before)
            http_eff = client.get(f"/api/agent/{agent['id']}/effective-config").json()["data"]
            assert http_eff["configFingerprint"] == fp_before["configFingerprint"]
            assert "secret-model-key" not in json.dumps(http_eff)

            # Create logical relation
            created = client.post(
                f"/api/datasource/{ds_id}/logical-relations",
                json={
                    "sourceTableName": "t_order",
                    "sourceColumnName": "buyer_uid",
                    "targetTableName": "t_user",
                    "targetColumnName": "id",
                    "relationType": "N:1",
                    "description": "订单通过buyer_uid关联用户id",
                },
            ).json()
            assert created["success"] is True
            rel_id = created["data"]["id"]

            # Query AFTER logical relation: JOIN SQL + Alice in result
            s2 = client.post(f"/api/agent/{agent['id']}/sessions", json={"title": "After"}).json()
            r2 = client.get(
                "/api/stream/search",
                params={"agentId": agent["id"], "conversationId": s2["id"], "query": "查订单用户名"},
            )
            assert "JOIN t_user u ON o.buyer_uid = u.id" in r2.text
            assert "Alice" in r2.text

            with client.app.state.engine.connect() as conn:
                fp_after = read_effective_config(conn, agent["id"])
                assert fp_after["configFingerprint"] != fp_before["configFingerprint"]

            # Password rotation does NOT change fingerprint
            client.put(f"/api/datasource/{ds_id}", json={"password": two_table_mysql_db["password"]})
            with client.app.state.engine.connect() as conn:
                fp_rotated = read_effective_config(conn, agent["id"])
                assert fp_rotated["configFingerprint"] == fp_after["configFingerprint"]

            # Update, batch save, and delete
            upd = client.put(
                f"/api/datasource/{ds_id}/logical-relations/{rel_id}",
                json={
                    "sourceTableName": "t_order",
                    "sourceColumnName": "buyer_uid",
                    "targetTableName": "t_user",
                    "targetColumnName": "id",
                    "relationType": "N:1",
                    "description": "更新后的描述",
                },
            ).json()
            assert upd["success"] is True
            assert upd["data"]["description"] == "更新后的描述"

            batch = client.put(
                f"/api/datasource/{ds_id}/logical-relations",
                json=[
                    {
                        "id": rel_id,
                        "sourceTableName": "t_order",
                        "sourceColumnName": "buyer_uid",
                        "targetTableName": "t_user",
                        "targetColumnName": "id",
                        "relationType": "N:1",
                        "description": "批量保留",
                    }
                ],
            ).json()
            assert batch["success"] is True
            assert len(batch["data"]) == 1

            assert client.delete(f"/api/datasource/{ds_id}/logical-relations/{rel_id}").json()["success"] is True
            assert client.get(f"/api/datasource/{ds_id}/logical-relations").json()["data"] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
