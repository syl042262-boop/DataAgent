"""User-visible history and result recovery against real MySQL."""

# ruff: noqa: F811
import json

from fastapi.testclient import TestClient
from test_stream_query_http import business_mysql_db, controlled_chat_server  # noqa: F401

from app.main import create_app


def test_history_idempotency_auth_and_titles():
    with TestClient(create_app()) as c:
        aid = c.post("/api/agent", json={"name": "history"}).json()["id"]
        sid = c.post(f"/api/agent/{aid}/sessions").json()["id"]
        base = f"/api/sessions/{sid}"
        key = c.post(f"/api/agent/{aid}/api-key/generate").json()["data"]["apiKey"]
        c.put(f"/api/agent/{aid}/api-key/toggle", params={"enabled": True})
        assert c.get(base + "/messages").status_code == 401
        assert c.get(f"/api/agent/{aid}/sessions/stream").status_code == 401
        c.headers["X-API-Key"] = key
        body = {
            "role": "user",
            "content": "销售统计",
            "titleNeeded": True,
            "metadata": json.dumps({"messageKey": "user:1"}),
        }
        first = c.post(base + "/messages", json=body)
        assert first.status_code == 200
        assert c.post(base + "/messages", json=body).json()["id"] == first.json()["id"]
        assert c.post(base + "/messages", json={**body, "content": "不同"}).status_code == 409
        assert len(c.get(base + "/messages").json()) == 1
        assert c.put(base + "/pin", params={"isPinned": True}).json()["success"]
        assert c.put(base + "/rename", params={"title": "重命名"}).json()["success"]
        session = c.get(f"/api/agent/{aid}/sessions").json()[0]
        assert session["title"] == "重命名" and session["isPinned"]
        assert c.post(base + "/messages", json={**body, "metadata": "false"}).status_code == 400


from test_stream_query_http import (
    _setup_agent_and_model,
)


def test_completed_run_discovered_after_restart_without_saving_stream(
    business_mysql_db,
    controlled_chat_server,
    monkeypatch,
):
    model_url, state = controlled_chat_server
    app = create_app()
    with TestClient(app) as c:
        aid, sid, _ = _setup_agent_and_model(c, model_url, business_mysql_db)
        from app import stream

        original_sse = stream._sse

        def crash_before_final(event, data):
            if data.get("eventType") == "FINAL_ANSWER":
                raise RuntimeError("injected transport failure after terminal commit")
            return original_sse(event, data)

        monkeypatch.setattr(stream, "_sse", crash_before_final)
        # Fail after durable terminal commit, before a final answer reaches the browser.
        assert (
            c.get(
                "/api/stream/search",
                params={"agentId": aid, "conversationId": sid, "query": "销售额"},
            ).status_code
            == 200
        )
        assert c.get(f"/api/sessions/{sid}/messages").json() == []
    with TestClient(create_app()) as c:
        base = f"/api/sessions/{sid}"
        page = c.get(base + "/runs", params={"limit": 1}).json()["data"]
        assert page["activeThreadId"] is None
        assert page["items"][0]["status"] == "COMPLETED"
        tid = page["items"][0]["threadId"]
        detail = c.get(base + "/runs/" + tid, params={"agentId": aid}).json()["data"]
        assert detail["result"]["finalAnswer"] == "East 总销售额为 200.00，West 为 50.00。"
        message = detail["result"]["messages"][0]
        message["metadata"]["messageKey"] = message.pop("messageKey")
        for _ in range(2):
            assert c.post(base + "/messages", json=message).status_code == 200
        assert len(c.get(base + "/messages").json()) == 1
        other = c.post("/api/agent", json={"name": "other"}).json()["id"]
        assert c.get(base + "/runs/" + tid, params={"agentId": other}).status_code == 404
        assert c.get(base + "/runs", params={"agentId": aid, "cursor": "!bad"}).status_code == 400
        state["mode"] = "provider_error"
        c.get("/api/stream/search", params={"agentId": aid, "conversationId": sid, "query": "失败"})
        page = c.get(base + "/runs", params={"agentId": aid, "limit": 1}).json()["data"]
        assert page["items"][0]["status"] == "FAILED" and page["nextCursor"]
        older = c.get(
            base + "/runs", params={"agentId": aid, "limit": 1, "cursor": page["nextCursor"]}
        ).json()["data"]
        assert older["items"][0]["threadId"] == tid
        failed = c.get(
            base + "/runs/" + page["items"][0]["threadId"], params={"agentId": aid}
        ).json()["data"]
        assert failed["result"]["outcome"] == "FAILED"


def test_authenticated_title_sse_heartbeat_and_agent_isolation():
    import socket
    import threading

    import httpx
    import uvicorn

    app = create_app()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", timeout_graceful_shutdown=1))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    import time

    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=8) as c:
            aid = c.post("/api/agent", json={"name": "SSE owner"}).json()["id"]
            sid = c.post(f"/api/agent/{aid}/sessions").json()["id"]
            other = c.post("/api/agent", json={"name": "other"}).json()["id"]
            other_sid = c.post(f"/api/agent/{other}/sessions").json()["id"]
            key = c.post(f"/api/agent/{aid}/api-key/generate").json()["data"]["apiKey"]
            c.put(f"/api/agent/{aid}/api-key/toggle", params={"enabled": True})
            assert c.get(f"/api/agent/{aid}/sessions/stream").status_code == 401
            with c.stream(
                "GET", f"/api/agent/{aid}/sessions/stream", headers={"X-API-Key": key}
            ) as response:
                lines = response.iter_lines()
                assert next(lines) == ": heartbeat"
                c.put(f"/api/sessions/{other_sid}/rename", params={"title": "foreign"})
                c.put(
                    f"/api/sessions/{sid}/rename",
                    params={"title": "owned"},
                    headers={"X-API-Key": key},
                )
                data = None
                for line in lines:
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        break
                assert data == {"type": "title-updated", "sessionId": sid, "title": "owned"}
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()


def test_nonterminal_result_hidden_and_cancelled_result_retained():
    import uuid

    from sqlalchemy import text

    app = create_app()
    with TestClient(app) as c:
        aid = c.post("/api/agent", json={"name": "cancel recovery"}).json()["id"]
        sid = c.post(f"/api/agent/{aid}/sessions").json()["id"]
        tid = str(uuid.uuid4())
        # Arrange persisted cancellation/checkpoint windows; assertions use only HTTP.
        with app.state.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO agent_run (thread_id,agent_id,conversation_id,request,"
                    "status) VALUES (:tid,:aid,:sid,'{}','CANCELLING')"
                ),
                {"tid": tid, "aid": aid, "sid": sid},
            )
            conn.execute(
                text(
                    "INSERT INTO agent_run_result (thread_id,result_version,outcome,"
                    "messages,reason) VALUES (:tid,1,'CANCELLED',:msgs,'user cancelled')"
                ),
                {
                    "tid": tid,
                    "msgs": json.dumps(
                        [
                            {
                                "messageKey": f"v1:{tid}:error:0",
                                "role": "assistant",
                                "content": "user cancelled",
                                "messageType": "error",
                                "metadata": {"threadId": tid, "resultVersion": 1},
                            }
                        ]
                    ),
                },
            )
        path = f"/api/sessions/{sid}/runs/{tid}"
        assert c.get(path).json()["data"]["result"] is None
        with app.state.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE agent_run SET status='CANCELLED',result_version=1 WHERE thread_id=:tid"
                ),
                {"tid": tid},
            )
        result = c.get(path).json()["data"]["result"]
        assert result["outcome"] == "CANCELLED" and result["finalAnswer"] is None
        assert result["messages"][0]["messageKey"] == f"v1:{tid}:error:0"
