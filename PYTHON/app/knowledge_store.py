"""Versioned knowledge ownership and a local, restart-safe SQLite vector index.

MySQL is authoritative. Index hits are usable only when their published revision
and embedding space match the current record. A crash during publication cannot
make stale content searchable. Single-worker record operations share a lock.
"""

import hashlib
import json
import math
import sqlite3
import threading
from typing import Any

from sqlalchemy import text

from app.agents import camel_row, require_agent
from app.external_vectors import IndexIncompleteError, create_external_index
from app.model_config import _post_model_json, as_dto, snake

TABLES = {
    "business": "business_knowledge",
    "semantic": "semantic_model",
    "document": "agent_knowledge",
}
FIELDS = {
    "business": {"businessTerm", "description", "synonyms", "isRecall"},
    "semantic": {
        "tableName",
        "columnName",
        "businessName",
        "synonyms",
        "businessDescription",
        "columnComment",
        "dataType",
        "createdTime",
        "status",
    },
    "document": {
        "title",
        "type",
        "question",
        "content",
        "isRecall",
        "splitterType",
        "sourceFilename",
        "filePath",
        "fileSize",
        "fileType",
    },
}


def embedding_config(engine):
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT * FROM model_config WHERE model_type='EMBEDDING' "
                    "AND is_active=1 AND is_deleted=0 LIMIT 1"
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise ValueError("No active EMBEDDING model")
    return as_dto(row)


def embedding_space(config, settings=None):
    storage = (
        []
        if settings is None or settings.vector_backend == "local"
        else [settings.vector_backend, settings.vector_url.rstrip("/"), settings.vector_namespace]
    )
    return hashlib.sha256(
        json.dumps(
            [config.provider, config.baseUrl, config.modelName, config.embeddingsPath] + storage
        ).encode()
    ).hexdigest()


def embed(config, content, timeout, dimension=0):
    result = _post_model_json(
        config,
        config.embeddingsPath or "/v1/embeddings",
        {"model": config.modelName, "input": content, "encoding_format": "float"},
        timeout,
    )
    try:
        vector = result["data"][0]["embedding"]
        if (
            not isinstance(vector, list)
            or not vector
            or any(
                not isinstance(v, (float, int)) or isinstance(v, bool) or not math.isfinite(v)
                for v in vector
            )
            or not any(vector)
            or (dimension and len(vector) != dimension)
        ):
            raise ValueError("Invalid embedding vector or dimension")
        return vector
    except (KeyError, IndexError, TypeError):
        raise ValueError("Invalid embedding response") from None


def cosine(left, right):
    if len(left) != len(right):
        raise ValueError("Embedding dimension changed; rebuild the index")
    return sum(a * b for a, b in zip(left, right)) / (
        math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    )


class KnowledgeStore:
    def __init__(self, engine, settings):
        self.engine = engine
        self.settings = settings
        self.lock = threading.RLock()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = settings.data_dir / "knowledge.sqlite"
        self.external = (
            create_external_index(
                settings.vector_backend,
                settings.vector_url,
                settings.vector_namespace,
                settings.vector_token,
            )
            if settings.vector_backend != "local"
            else None
        )
        with self.index() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS chunks (kind TEXT, record_id INTEGER, "
                "agent_id INTEGER, revision INTEGER, space TEXT, chunk_id INTEGER, "
                "content TEXT, vector TEXT, PRIMARY KEY(kind,record_id,space,chunk_id))"
            )
            columns = list(db.execute("PRAGMA table_info(chunks)"))
            if not next(column[5] for column in columns if column[1] == "space"):
                db.execute("ALTER TABLE chunks RENAME TO chunks_legacy")
                db.execute(
                    "CREATE TABLE chunks (kind TEXT, record_id INTEGER, agent_id INTEGER, "
                    "revision INTEGER, space TEXT, chunk_id INTEGER, content TEXT, vector TEXT, "
                    "PRIMARY KEY(kind,record_id,space,chunk_id))"
                )
                db.execute("INSERT INTO chunks SELECT * FROM chunks_legacy")
                db.execute("DROP TABLE chunks_legacy")
            # Persist destinations before remote publication, so failed writes and
            # backend changes can be cleaned without retaining credentials.
            db.execute(
                "CREATE TABLE IF NOT EXISTS external_targets ("
                "kind TEXT, record_id INTEGER, agent_id INTEGER, backend TEXT, "
                "url TEXT, namespace TEXT, space TEXT, dimension INTEGER, "
                "PRIMARY KEY(kind,record_id,backend,url,namespace,space,dimension))"
            )
        # Interrupted builds never silently become searchable after restart.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE python_knowledge_state SET embedding_status='FAILED', "
                    "error_msg='Index build interrupted; retry embedding' "
                    "WHERE embedding_status IN ('PENDING','PROCESSING')"
                )
            )
            for table in ("business_knowledge", "agent_knowledge"):
                conn.execute(
                    text(
                        f"UPDATE {table} SET embedding_status='FAILED', "
                        "error_msg='Index build interrupted; retry embedding' "
                        "WHERE embedding_status IN ('PENDING','PROCESSING')"
                    )
                )

    def index(self):
        return sqlite3.connect(self.index_path, timeout=30)

    def delete_external(self, kind, identifier):
        with self.index() as db:
            targets = db.execute(
                "SELECT backend,url,namespace,space,dimension FROM external_targets "
                "WHERE kind=? AND record_id=?",
                (kind, identifier),
            ).fetchall()
        for backend, url, namespace, space, dimension in targets:
            same_destination = (
                backend == self.settings.vector_backend
                and url.rstrip("/") == self.settings.vector_url.rstrip("/")
                and namespace == self.settings.vector_namespace
            )
            token = self.settings.vector_token if same_destination else None
            index = create_external_index(backend, url, namespace, token)
            index.delete(kind, identifier, space, dimension)
            with self.index() as db:
                db.execute(
                    "DELETE FROM external_targets WHERE kind=? AND record_id=? AND "
                    "backend=? AND url=? AND namespace=? AND space=? AND dimension=?",
                    (kind, identifier, backend, url, namespace, space, dimension),
                )

    def delete_agent_vectors(self, agent_id):
        with self.index() as db:
            targets = db.execute(
                "SELECT DISTINCT kind,record_id FROM external_targets WHERE agent_id=?", (agent_id,)
            ).fetchall()
        for kind, identifier in targets:
            self.delete_external(kind, identifier)

    def get(self, kind, identifier, conn=None):
        if conn is None:
            with self.engine.connect() as connection:
                return self.get(kind, identifier, connection)
        deleted = "" if kind == "semantic" else " AND is_deleted=0"
        row = (
            conn.execute(
                text(f"SELECT * FROM {TABLES[kind]} WHERE id=:id{deleted}"), {"id": identifier}
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ValueError("Knowledge record not found")
        result = camel_row(row)
        for key in ("createdTime", "updatedTime"):
            if result.get(key) is not None:
                result[key] = result[key].strftime("%Y-%m-%d %H:%M:%S")
        if kind == "semantic":
            result["updateTime"] = result.pop("updatedTime")
        if kind != "semantic":
            result["isRecall"] = bool(result["isRecall"])
        if kind == "document":
            result["fileUrl"] = (
                "/api/upload/files/" + result["filePath"] if result.get("filePath") else None
            )
        state = (
            conn.execute(
                text("SELECT * FROM python_knowledge_state WHERE kind=:kind AND record_id=:id"),
                {"kind": kind, "id": identifier},
            )
            .mappings()
            .first()
        )
        if state:
            result.update(
                contentRevision=state["revision"],
                indexRevision=state["index_revision"],
                embeddingStatus=state["embedding_status"],
                errorMsg=state["error_msg"],
                embeddingSpace=state["embedding_space"],
            )
        return result

    def list(self, kind, agent_id=None, keyword=None):
        with self.engine.connect() as conn:
            where = ["1=1"] if kind == "semantic" else ["is_deleted=0"]
            params: dict[str, Any] = {}
            if agent_id is not None:
                require_agent(conn, agent_id)
                where.append("agent_id=:aid")
                params["aid"] = agent_id
            if keyword:
                cols = {
                    "business": ("business_term", "description", "synonyms"),
                    "semantic": ("business_name", "table_name", "column_name"),
                    "document": ("title",),
                }[kind]
                where.append("(" + " OR ".join(f"{col} LIKE :keyword" for col in cols) + ")")
                params["keyword"] = "%" + keyword + "%"
            ids = (
                conn.execute(
                    text(
                        f"SELECT id FROM {TABLES[kind]} WHERE "
                        + " AND ".join(where)
                        + " ORDER BY id DESC"
                    ),
                    params,
                )
                .scalars()
                .all()
            )
            return [self.get(kind, identifier, conn) for identifier in ids]

    def save(self, kind, payload, identifier=None):
        with self.lock:
            with self.engine.begin() as conn:
                if identifier is not None:
                    old = self.get(kind, identifier, conn)
                    agent_id = old["agentId"]
                    if payload.get("agentId", agent_id) != agent_id:
                        raise ValueError("Knowledge ownership cannot be changed")
                else:
                    agent_id = payload["agentId"]
                require_agent(conn, agent_id)
                values = {snake(k): v for k, v in payload.items() if k in FIELDS[kind]}
                if kind == "semantic" and identifier is None:
                    ds = conn.execute(
                        text(
                            "SELECT datasource_id FROM agent_datasource "
                            "WHERE agent_id=:aid ORDER BY is_active DESC,id LIMIT 1"
                        ),
                        {"aid": agent_id},
                    ).scalar()
                    if ds is None:
                        raise ValueError("No datasource found for Agent")
                    values["datasource_id"] = ds
                if identifier is None:
                    values["agent_id"] = agent_id
                    cols = ",".join(values)
                    identifier = conn.execute(
                        text(
                            f"INSERT INTO {TABLES[kind]} ({cols}) VALUES ("
                            + ",".join(":" + k for k in values)
                            + ")"
                        ),
                        values,
                    ).lastrowid
                else:
                    conn.execute(
                        text(
                            f"UPDATE {TABLES[kind]} SET "
                            + ",".join(k + "=:" + k for k in values)
                            + " WHERE id=:_id"
                        ),
                        {**values, "_id": identifier},
                    )
                conn.execute(
                    text(
                        "INSERT INTO python_knowledge_state(kind,record_id,agent_id) "
                        "VALUES (:kind,:id,:aid) ON DUPLICATE KEY UPDATE "
                        "revision=revision+1, embedding_status='PENDING',error_msg=NULL"
                    ),
                    {"kind": kind, "id": identifier, "aid": agent_id},
                )
            self.rebuild(kind, identifier)
            return self.get(kind, identifier)

    def set_status(self, conn, kind, identifier, status, error=None):
        params = {"kind": kind, "id": identifier, "status": status, "error": error}
        conn.execute(
            text(
                "UPDATE python_knowledge_state SET embedding_status=:status,error_msg=:error "
                "WHERE kind=:kind AND record_id=:id"
            ),
            params,
        )
        if kind != "semantic":
            conn.execute(
                text(
                    f"UPDATE {TABLES[kind]} SET embedding_status=:status,error_msg=:error "
                    "WHERE id=:id"
                ),
                params,
            )

    def rebuild(self, kind, identifier, *, config=None, publish=True):
        from app.local_files import parse_document, split_document

        with self.lock:
            row = self.get(kind, identifier)
            if publish:
                with self.engine.begin() as conn:
                    self.set_status(conn, kind, identifier, "PROCESSING")
            try:
                cfg = config or embedding_config(self.engine)
                space = embedding_space(cfg, self.settings)
                if kind == "business":
                    contents = [
                        "\n".join(
                            str(row.get(k) or "")
                            for k in ("businessTerm", "description", "synonyms")
                        )
                    ]
                elif kind == "semantic":
                    contents = [
                        "\n".join(
                            str(row.get(k) or "")
                            for k in (
                                "tableName",
                                "columnName",
                                "businessName",
                                "synonyms",
                                "businessDescription",
                                "columnComment",
                                "dataType",
                            )
                        )
                    ]
                elif row["type"] == "DOCUMENT":
                    contents = split_document(
                        parse_document(self.settings, row["filePath"]),
                        row.get("splitterType") or "token",
                        lambda value: embed(
                            cfg,
                            value,
                            self.settings.model_timeout,
                            self.settings.embedding_dimension,
                        ),
                    )
                else:
                    contents = [row["question"] + "\n" + row["content"]]
                vectors = [
                    embed(
                        cfg, content, self.settings.model_timeout, self.settings.embedding_dimension
                    )
                    for content in contents
                ]
                if len({len(v) for v in vectors}) != 1:
                    raise ValueError("Inconsistent embedding dimensions")
                if publish:
                    self.delete_external(kind, identifier)
                elif row.get("embeddingSpace") == space:
                    raise ValueError("Staging requires a distinct embedding space or namespace")
                if self.external:
                    with self.index() as db:
                        db.execute(
                            "INSERT OR IGNORE INTO external_targets VALUES (?,?,?,?,?,?,?,?)",
                            (
                                kind,
                                identifier,
                                row["agentId"],
                                self.settings.vector_backend,
                                self.settings.vector_url,
                                self.settings.vector_namespace,
                                space,
                                len(vectors[0]),
                            ),
                        )
                    self.external.replace(
                        kind,
                        identifier,
                        row["agentId"],
                        row["contentRevision"],
                        space,
                        list(zip(contents, vectors)),
                    )
                with self.index() as db:
                    if publish:
                        db.execute(
                            "DELETE FROM chunks WHERE kind=? AND record_id=?", (kind, identifier)
                        )
                    else:
                        db.execute(
                            "DELETE FROM chunks WHERE kind=? AND record_id=? AND space=?",
                            (kind, identifier, space),
                        )
                    db.executemany(
                        "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)",
                        [
                            (
                                kind,
                                identifier,
                                row["agentId"],
                                row["contentRevision"],
                                space,
                                i,
                                content,
                                json.dumps(vector),
                            )
                            for i, (content, vector) in enumerate(zip(contents, vectors))
                        ],
                    )
                if not publish:
                    return {"revision": row["contentRevision"], "space": space}
                with self.engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE python_knowledge_state SET index_revision=revision,"
                            "embedding_space=:space WHERE kind=:kind AND record_id=:id"
                        ),
                        {"space": space, "kind": kind, "id": identifier},
                    )
                    self.set_status(conn, kind, identifier, "COMPLETED")
            except Exception as exc:  # noqa: BLE001 -- persist failures from every parser/index adapter
                # Only our sanitized errors may reach the API, never parser paths/provider bodies.
                error = (
                    str(exc)[:255]
                    if isinstance(exc, ValueError)
                    else "File parsing or index write failed; retry embedding"
                )
                if not publish:
                    raise ValueError(error) from None
                with self.engine.begin() as conn:
                    self.set_status(conn, kind, identifier, "FAILED", error)

    def recall(self, kind, identifier, enabled):
        with self.lock, self.engine.begin() as conn:
            self.get(kind, identifier, conn)
            col = "status" if kind == "semantic" else "is_recall"
            conn.execute(
                text(f"UPDATE {TABLES[kind]} SET {col}=:enabled WHERE id=:id"),
                {"enabled": enabled, "id": identifier},
            )

    def delete(self, kind, identifier):
        with self.lock:
            self.delete_external(kind, identifier)
            with self.engine.begin() as conn:
                row = self.get(kind, identifier, conn)
                if kind == "semantic":
                    conn.execute(
                        text("DELETE FROM semantic_model WHERE id=:id"), {"id": identifier}
                    )
                else:
                    conn.execute(
                        text(f"UPDATE {TABLES[kind]} SET is_deleted=1 WHERE id=:id"),
                        {"id": identifier},
                    )
                conn.execute(
                    text("DELETE FROM python_knowledge_state WHERE kind=:kind AND record_id=:id"),
                    {"kind": kind, "id": identifier},
                )
            with self.index() as db:
                db.execute("DELETE FROM chunks WHERE kind=? AND record_id=?", (kind, identifier))
            if row.get("filePath"):
                from app.local_files import cleanup_unreferenced_file

                cleanup_unreferenced_file(self.engine, self.settings, row["filePath"])

    def search(self, agent_id, query, kinds=None):
        with self.lock:
            with self.engine.connect() as conn:
                require_agent(conn, agent_id)
                policy = (
                    conn.execute(
                        text("SELECT * FROM python_recall_config WHERE agent_id=:aid"),
                        {"aid": agent_id},
                    )
                    .mappings()
                    .first()
                )
            top_k = policy["top_k"] if policy else 8
            threshold = policy["similarity_threshold"] if policy else 0.0
            records = {}
            from app.agent_datasources import current_binding

            with self.engine.connect() as conn:
                try:
                    binding = current_binding(conn, agent_id)
                except ValueError:
                    binding = {}
            for kind in TABLES:
                if kinds and kind not in kinds:
                    continue
                for row in self.list(kind, agent_id):
                    if kind == "semantic" and (
                        row["tableName"] not in binding.get("selectTables", [])
                        or row["datasourceId"] != binding.get("datasourceId")
                    ):
                        continue
                    if (
                        row.get("isRecall", row.get("status") == 1)
                        and row.get("embeddingStatus") == "COMPLETED"
                        and row.get("contentRevision") == row.get("indexRevision")
                    ):
                        records[(kind, row["id"])] = row
            if not records:
                return []
            cfg = embedding_config(self.engine)
            space = embedding_space(cfg, self.settings)
            vector = embed(
                cfg, query, self.settings.model_timeout, self.settings.embedding_dimension
            )
            hits = []
            if self.external:
                allowed = [
                    (kind, identifier, row["contentRevision"])
                    for (kind, identifier), row in records.items()
                    if row.get("embeddingSpace") == space
                ]
                with self.index() as db:
                    manifest = db.execute(
                        "SELECT kind,record_id,revision,COUNT(*) FROM chunks "
                        "WHERE agent_id=? AND space=? "
                        "GROUP BY kind,record_id,revision",
                        (agent_id, space),
                    ).fetchall()
                expected_counts = {
                    (kind, identifier, revision): count
                    for kind, identifier, revision, count in manifest
                }
                try:
                    results = self.external.search(
                        agent_id,
                        space,
                        vector,
                        allowed,
                        top_k,
                        verify=True,
                        expected_counts=expected_counts,
                    )
                except IndexIncompleteError as exc:
                    with self.engine.begin() as conn:
                        for kind, identifier, _ in exc.missing:
                            self.set_status(conn, kind, identifier, "FAILED", str(exc))
                    raise
                for hit in results:
                    row = records[(hit["kind"], hit["record_id"])]
                    if hit["score"] >= threshold:
                        hits.append(
                            {
                                "kind": hit["kind"],
                                "id": hit["record_id"],
                                "content": hit["content"],
                                "score": hit["score"],
                                "contentRevision": hit["revision"],
                                "embeddingSpace": space,
                                "tableName": row.get("tableName"),
                                "datasourceId": row.get("datasourceId"),
                            }
                        )
                return hits
            with self.index() as db:
                rows = db.execute(
                    "SELECT kind,record_id,revision,content,vector FROM chunks "
                    "WHERE agent_id=? AND space=?",
                    (agent_id, space),
                ).fetchall()
            for kind, identifier, revision, content, stored_vector in rows:
                row = records.get((kind, identifier))
                if row is None or revision != row["contentRevision"]:
                    continue
                score = cosine(vector, json.loads(stored_vector))
                if score >= threshold:
                    hits.append(
                        {
                            "kind": kind,
                            "id": identifier,
                            "content": content,
                            "score": score,
                            "contentRevision": revision,
                            "embeddingSpace": space,
                            "tableName": row.get("tableName"),
                            "datasourceId": row.get("datasourceId"),
                        }
                    )
            return sorted(hits, key=lambda hit: hit["score"], reverse=True)[:top_k]
