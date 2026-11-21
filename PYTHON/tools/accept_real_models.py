"""Exercise the public HTTP contract with user-supplied provider credentials.

Never prints provider URLs, credentials, request payloads or upstream bodies.
"""

import argparse
from pathlib import Path

import httpx
from dotenv import dotenv_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--backend", default="http://127.0.0.1:8065")
    args = parser.parse_args()
    values = dotenv_values(args.source_env)
    definitions = [
        (
            "CHAT",
            "OPENAI_BASE_URL",
            "LLM_MODEL",
            "OPENAI_API_KEY",
            "completionsPath",
            "chat/completions",
        ),
        (
            "EMBEDDING",
            "EMBEDDING_BASE_URL",
            "EMBEDDING_MODEL",
            "EMBEDDING_API_KEY",
            "embeddingsPath",
            "embeddings",
        ),
    ]
    with httpx.Client(base_url=args.backend, timeout=180, trust_env=False) as client:
        for kind, base_key, model_key, secret_key, path_key, endpoint in definitions:
            base = values.get(base_key)
            model = values.get(model_key)
            secret = values.get(secret_key)
            if not base or not model or not secret:
                raise SystemExit(f"{kind}: source configuration incomplete")
            config = {
                "provider": "custom",
                "baseUrl": base.rstrip("/"),
                "modelName": model,
                "modelType": kind,
                "apiKey": secret,
                path_key: ("/" if base.rstrip("/").endswith("/v1") else "/v1/") + endpoint,
            }
            existing = client.get("/api/model-config/list").json()["data"]
            found = next(
                (m for m in existing if m["modelType"] == kind and m["modelName"] == model), None
            )
            if found:
                config["id"] = found["id"]
                result = client.put("/api/model-config/update", json=config).json()
            else:
                result = client.post("/api/model-config/add", json=config).json()
            if not result["success"]:
                raise SystemExit(f"{kind}: save failed")
            saved = next(
                m
                for m in client.get("/api/model-config/list").json()["data"]
                if m["modelType"] == kind and m["modelName"] == model
            )
            identifier = saved["id"]
            for action in ("test", "activate"):
                result = client.post(f"/api/model-config/{action}/{identifier}").json()
                if not result["success"]:
                    # Backend error is sanitized, but keep command output minimal.
                    raise SystemExit(f"{kind}: {action} failed: {result['message']}")
            print(f"{kind}: saved, provider call succeeded, activated")
        assert client.get("/api/model-config/check-ready").json()["data"]["ready"]
        print("Both model types ready")


if __name__ == "__main__":
    main()
