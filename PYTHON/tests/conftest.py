"""HTTP tests use a disposable schema on a real MySQL server."""

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


@pytest.fixture(autouse=True)
def isolated_management_database(tmp_path_factory):
    configured = os.environ.get("DATAAGENT_TEST_DATABASE_URL")
    if not configured:
        pytest.fail(
            "Set DATAAGENT_TEST_DATABASE_URL to a disposable MySQL server (CREATE DATABASE required)"
        )
    url = make_url(configured)
    database = "dataagent_test_" + uuid.uuid4().hex
    engine = create_engine(url.set(database=None))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"CREATE DATABASE `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_bin"
        )
    previous = {
        key: os.environ.get(key) for key in ("DATAAGENT_DATABASE_URL", "DATAAGENT_DATA_DIR")
    }
    os.environ["DATAAGENT_DATABASE_URL"] = url.set(database=database).render_as_string(
        hide_password=False
    )
    os.environ["DATAAGENT_DATA_DIR"] = str(tmp_path_factory.mktemp("checkpoints"))
    try:
        yield
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{database}`")
        engine.dispose()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def model_server():
    """Controlled output only at the external provider HTTP boundary."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.headers.get("Authorization") != "Bearer fixture-key":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error":"fixture-key must not be echoed"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if self.path == "/v1/chat/completions":
                result = {"choices": [{"message": {"content": "Hello"}}]}
            elif self.path == "/custom/embed":
                result = {"data": [{"embedding": [0.2, 0.4, 0.6]}]}
            else:
                result = {"unexpected": True}
            if payload["model"] == "empty-output":
                result = {"choices": [{"message": {"content": ""}}]}
            self.wfile.write(json.dumps(result).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
