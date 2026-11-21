from fastapi.testclient import TestClient

from app.main import create_app


def test_agent_lifecycle_questions_and_restart():
    with TestClient(create_app()) as client:
        agent = client.post("/api/agent", json={"name": "Sales", "description": "Revenue"}).json()
        assert agent["status"] == "draft"
        identifier = agent["id"]
        path = f"/api/agent/{identifier}"
        assert client.post(path + "/publish").json()["status"] == "published"
        assert client.get("/api/agent/list?status=published").json()[0]["id"] == identifier
        assert client.put(path, json={"name": "Updated"}).json()["description"] == "Revenue"
        assert (
            client.post(path + "/preset-questions", json=[{"question": "Total sales?"}]).status_code
            == 200
        )
    with TestClient(create_app()) as client:
        assert client.get(path).json()["name"] == "Updated"
        questions = client.get(path + "/preset-questions").json()
        assert questions[0]["isActive"] is True
        assert questions[0]["question"] == "Total sales?"
        assert client.delete(path + f"/preset-questions/{questions[0]['id']}").status_code == 200
        assert client.get(path + "/preset-questions").json() == []
        assert client.post(path + "/offline").json()["status"] == "offline"
        assert client.get("/api/agent/999999").status_code == 404


def test_api_key_rotation_masking_and_header_precedence():
    with TestClient(create_app()) as client:
        agent = client.post("/api/agent", json={"name": "Protected"}).json()
        path = f"/api/agent/{agent['id']}"
        assert client.get(path + "/access").status_code == 200
        key = client.post(path + "/api-key/generate").json()["data"]["apiKey"]
        assert key.startswith("sk-")
        for url in [path, "/api/agent/list", path + "/api-key"]:
            assert key not in client.get(url).text
        assert client.get(path + "/access").status_code == 401
        assert (
            client.get(path + "/access", headers={"Authorization": f"Bearer {key}"}).status_code
            == 200
        )
        assert (
            client.get(
                path + "/access", headers={"X-API-Key": "wrong", "Authorization": f"Bearer {key}"}
            ).status_code
            == 401
        )
        new_key = client.post(path + "/api-key/reset").json()["data"]["apiKey"]
        assert new_key != key
        assert client.get(path + "/access", headers={"X-API-Key": key}).status_code == 401
        assert client.get(path + "/access", headers={"X-API-Key": new_key}).status_code == 200
        assert client.post(path + "/api-key/enable?enabled=false").json()["success"]
        assert client.get(path + "/access").status_code == 200
        assert client.delete(path + "/api-key").json()["data"]["apiKey"] is None
        assert not client.post(path + "/api-key/enable?enabled=true").json()["success"]
