from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_service_starts_without_java():
    with TestClient(create_app()) as client:
        response = client.get("/echo/ok")
        assert response.status_code == 200
        assert response.text == "ok"


def test_saved_model_survives_application_restart():
    config = {
        "provider": "custom",
        "baseUrl": "http://localhost:9999",
        "modelName": "ticket01-restart",
        "modelType": "CHAT",
        "apiKey": "secret-key",
    }
    with TestClient(create_app()) as client:
        assert client.post("/api/model-config/add", json=config).json()["success"]
    with TestClient(create_app()) as client:
        models = client.get("/api/model-config/list").json()["data"]
        saved = next(m for m in models if m["modelName"] == config["modelName"])
        assert saved["isActive"] is False
        assert "secret-key" not in str(saved)
        assert client.delete(f"/api/model-config/{saved['id']}").json()["success"]


@pytest.mark.parametrize("kind,path", [("CHAT", None), ("EMBEDDING", "/custom/embed")])
def test_model_management_and_provider_calls(model_server, kind, path):
    with TestClient(create_app()) as client:
        config = {
            "provider": "custom",
            "baseUrl": model_server,
            "modelName": f"fixture-{kind}",
            "modelType": kind,
            "apiKey": "fixture-key",
            "embeddingsPath": path,
        }
        assert client.post("/api/model-config/add", json=config).json()["success"]
        saved = next(
            m
            for m in client.get("/api/model-config/list").json()["data"]
            if m["modelName"] == config["modelName"]
        )
        identifier = saved["id"]
        assert client.post(f"/api/model-config/test/{identifier}").json()["success"]
        saved["maxTokens"] = 128
        assert client.put("/api/model-config/update", json=saved).json()["success"]
        # The masked key in the edit form must preserve the usable original key.
        assert client.post(f"/api/model-config/test/{identifier}").json()["success"]
        assert client.post(f"/api/model-config/activate/{identifier}").json()["success"]
        assert client.get("/api/model-config/check-ready").json()["data"][
            "chatModelReady" if kind == "CHAT" else "embeddingModelReady"
        ]
        assert not client.delete(f"/api/model-config/{identifier}").json()["success"]
        saved["modelType"] = "EMBEDDING" if kind == "CHAT" else "CHAT"
        assert not client.put("/api/model-config/update", json=saved).json()["success"]
    with TestClient(create_app()) as restarted:
        persisted = next(
            m
            for m in restarted.get("/api/model-config/list").json()["data"]
            if m["id"] == identifier
        )
        assert persisted["isActive"] is True
        assert persisted["maxTokens"] == 128
        assert persisted["modelType"] == kind
        assert restarted.post(f"/api/model-config/test/{identifier}").json()["success"]


def test_provider_errors_are_visible_without_secrets(model_server):
    with TestClient(create_app()) as client:
        config = {
            "provider": "custom",
            "baseUrl": model_server,
            "modelName": "bad-key",
            "modelType": "CHAT",
            "apiKey": "invalid-secret",
        }
        client.post("/api/model-config/add", json=config)
        saved = client.get("/api/model-config/list").json()["data"][0]
        error = client.post(f"/api/model-config/test/{saved['id']}").json()
        assert not error["success"]
        assert "401" in error["message"]
        assert "secret" not in str(error) and "fixture-key" not in str(error)
        saved.update(apiKey="fixture-key", modelName="empty-output")
        assert client.put("/api/model-config/update", json=saved).json()["success"]
        assert not client.post(f"/api/model-config/test/{saved['id']}").json()["success"]


def test_invalid_config_uses_compatible_error_envelope():
    with TestClient(create_app()) as client:
        result = client.post("/api/model-config/add", json={"apiKey": "private"})
        assert result.status_code == 400
        assert result.json()["success"] is False
        assert "private" not in result.text
        assert "detail" not in result.json()
        assert not client.post("/api/model-config/activate/999999").json()["success"]


def test_url_with_empty_username_cannot_expose_embedded_password():
    with TestClient(create_app()) as client:
        result = client.post(
            "/api/model-config/add",
            json={
                "provider": "custom",
                "modelType": "CHAT",
                "modelName": "credential-url",
                "baseUrl": "http://:embedded-private-key@localhost:9999",
            },
        )
        assert result.status_code == 400
        assert "embedded-private-key" not in result.text
        assert "embedded-private-key" not in client.get("/api/model-config/list").text


def test_embedding_space_changes_require_reindexing(model_server):
    with TestClient(create_app()) as client:
        config = {
            "provider": "custom",
            "baseUrl": model_server,
            "modelType": "EMBEDDING",
            "modelName": "original-space",
            "apiKey": "fixture-key",
            "embeddingsPath": "/custom/embed",
        }
        assert client.post("/api/model-config/add", json=config).json()["success"]
        current = client.get("/api/model-config/list").json()["data"][0]
        assert client.post(f"/api/model-config/activate/{current['id']}").json()["success"]
        config["modelName"] = "different-space"
        client.post("/api/model-config/add", json=config)
        target = client.get("/api/model-config/list").json()["data"][0]
        assert not client.post(f"/api/model-config/activate/{target['id']}").json()["success"]
        current["modelName"] = "different-space"
        assert not client.put("/api/model-config/update", json=current).json()["success"]
        persisted = next(
            m for m in client.get("/api/model-config/list").json()["data"] if m["isActive"]
        )
        assert persisted["modelName"] == "original-space"
        assert client.post(f"/api/model-config/test/{persisted['id']}").json()["success"]


def test_embedding_probe_checks_configured_vector_dimension(model_server):
    with TestClient(create_app(Settings(embedding_dimension=4))) as client:
        client.post(
            "/api/model-config/add",
            json={
                "provider": "custom",
                "baseUrl": model_server,
                "modelType": "EMBEDDING",
                "modelName": "dimension-test",
                "apiKey": "fixture-key",
                "embeddingsPath": "/custom/embed",
            },
        )
        identifier = client.get("/api/model-config/list").json()["data"][0]["id"]
        assert not client.post(f"/api/model-config/test/{identifier}").json()["success"]


def test_concurrent_activation_keeps_only_one_active_model():
    with TestClient(create_app()) as client:
        identifiers = []
        for index in range(2):
            config = {
                "provider": "custom",
                "baseUrl": "http://localhost:9999",
                "modelName": f"concurrent-{index}",
                "modelType": "CHAT",
            }
            assert client.post("/api/model-config/add", json=config).json()["success"]
            identifiers.append(client.get("/api/model-config/list").json()["data"][0]["id"])
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda identifier: client.post(
                        f"/api/model-config/activate/{identifier}"
                    ).json(),
                    identifiers,
                )
            )
        assert all(result["success"] for result in results)
        active = [
            m
            for m in client.get("/api/model-config/list").json()["data"]
            if m["modelType"] == "CHAT" and m["isActive"]
        ]
        assert len(active) == 1
        inactive = next(identifier for identifier in identifiers if identifier != active[0]["id"])
        assert client.delete(f"/api/model-config/{inactive}").json()["success"]
        assert not client.post(f"/api/model-config/test/{inactive}").json()["success"]
