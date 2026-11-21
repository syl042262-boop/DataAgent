"""Remaining legacy contracts, verified by public round trips and real MySQL."""

from fastapi.testclient import TestClient
from test_knowledge_http import activate_embedding
from test_stream_query_http import _setup_agent_and_model

from app.main import create_app

pytest_plugins = ["test_stream_query_http"]


def test_knowledge_edit_list_and_individual_semantic_delete(model_server, business_mysql_db):
    with TestClient(create_app()) as client:
        aid, _, _ = _setup_agent_and_model(client, model_server, business_mysql_db)
        activate_embedding(client, model_server)
        business = client.post(
            "/api/business-knowledge",
            json={
                "agentId": aid,
                "businessTerm": "Paid revenue",
                "description": "Exclude refunds",
            },
        ).json()["data"]
        listed = client.get(
            "/api/business-knowledge", params={"agentId": aid, "keyword": "Paid"}
        ).json()
        assert listed["success"] and len(listed["data"]) == 1
        assert listed["data"][0]["id"] == business["id"]
        document = client.post(
            "/api/agent-knowledge/create",
            data={
                "agentId": aid,
                "title": "Old policy",
                "type": "QA",
                "question": "Revenue?",
                "content": "Old policy",
            },
        ).json()["data"]
        updated = client.put(
            "/api/agent-knowledge/" + str(document["id"]),
            json={
                "title": "Current policy",
                "content": "Paid revenue excludes refunds",
            },
        ).json()["data"]
        assert updated["title"] == "Current policy"
        assert updated["contentRevision"] == 2
        assert updated["embeddingStatus"] == "COMPLETED"
        assert client.post(
            "/api/semantic-model",
            json={
                "agentId": aid,
                "tableName": "sales",
                "columnName": "amount",
                "businessName": "Revenue",
                "dataType": "decimal",
            },
        ).json()["success"]
        semantic = client.get("/api/semantic-model", params={"agentId": aid}).json()["data"][0]
        assert client.delete("/api/semantic-model/" + str(semantic["id"])).json()["data"] is True
        assert client.get("/api/semantic-model/" + str(semantic["id"])).json()["data"] is None
    with TestClient(create_app()) as client:
        saved = client.get("/api/agent-knowledge/" + str(document["id"])).json()["data"]
        assert (
            saved["title"] == "Current policy"
            and saved["content"] == "Paid revenue excludes refunds"
        )
        assert client.get("/api/semantic-model", params={"agentId": aid}).json()["data"] == []


def test_prompt_list_and_type_filter_preserve_saved_configuration():
    with TestClient(create_app()) as client:
        aid = client.post("/api/agent", json={"name": "Prompt owner"}).json()["id"]
        other = client.post("/api/agent", json={"name": "Other owner"}).json()["id"]
        for name, owner, kind, priority in [
            ("Owner SQL", aid, "sql-generator", 20),
            ("Other SQL", other, "sql-generator", 10),
            ("Global rewrite", None, "rewrite", 5),
        ]:
            assert client.post(
                "/api/prompt-config/save",
                json={
                    "name": name,
                    "agentId": owner,
                    "promptType": kind,
                    "optimizationPrompt": "仅依据已选择的数据表回答。",
                    "priority": priority,
                },
            ).json()["success"]
        listed = client.get("/api/prompt-config/list").json()
        assert listed["total"] == 3
        assert [item["name"] for item in listed["data"]] == [
            "Owner SQL",
            "Other SQL",
            "Global rewrite",
        ]
        filtered = client.get(
            "/api/prompt-config/list-by-type/sql-generator", params={"agentId": aid}
        ).json()
        assert filtered["total"] == 1 and filtered["data"][0]["name"] == "Owner SQL"
    with TestClient(create_app()) as client:
        assert client.get("/api/prompt-config/list").json()["total"] == 3


def test_clearing_idle_sessions_deletes_all_messages_and_allows_a_new_session():
    with TestClient(create_app()) as client:
        aid = client.post("/api/agent", json={"name": "Clear history"}).json()["id"]
        sessions = [
            client.post(f"/api/agent/{aid}/sessions", json={}).json()["id"] for _ in range(2)
        ]
        for sid in sessions:
            assert (
                client.post(
                    f"/api/sessions/{sid}/messages",
                    json={
                        "role": "user",
                        "content": "Historical question",
                    },
                ).status_code
                == 200
            )
        cleared = client.delete(f"/api/agent/{aid}/sessions").json()
        assert cleared["success"]
        assert client.get(f"/api/agent/{aid}/sessions").json() == []
        for sid in sessions:
            assert client.get(f"/api/sessions/{sid}/messages").status_code == 404
            assert (
                client.post(
                    f"/api/sessions/{sid}/messages",
                    json={
                        "role": "assistant",
                        "content": "late",
                    },
                ).status_code
                == 404
            )
        new = client.post(f"/api/agent/{aid}/sessions", json={}).json()["id"]
        assert new not in sessions
    with TestClient(create_app()) as client:
        assert [item["id"] for item in client.get(f"/api/agent/{aid}/sessions").json()] == [new]
