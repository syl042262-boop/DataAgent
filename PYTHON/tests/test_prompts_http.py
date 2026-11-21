"""HTTP/SSE tests for prompt configuration CRUD, compatibility checks, priority, and runtime injection."""

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

from app.main import create_app
from app.prompts import ALLOWED_PLAN_TOOLS, DEFAULT_PROMPTS, check_prompt_compatibility


@pytest.fixture
def prompt_mysql_db():
    configured = os.environ["DATAAGENT_TEST_DATABASE_URL"]
    url = make_url(configured)
    db_name = "dataagent_prompt_" + uuid.uuid4().hex
    engine = create_engine(url.set(database=None))
    with engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE DATABASE `{db_name}`")
        conn.exec_driver_sql(
            f"CREATE TABLE `{db_name}`.metrics (id INT PRIMARY KEY, label VARCHAR(50), val INT)"
        )
        conn.exec_driver_sql(f"INSERT INTO `{db_name}`.metrics VALUES (1, 'alpha', 100)")
    try:
        yield {
            "name": "Prompt Test DB",
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


def test_prompt_crud_priority_ordering_and_compatibility_guards():
    for ptype, content in DEFAULT_PROMPTS.items():
        assert check_prompt_compatibility(ptype, content) == []
    assert "PYTHON_GENERATE_NODE" not in ALLOWED_PLAN_TOOLS

    with TestClient(create_app()) as client:
        types = client.get("/api/prompt-config/types").json()["data"]
        assert "python-generator" not in types
        assert set(types) == {"report-generator", "planner", "sql-generator", "rewrite"}

        # Save two prompts with duplicate priority, different displayOrder
        p1 = client.post(
            "/api/prompt-config/save",
            json={
                "name": "SQL Rule B",
                "promptType": "sql-generator",
                "optimizationPrompt": "始终返回中文列别名",
                "enabled": True,
                "priority": 10,
                "displayOrder": 2,
            },
        ).json()
        assert p1["success"] is True
        p1_id = p1["data"]["id"]

        p2 = client.post(
            "/api/prompt-config/save",
            json={
                "name": "SQL Rule A",
                "promptType": "sql-generator",
                "optimizationPrompt": "优先过滤无效记录",
                "enabled": True,
                "priority": 10,
                "displayOrder": 1,
            },
        ).json()
        assert p2["success"] is True
        p2_id = p2["data"]["id"]

        active_all = client.get("/api/prompt-config/active-all/sql-generator").json()
        assert active_all["hasOptimizationConfigs"] is True
        assert [c["id"] for c in active_all["data"]] == [p2_id, p1_id]

        # Priority & displayOrder updates
        assert client.post(f"/api/prompt-config/{p1_id}/priority", json={"priority": 20}).json()["success"]
        assert client.post(f"/api/prompt-config/{p2_id}/display-order", json={"displayOrder": 5}).json()["success"]
        active_one = client.get("/api/prompt-config/active/sql-generator").json()
        assert active_one["hasCustomConfig"] is True
        assert active_one["data"]["id"] == p1_id

        # Disable & batch-enable / batch-disable
        assert client.post(f"/api/prompt-config/{p1_id}/disable").json()["success"]
        assert client.get(f"/api/prompt-config/{p1_id}").json()["data"]["enabled"] is False
        assert client.post("/api/prompt-config/batch-enable", json=[p1_id, p2_id]).json()["success"]
        assert client.post("/api/prompt-config/batch-disable", json=[p1_id]).json()["success"]
        assert client.get(f"/api/prompt-config/{p1_id}").json()["data"]["enabled"] is False

        # Incompatible prompt: preserves original text, reports line/column, blocks activation
        bad_text = "第一行正常\n第二步请使用 PYTHON_GENERATE_NODE 执行分析"
        bad_save = client.post(
            "/api/prompt-config/save",
            json={
                "name": "Legacy Python Prompt",
                "promptType": "planner",
                "optimizationPrompt": bad_text,
                "enabled": True,
            },
        ).json()
        assert bad_save["success"] is False
        assert bad_save["data"]["systemPrompt"] == bad_text
        assert bad_save["data"]["enabled"] is False
        assert bad_save["compatibilityIssues"][0]["line"] == 2
        assert bad_save["compatibilityIssues"][0]["matched"] == "PYTHON_GENERATE_NODE"

        bad_id = bad_save["data"]["id"]
        assert client.post(f"/api/prompt-config/{bad_id}/enable").json()["success"] is False
        assert client.get(f"/api/prompt-config/{bad_id}").json()["data"]["enabled"] is False
        assert client.post("/api/prompt-config/batch-enable", json=[p2_id, bad_id]).json()["success"] is False
        assert client.delete(f"/api/prompt-config/{bad_id}").json()["success"] is True

        # Imported config with explicit ID and Python tool instruction also blocked from activation
        imported_id = f"imported-{uuid.uuid4().hex[:8]}"
        imported_res = client.post(
            "/api/prompt-config/save",
            json={
                "id": imported_id,
                "name": "Imported Legacy Config",
                "promptType": "planner",
                "optimizationPrompt": "若无法聚合则调用 python-analyze 脚本",
                "enabled": True,
            },
        ).json()
        assert imported_res["success"] is False
        assert imported_res["data"]["id"] == imported_id
        assert imported_res["data"]["enabled"] is False
        assert imported_res["compatibilityIssues"][0]["matched"] == "python-analyze"


def test_active_prompt_enters_query_and_disabled_prompt_is_ignored(prompt_mysql_db):
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
            elif "SQL" in sys_msg:
                reply = "SELECT label, val FROM metrics"
            else:
                reply = "metrics 表中 alpha 的值为 100。"
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
                    "apiKey": "k",
                    "modelName": "m",
                    "modelType": "CHAT",
                },
            )
            model_id = client.get("/api/model-config/list").json()["data"][0]["id"]
            assert client.post(f"/api/model-config/activate/{model_id}").json()["success"]
            ds = client.post("/api/datasource", json=prompt_mysql_db).json()
            agent = client.post("/api/agent", json={"name": "Prompt Agent"}).json()
            client.post(f"/api/agent/{agent['id']}/datasources/{ds['id']}")
            client.post(
                f"/api/agent/{agent['id']}/datasources/tables",
                json={"datasourceId": ds["id"], "tables": ["metrics"]},
            )
            client.post(f"/api/agent/{agent['id']}/datasources/init")

            client.post(
                "/api/prompt-config/save",
                json={
                    "name": "Active Marker",
                    "promptType": "sql-generator",
                    "agentId": agent["id"],
                    "optimizationPrompt": "ACTIVE_MARKER_XYZ: 必须返回 label 与 val",
                    "enabled": True,
                    "priority": 5,
                },
            )
            client.post(
                "/api/prompt-config/save",
                json={
                    "name": "Disabled Marker",
                    "promptType": "sql-generator",
                    "agentId": agent["id"],
                    "optimizationPrompt": "DISABLED_MARKER_ABC: 不应生效",
                    "enabled": False,
                    "priority": 99,
                },
            )

            session = client.post(
                f"/api/agent/{agent['id']}/sessions", json={"title": "Prompt test"}
            ).json()
            resp = client.get(
                "/api/stream/search",
                params={"agentId": agent["id"], "conversationId": session["id"], "query": "查指标"},
            )
            assert resp.status_code == 200
            assert "event: complete" in resp.text
            sql_prompts = [s for s in captured_systems if "数据库 Schema" in s]
            assert len(sql_prompts) == 1
            assert "ACTIVE_MARKER_XYZ" in sql_prompts[0]
            assert "DISABLED_MARKER_ABC" not in sql_prompts[0]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
