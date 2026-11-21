"""HTTP tests for session creation and listing (Ticket 03)."""

from fastapi.testclient import TestClient

from app.main import create_app


def _create_agent(client: TestClient, name: str = "Session Agent") -> int:
    created = client.post("/api/agent", json={"name": name, "status": "published"})
    assert created.status_code == 200
    return created.json()["id"]


def test_create_list_sessions_and_restart_persistence():
    with TestClient(create_app()) as client:
        missing = client.get("/api/agent/999999/sessions")
        assert missing.status_code == 404
        missing_create = client.post("/api/agent/999999/sessions", json={"title": "x"})
        assert missing_create.status_code == 404

        agent_a = _create_agent(client, "Agent A")
        agent_b = _create_agent(client, "Agent B")

        assert client.get(f"/api/agent/{agent_a}/sessions").json() == []

        first = client.post(f"/api/agent/{agent_a}/sessions", json={"title": "销售分析"})
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["agentId"] == agent_a
        assert first_body["title"] == "销售分析"
        assert first_body["status"] == "active"
        assert first_body["isPinned"] is False
        assert isinstance(first_body["id"], str) and len(first_body["id"]) == 36

        second = client.post(f"/api/agent/{agent_a}/sessions")
        assert second.status_code == 200
        second_body = second.json()
        assert second_body["title"] == "新会话"
        assert second_body["id"] != first_body["id"]

        other = client.post(f"/api/agent/{agent_b}/sessions", json={"title": "B 会话"})
        assert other.status_code == 200

    with TestClient(create_app()) as restarted:
        listed = restarted.get(f"/api/agent/{agent_a}/sessions")
        assert listed.status_code == 200
        ids = [item["id"] for item in listed.json()]
        assert set(ids) == {first_body["id"], second_body["id"]}
        assert other.json()["id"] not in ids
