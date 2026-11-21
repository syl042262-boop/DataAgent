"""External vector indexes. MySQL-provided record revisions filter before ranking."""

import hashlib
import json
import re

import httpx


class IndexIncompleteError(ValueError):
    def __init__(self, missing):
        super().__init__("External vector index incomplete; rebuild embedding")
        self.missing = missing


class ExternalIndex:
    def __init__(self, backend, url, namespace, token=None):
        if backend not in {"elasticsearch", "milvus"}:
            raise ValueError("Unsupported external vector backend")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", namespace):
            raise ValueError("Invalid vector namespace")
        self.backend = backend
        self.url = url.rstrip("/")
        self.namespace = namespace
        self.headers = {"Authorization": "Bearer " + token} if token else {}

    def name(self, space, dimension):
        digest = hashlib.sha256(space.encode()).hexdigest()[:24]
        return f"{self.namespace}_{digest}_{dimension}"

    def request(self, method, path, payload=None, missing=False):
        try:
            response = httpx.request(
                method, self.url + path, json=payload, headers=self.headers, timeout=30
            )
            if missing and response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            if self.backend == "elasticsearch" and (
                data.get("failures")
                or data.get("timed_out")
                or data.get("_shards", {}).get("failed", 0)
            ):
                raise ValueError("External vector operation incomplete; retry embedding")
            if self.backend == "milvus" and data.get("code", 0) != 0:
                raise ValueError("External vector operation failed; retry embedding")
            return data
        except (httpx.HTTPError, json.JSONDecodeError):
            raise ValueError("External vector service unavailable; retry embedding") from None

    def milvus(self, operation, name, **payload):
        return self.request(
            "POST", "/v2/vectordb/" + operation, {"collectionName": name, **payload}
        )

    def exists(self, name):
        if self.backend == "milvus":
            return self.milvus("collections/has", name)["data"]["has"]
        return self.request("GET", "/" + name, missing=True) is not None

    def ensure(self, name, dimension):
        if self.exists(name):
            return
        if self.backend == "milvus":
            self.milvus(
                "collections/create",
                name,
                dimension=dimension,
                metricType="COSINE",
                idType="VarChar",
                autoID=False,
                params={"max_length": 64, "enableDynamicField": True, "consistencyLevel": "Strong"},
            )
        else:
            self.request(
                "PUT",
                "/" + name,
                {
                    "mappings": {
                        "properties": {
                            "vector": {"type": "dense_vector", "dims": dimension, "index": False},
                            "agent_id": {"type": "long"},
                            "record_key": {"type": "keyword"},
                            "kind": {"type": "keyword"},
                            "record_id": {"type": "long"},
                            "revision": {"type": "long"},
                            "content": {"type": "text", "index": False},
                        }
                    }
                },
            )

    def replace(self, kind, identifier, agent_id, revision, space, chunks):
        dimension = len(chunks[0][1])
        name = self.name(space, dimension)
        self.ensure(name, dimension)
        self.delete(kind, identifier, space, dimension)
        rows = []
        for position, (content, vector) in enumerate(chunks):
            key = f"{kind}:{identifier}:{revision}"
            rows.append(
                {
                    "id": hashlib.sha256(f"{key}:{position}".encode()).hexdigest(),
                    "kind": kind,
                    "record_id": identifier,
                    "agent_id": agent_id,
                    "revision": revision,
                    "record_key": key,
                    "content": content,
                    "vector": vector,
                }
            )
        if self.backend == "milvus":
            self.milvus("entities/insert", name, data=rows)
        else:
            for row in rows:
                self.request("PUT", f"/{name}/_doc/{row['id']}?refresh=true", row)

    def search(
        self, agent_id, space, vector, allowed, limit, *, verify=False, expected_counts=None
    ):
        if not allowed:
            return []
        name = self.name(space, len(vector))
        if not self.exists(name):
            raise IndexIncompleteError(allowed)
        keys = [f"{kind}:{identifier}:{revision}" for kind, identifier, revision in allowed]
        # Collection existence alone cannot prove publication survived remote
        # data loss. Validate authoritative revisions before returning any hits.
        if verify:
            present: dict[str, int] = {}
            for offset in range(0, len(keys), 1000):
                batch = keys[offset : offset + 1000]
                if self.backend == "elasticsearch":
                    coverage = self.request(
                        "POST",
                        f"/{name}/_search",
                        {
                            "size": 0,
                            "query": {
                                "bool": {
                                    "filter": [
                                        {"term": {"agent_id": agent_id}},
                                        {"terms": {"record_key": batch}},
                                    ]
                                }
                            },
                            "aggs": {
                                "records": {"terms": {"field": "record_key", "size": len(batch)}}
                            },
                        },
                    )
                    present.update(
                        (item["key"], item["doc_count"])
                        for item in coverage["aggregations"]["records"]["buckets"]
                    )
                else:
                    # Querying one scalar match per revision avoids a chunk limit
                    # silently hiding records with large documents.
                    for key in batch:
                        coverage = self.milvus(
                            "entities/query",
                            name,
                            filter=f"agent_id == {int(agent_id)} and record_key == {json.dumps(key)}",
                            outputFields=["count(*)"],
                            consistencyLevel="Strong",
                        )
                        if coverage["data"]:
                            present[key] = coverage["data"][0]["count(*)"]
            missing = [
                item
                for item, key in zip(allowed, keys)
                if not present.get(key)
                or (expected_counts is not None and present.get(key) != expected_counts.get(item))
            ]
            if missing:
                raise IndexIncompleteError(missing)
        if self.backend == "milvus":
            result = self.milvus(
                "entities/search",
                name,
                data=[vector],
                limit=limit,
                filter=f"agent_id == {int(agent_id)} and record_key in {json.dumps(keys)}",
                outputFields=["kind", "record_id", "revision", "content"],
                consistencyLevel="Strong",
                searchParams={"metricType": "COSINE"},
            )
            return [{**row, "score": row["distance"]} for row in result["data"]]
        result = self.request(
            "POST",
            f"/{name}/_search",
            {
                "size": limit,
                "query": {
                    "script_score": {
                        "query": {
                            "bool": {
                                "filter": [
                                    {"term": {"agent_id": agent_id}},
                                    {"terms": {"record_key": keys}},
                                ]
                            }
                        },
                        "script": {
                            "source": "cosineSimilarity(params.q, 'vector') + 1.0",
                            "params": {"q": vector},
                        },
                    }
                },
            },
        )
        return [{**hit["_source"], "score": hit["_score"] - 1} for hit in result["hits"]["hits"]]

    def delete(self, kind, identifier, space, dimension):
        name = self.name(space, dimension)
        if not self.exists(name):
            return
        if self.backend == "milvus":
            self.milvus(
                "entities/delete",
                name,
                filter=f"kind == {json.dumps(kind)} and record_id == {int(identifier)}",
            )
        else:
            self.request(
                "POST",
                f"/{name}/_delete_by_query?refresh=true",
                {
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"kind": kind}},
                                {"term": {"record_id": identifier}},
                            ]
                        }
                    }
                },
            )

    def drop(self, space, dimension):
        name = self.name(space, dimension)
        if not self.exists(name):
            return
        if self.backend == "milvus":
            self.milvus("collections/drop", name)
        else:
            self.request("DELETE", "/" + name)


def create_external_index(backend, url, namespace, token=None):
    return ExternalIndex(backend, url, namespace, token)
