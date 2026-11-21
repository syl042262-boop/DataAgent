"""Real external services at the agreed vector adapter boundary."""

import uuid

import pytest

from app.external_vectors import create_external_index

pytest_plugins = ["test_stream_query_http"]


@pytest.mark.parametrize(
    "backend,url",
    [
        ("elasticsearch", "http://127.0.0.1:19200"),
        ("milvus", "http://127.0.0.1:19531"),
    ],
)
def test_external_vectors_filter_replace_delete_and_survive_new_client(backend, url):
    namespace = "test_" + uuid.uuid4().hex
    index = create_external_index(backend, url, namespace)
    allowed = [("business", 11, 1), ("semantic", 12, 1), ("document", 13, 1)]
    try:
        for kind, identifier, revision in allowed:
            index.replace(
                kind, identifier, 7, revision, "space1", [("original-" + kind, [1.0, 0.0, 0.0])]
            )
        index.replace("business", 20, 8, 1, "space1", [("other agent", [1.0, 0.0, 0.0])])
        restarted = create_external_index(backend, url, namespace)
        hits = restarted.search(7, "space1", [1.0, 0.0, 0.0], allowed, 10)
        assert {h["content"] for h in hits} == {
            "original-business",
            "original-semantic",
            "original-document",
        }
        assert all(abs(h["score"] - 1) < 0.001 for h in hits)
        restarted.replace("business", 11, 7, 2, "space1", [("updated", [1.0, 0.0, 0.0])])
        hits = restarted.search(7, "space1", [1.0, 0.0, 0.0], allowed, 10)
        assert all(h["content"] != "original-business" for h in hits)
        allowed[0] = ("business", 11, 2)
        assert "updated" in {
            h["content"] for h in restarted.search(7, "space1", [1.0, 0.0, 0.0], allowed, 10)
        }
        restarted.delete("business", 11, "space1", 3)
        assert all(
            h["kind"] != "business"
            for h in restarted.search(7, "space1", [1.0, 0.0, 0.0], allowed, 10)
        )
    finally:
        index.drop("space1", 3)


@pytest.mark.parametrize(
    "backend,url",
    [
        ("elasticsearch", "http://127.0.0.1:19200"),
        ("milvus", "http://127.0.0.1:19531"),
    ],
)
def test_external_knowledge_http_restart_rebuild_and_failure(
    backend, url, model_server, business_mysql_db
):
    from fastapi.testclient import TestClient
    from test_knowledge_http import activate_embedding
    from test_stream_query_http import _setup_agent_and_model

    from app.config import Settings
    from app.main import create_app

    settings = Settings(
        vector_backend=backend, vector_url=url, vector_namespace="http_" + uuid.uuid4().hex
    )
    with TestClient(create_app(settings)) as client:
        aid, _, _ = _setup_agent_and_model(client, model_server, business_mysql_db)
        activate_embedding(client, model_server)
        business = client.post(
            "/api/business-knowledge",
            json={"agentId": aid, "businessTerm": "Revenue", "description": "Paid sales"},
        ).json()["data"]
        assert business["embeddingStatus"] == "COMPLETED", business
        client.post(
            "/api/semantic-model",
            json={
                "agentId": aid,
                "tableName": "sales",
                "columnName": "amount",
                "businessName": "Revenue",
                "dataType": "decimal",
            },
        )
        document = client.post(
            "/api/agent-knowledge/create",
            data={"agentId": aid, "title": "Policy", "type": "DOCUMENT"},
            files={"file": ("policy.txt", b"Paid revenue excludes refunds.")},
        ).json()["data"]
        assert document["embeddingStatus"] == "COMPLETED", document
        semantic = client.get("/api/semantic-model", params={"agentId": aid}).json()["data"][0]

        def search():
            return client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "revenue"})

        assert {h["kind"] for h in search().json()["data"]} == {"business", "semantic", "document"}
    # Re-open the service against the same management DB and data directory.
    with TestClient(create_app(settings)) as client:
        assert len(search().json()["data"]) == 3
        index = create_external_index(backend, url, settings.vector_namespace)
        try:
            # The published destination is visible to review/config guards.
            effective = client.get(f"/api/agent/{aid}/effective-config").json()["data"]
            assert effective["config"]["vectorStorage"]["backend"] == backend
            # Lost remote collection must be visible; local cache cannot hide it.
            index.drop(business["embeddingSpace"], 3)
            assert search().json()["success"] is False
            for kind, identifier, path in [
                ("business", business["id"], "/api/business-knowledge/"),
                ("document", document["id"], "/api/agent-knowledge/"),
                ("semantic", semantic["id"], "/api/semantic-model/"),
            ]:
                assert (
                    client.get(path + str(identifier)).json()["data"]["embeddingStatus"] == "FAILED"
                )
            client.post("/api/business-knowledge/retry-embedding/" + str(business["id"]))
            # Remaining lost revisions stay visibly FAILED after partial rebuild.
            assert (
                client.get("/api/agent-knowledge/" + str(document["id"])).json()["data"][
                    "embeddingStatus"
                ]
                == "FAILED"
            )
            client.post("/api/agent-knowledge/retry-embedding/" + str(document["id"]))
            client.put("/api/semantic-model/" + str(semantic["id"]), json=semantic)
            assert {h["kind"] for h in search().json()["data"]} == {
                "business",
                "semantic",
                "document",
            }
            client.delete("/api/business-knowledge/" + str(business["id"]))
            assert {h["kind"] for h in search().json()["data"]} == {"semantic", "document"}
        finally:
            index.drop(business["embeddingSpace"], 3)


@pytest.mark.parametrize(
    "backend,url",
    [
        ("elasticsearch", "http://127.0.0.1:19200"),
        ("milvus", "http://127.0.0.1:19531"),
    ],
)
def test_external_index_detects_incomplete_document(backend, url):
    from app.external_vectors import IndexIncompleteError

    index = create_external_index(backend, url, "partial_" + uuid.uuid4().hex)
    try:
        index.replace("document", 1, 7, 1, "space", [("first", [1.0, 0.0, 0.0])])
        with pytest.raises(IndexIncompleteError):
            index.search(
                7,
                "space",
                [1.0, 0.0, 0.0],
                [("document", 1, 1)],
                10,
                verify=True,
                expected_counts={("document", 1, 1): 2},
            )
    finally:
        index.drop("space", 3)
