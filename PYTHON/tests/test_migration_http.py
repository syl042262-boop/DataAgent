"""Migration acceptance via the approved CLI and HTTP boundaries, on a Java SQL copy."""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlparse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.main import create_app


@pytest.fixture(
    params=[
        ("legacy", "/api/upload/files"),
        ("bcrypt", "/api/upload/files"),
        ("legacy", "/uploads"),
        ("bcrypt", "/api/upload/uploads"),
    ]
)
def java_copy(tmp_path, monkeypatch, request):
    key_encoding, source_prefix = request.param
    configured = make_url(os.environ["DATAAGENT_TEST_DATABASE_URL"])
    name = "dataagent_java_copy_" + uuid.uuid4().hex
    server = create_engine(configured.set(database=None))
    with server.begin() as conn:
        conn.exec_driver_sql(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin")
    url = configured.set(database=name)
    engine = create_engine(url)
    root = Path(__file__).resolve().parents[2]
    scripts = root / "JAVA/data-agent-management/src/main/resources/sql"
    with engine.begin() as conn:
        for filename in ["schema.sql", "data.sql"]:
            for statement in sqlparse.split((scripts / filename).read_text(encoding="utf-8-sig")):
                if statement.strip():
                    conn.exec_driver_sql(statement.replace("%", "%%"))
        import bcrypt

        key = "sk-migration-example"
        if key_encoding == "bcrypt":
            key = "{bcrypt}" + bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode() + "::mple"
        conn.execute(
            text("UPDATE agent SET api_key=:key,api_key_enabled=1 WHERE id=1"), {"key": key}
        )
        conn.execute(
            text(
                "INSERT INTO chat_session(id,agent_id,title) VALUES ('legacy-session',1,'Old chat')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO chat_message(id,session_id,role,content,message_type) "
                "VALUES (800,'legacy-session','assistant','Historical PYTHON print(1)','PYTHON')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO agent_datasource_tables(agent_datasource_id,table_name) VALUES (1,'orders')"
            )
        )
        from PIL import Image

        prefix_path = "" if source_prefix == "/api/upload/files" else "data-agent/"
        avatar_path = prefix_path + "avatars/legacy.png"
        report_path = prefix_path + "reports/legacy.html"
        (tmp_path / avatar_path).parent.mkdir(parents=True)
        Image.new("RGB", (4, 4), "blue").save(tmp_path / avatar_path)
        (tmp_path / report_path).parent.mkdir(parents=True)
        (tmp_path / report_path).write_text("<h1>Historical revenue</h1>", encoding="utf-8")
        conn.execute(
            text("UPDATE agent SET avatar=:avatar WHERE id=1"),
            {"avatar": source_prefix + "/" + avatar_path},
        )
        conn.execute(
            text(
                "INSERT INTO chat_message(id,session_id,role,content,message_type,metadata) "
                "VALUES (801,'legacy-session','assistant',:content,'report',:metadata)"
            ),
            {
                "content": f'<a href="{source_prefix}/{report_path}">Report</a>',
                "metadata": json.dumps({"artifact": source_prefix + "/" + report_path}),
            },
        )
        conn.execute(
            text(
                "INSERT INTO agent_knowledge(id,agent_id,title,type,file_path,is_deleted) "
                "VALUES (91,1,'Removed file','DOCUMENT','missing.txt',1)"
            )
        )
        conn.exec_driver_sql("CREATE TABLE java_checkpoint (id INT PRIMARY KEY, payload TEXT)")
        conn.exec_driver_sql("INSERT INTO java_checkpoint VALUES (1,'do not execute')")
        (tmp_path / "legacy.txt").write_text("Copied policy excludes refunds.", encoding="utf-8")
        conn.execute(
            text(
                "INSERT INTO agent_knowledge(id,agent_id,title,type,file_path,file_type) "
                "VALUES (90,1,'File policy','DOCUMENT','legacy.txt','txt')"
            )
        )
    try:
        monkeypatch.setenv(
            "DATAAGENT_MIGRATION_SOURCE_URL", url.render_as_string(hide_password=False)
        )
        yield tmp_path
    finally:
        engine.dispose()
        with server.begin() as conn:
            conn.exec_driver_sql(f"DROP DATABASE `{name}`")
        server.dispose()


def test_java_copy_import_is_repeatable_and_preserves_http_history_and_access(java_copy):
    files = java_copy
    env = os.environ.copy()
    command = [sys.executable, "-m", "app.migration", "--source-files", str(files)]
    dry = subprocess.run(
        command, check=False, env=env, capture_output=True, text=True, encoding="utf-8"
    )
    assert dry.returncode == 0, dry.stdout + dry.stderr
    report = json.loads(dry.stdout)
    assert report["status"] == "VALIDATED" and len(report["businessTables"]) == 13
    assert report["memoryPolicy"] == "REBUILD_FROM_NEW_SUCCESSFUL_TURNS"
    with TestClient(create_app()) as client:
        assert client.get("/api/agent/list").json() == []
    applied = subprocess.run(
        command + ["--apply"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert json.loads(applied.stdout)["status"] == "IMPORTED"
    again = subprocess.run(
        command + ["--apply"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert again.returncode == 0, again.stdout + again.stderr
    assert json.loads(again.stdout)["status"] == "ALREADY_IMPORTED"
    with TestClient(create_app()) as client:
        assert len(client.get("/api/agent/list").json()) == 4
        assert client.get("/api/agent/1/access").status_code == 401
        headers = {"X-API-Key": "sk-migration-example"}
        assert client.get("/api/agent/1/access", headers=headers).status_code == 200
        messages = client.get("/api/sessions/legacy-session/messages", headers=headers).json()
        assert len(messages) == 2 and messages[0]["id"] == 800
        assert messages[0]["content"] == "Historical PYTHON print(1)"
        report_url = json.loads(messages[1]["metadata"])["artifact"]
        assert report_url.startswith("/api/upload/files/reports/")
        assert report_url in messages[1]["content"]
        assert client.get(report_url).content == b"<h1>Historical revenue</h1>"
        avatar = client.get("/api/agent/1").json()["avatar"]
        assert avatar.startswith("/api/upload/files/avatars/")
        assert client.get(avatar).headers["content-type"] == "image/png"
        record = client.get("/api/agent-knowledge/90").json()["data"]
        assert record["embeddingStatus"] == "FAILED"
        assert client.get(record["fileUrl"]).content == b"Copied policy excludes refunds."
        assert (
            client.get("/api/sessions/legacy-session/runs", headers=headers).json()["data"]["items"]
            == []
        )
        assert client.delete("/api/sessions/legacy-session", headers=headers).status_code == 200
    with TestClient(create_app()) as client:
        assert client.get(report_url).status_code == 404
        assert client.get(avatar).status_code == 200
        assert client.get(record["fileUrl"]).status_code == 200


def test_failed_import_rolls_back_business_rows_and_can_retry(java_copy):
    source = create_engine(os.environ["DATAAGENT_MIGRATION_SOURCE_URL"])
    try:
        with source.begin() as conn:
            conn.exec_driver_sql(
                "ALTER TABLE agent_knowledge ADD COLUMN unsupported_copy_field INT"
            )
        command = [
            sys.executable,
            "-m",
            "app.migration",
            "--source-files",
            str(java_copy),
            "--apply",
        ]
        failed = subprocess.run(
            command, check=False, capture_output=True, text=True, encoding="utf-8"
        )
        assert failed.returncode == 1
        assert "agent_knowledge" in json.loads(failed.stdout)["error"]
        with TestClient(create_app()) as client:
            assert client.get("/api/agent/list").json() == []
        with source.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE agent_knowledge DROP COLUMN unsupported_copy_field")
        retry = subprocess.run(
            command, check=False, capture_output=True, text=True, encoding="utf-8"
        )
        assert retry.returncode == 0, retry.stdout
        with TestClient(create_app()) as client:
            assert len(client.get("/api/agent/list").json()) == 4
    finally:
        source.dispose()


def test_import_refuses_reused_python_database_even_after_agent_cleanup(java_copy):
    with TestClient(create_app()) as client:
        aid = client.post("/api/agent", json={"name": "Old target"}).json()["id"]
        assert client.delete(f"/api/agent/{aid}").status_code == 200
    with TestClient(create_app()) as client:
        assert client.get("/api/agent/list").json() == []
    result = subprocess.run(
        [sys.executable, "-m", "app.migration", "--source-files", str(java_copy), "--apply"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    assert "fresh" in json.loads(result.stdout)["error"].lower()


@pytest.mark.parametrize(
    "backend,url",
    [
        ("local", ""),
        ("elasticsearch", "http://127.0.0.1:19200"),
        ("milvus", "http://127.0.0.1:19531"),
    ],
)
def test_embedding_space_migration_rebuilds_before_switch(model_server, monkeypatch, backend, url):
    monkeypatch.setenv("DATAAGENT_VECTOR_BACKEND", backend)
    monkeypatch.setenv("DATAAGENT_VECTOR_URL", url)
    namespace = "migrate_" + uuid.uuid4().hex
    monkeypatch.setenv("DATAAGENT_VECTOR_NAMESPACE", namespace)
    from test_knowledge_http import activate_embedding

    with TestClient(create_app()) as client:
        activate_embedding(client, model_server)
        aid = client.post("/api/agent", json={"name": "Index migration"}).json()["id"]
        row = client.post(
            "/api/business-knowledge",
            json={"agentId": aid, "businessTerm": "Revenue", "description": "Paid revenue"},
        ).json()["data"]
        models = client.get("/api/model-config/list").json()["data"]
        original = next(model for model in models if model["modelType"] == "EMBEDDING")
        replacement = {**original, "modelName": "next-embedding-space", "apiKey": "fixture-key"}
        replacement.pop("id")
        client.post("/api/model-config/add", json=replacement)
        target = next(
            model
            for model in client.get("/api/model-config/list").json()["data"]
            if model["modelName"] == "next-embedding-space"
        )
        # Online hot switching remains guarded.
        assert (
            client.post("/api/model-config/activate/" + str(target["id"])).json()["success"]
            is False
        )
    command = [sys.executable, "-m", "app.vector_operations", "--model-id", str(target["id"])]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["status"] == "REBUILT_AND_ACTIVATED"
    with TestClient(create_app()) as client:
        updated = client.get("/api/business-knowledge/" + str(row["id"])).json()["data"]
        assert updated["embeddingStatus"] == "COMPLETED"
        assert updated["embeddingSpace"] != row["embeddingSpace"]
        hits = client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "revenue"}).json()[
            "data"
        ]
        assert len(hits) == 1 and hits[0]["embeddingSpace"] == updated["embeddingSpace"]


def test_failed_embedding_migration_keeps_default_and_can_retry(model_server):
    from test_knowledge_http import activate_embedding

    with TestClient(create_app()) as client:
        activate_embedding(client, model_server)
        aid = client.post("/api/agent", json={"name": "Migration failure"}).json()["id"]
        client.post(
            "/api/business-knowledge",
            json={"agentId": aid, "businessTerm": "Revenue", "description": "Paid"},
        )
        old = next(
            model
            for model in client.get("/api/model-config/list").json()["data"]
            if model["modelType"] == "EMBEDDING"
        )
        target = {**old, "modelName": "new-space", "apiKey": "wrong-key"}
        target.pop("id")
        client.post("/api/model-config/add", json=target)
        target = next(
            model
            for model in client.get("/api/model-config/list").json()["data"]
            if model["modelName"] == "new-space"
        )
    command = [sys.executable, "-m", "app.vector_operations", "--model-id", str(target["id"])]
    failed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    assert failed.returncode == 1
    assert "wrong-key" not in failed.stdout
    with TestClient(create_app()) as client:
        current = client.get("/api/model-config/list").json()["data"]
        assert next(model for model in current if model["isActive"])["id"] == old["id"]
        target["apiKey"] = "fixture-key"
        client.put("/api/model-config/update", json=target)
    retry = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    assert retry.returncode == 0, retry.stdout
    with TestClient(create_app()) as client:
        hits = client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "revenue"}).json()[
            "data"
        ]
        assert len(hits) == 1


@pytest.fixture
def interrupted_embedding_server():
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    failures = {"remaining": 1}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if (
                payload["model"] == "target-space"
                and "Second" in payload["input"]
                and failures["remaining"]
            ):
                failures["remaining"] -= 1
                self.send_response(503)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"data":[{"embedding":[0.2,0.4,0.6]}]}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        worker.join()
        server.server_close()


@pytest.mark.parametrize(
    "backend,url",
    [
        ("local", ""),
        ("elasticsearch", "http://127.0.0.1:19200"),
        ("milvus", "http://127.0.0.1:19531"),
    ],
)
def test_partial_staging_failure_preserves_old_recall_after_restart(
    interrupted_embedding_server,
    monkeypatch,
    backend,
    url,
):
    from test_knowledge_http import activate_embedding

    monkeypatch.setenv("DATAAGENT_VECTOR_BACKEND", backend)
    monkeypatch.setenv("DATAAGENT_VECTOR_URL", url)
    namespace = "staging_" + uuid.uuid4().hex
    monkeypatch.setenv("DATAAGENT_VECTOR_NAMESPACE", namespace)
    with TestClient(create_app()) as client:
        activate_embedding(client, interrupted_embedding_server)
        aid = client.post("/api/agent", json={"name": "Staging"}).json()["id"]
        rows = [
            client.post(
                "/api/business-knowledge",
                json={"agentId": aid, "businessTerm": name, "description": "Paid revenue"},
            ).json()["data"]
            for name in ("Second", "First")
        ]
        old = next(m for m in client.get("/api/model-config/list").json()["data"] if m["isActive"])
        target = {**old, "modelName": "target-space", "apiKey": "fixture-key"}
        target.pop("id")
        client.post("/api/model-config/add", json=target)
        target = next(
            m
            for m in client.get("/api/model-config/list").json()["data"]
            if m["modelName"] == "target-space"
        )
    command = [sys.executable, "-m", "app.vector_operations", "--model-id", str(target["id"])]
    failed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    assert failed.returncode == 1
    with TestClient(create_app()) as client:
        for row in rows:
            current = client.get("/api/business-knowledge/" + str(row["id"])).json()["data"]
            assert current["embeddingStatus"] == "COMPLETED"
            assert current["embeddingSpace"] == row["embeddingSpace"]
        hits = client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "Paid"}).json()[
            "data"
        ]
        assert len(hits) == 2
    retry = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    assert retry.returncode == 0, retry.stdout
    with TestClient(create_app()) as client:
        hits = client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "Paid"}).json()[
            "data"
        ]
        assert len(hits) == 2 and all(
            hit["embeddingSpace"] != rows[0]["embeddingSpace"] for hit in hits
        )
    if backend != "local":
        from app.external_vectors import create_external_index

        index = create_external_index(backend, url, namespace)
        index.drop(rows[0]["embeddingSpace"], 3)
        index.drop(hits[0]["embeddingSpace"], 3)
