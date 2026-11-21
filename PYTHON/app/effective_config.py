"""Secret-free effective configuration snapshot and deterministic fingerprint for run/resume validation."""

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.agent_datasources import current_binding
from app.agents import response
from app.datasources import require_datasource
from app.logical_relations import load_logical_relations
from app.prompts import SUPPORTED_PROMPT_TYPES, load_active_prompts

router = APIRouter(prefix="/api/agent")


@router.get("/{agent_id}/effective-config")
def get_effective_config(agent_id: int, request: Request):
    with request.app.state.engine.connect() as conn:
        return response(read_effective_config(conn, agent_id, request.app.state.settings))


def read_effective_config(conn, agent_id: int, settings=None) -> dict[str, Any]:
    """Assemble the secret-free effective configuration and canonical SHA-256 fingerprint."""
    agent_row = (
        conn.execute(
            text("SELECT id, name, status, api_key_enabled, prompt FROM agent WHERE id=:id"),
            {"id": agent_id},
        )
        .mappings()
        .first()
    )
    if agent_row is None:
        raise ValueError("智能体不存在")

    binding = current_binding(conn, agent_id)
    source = require_datasource(conn, binding["datasourceId"])
    selected_tables = sorted(binding.get("selectTables") or [])
    relations = load_logical_relations(conn, binding["datasourceId"], selected_tables)

    prompts_by_type = {
        ptype: [
            {
                "id": item["id"],
                "promptType": item["promptType"],
                "agentId": item["agentId"],
                "systemPrompt": item["systemPrompt"],
                "priority": item["priority"],
                "displayOrder": item["displayOrder"],
            }
            for item in load_active_prompts(conn, ptype, agent_id)
        ]
        for ptype in SUPPORTED_PROMPT_TYPES
    }

    model_row = (
        conn.execute(
            text(
                "SELECT id, provider, base_url, model_name, temperature, max_tokens, completions_path "
                "FROM model_config WHERE is_deleted=0 AND model_type='CHAT' AND is_active=1 LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    active_model = (
        {
            "id": model_row["id"],
            "provider": model_row["provider"],
            "baseUrl": model_row["base_url"],
            "modelName": model_row["model_name"],
            "temperature": str(model_row["temperature"]) if model_row["temperature"] is not None else None,
            "maxTokens": model_row["max_tokens"],
            "completionsPath": model_row["completions_path"],
        }
        if model_row
        else None
    )

    from app.config import Settings

    settings = settings or Settings()
    storage = {'backend': settings.vector_backend, 'dimension': settings.embedding_dimension}
    if settings.vector_backend != 'local':
        storage.update(url=settings.vector_url.rstrip('/'), namespace=settings.vector_namespace)
    config: dict[str, Any] = {
        'vectorStorage': storage,
        "agent": {
            "id": agent_row["id"],
            "status": agent_row["status"],
            "apiKeyEnabled": bool(agent_row["api_key_enabled"]),
            "prompt": agent_row["prompt"],
        },
        "datasource": {
            "id": source["id"],
            "type": source["type"],
            "host": source["host"],
            "port": source["port"],
            "databaseName": source["database_name"],
            "schemaName": source.get("schema_name"),
            "connectionUrl": source.get("connection_url"),
            "username": source.get('username'),
        },
        "selectTables": selected_tables,
        "logicalRelations": [
            {
                "sourceTableName": r["sourceTableName"],
                "sourceColumnName": r["sourceColumnName"],
                "targetTableName": r["targetTableName"],
                "targetColumnName": r["targetColumnName"],
                "relationType": r["relationType"],
                "description": r["description"],
            }
            for r in relations
        ],
        "prompts": prompts_by_type,
        "chatModel": active_model,
        "knowledge": knowledge_config(conn, agent_id),
    }
    canonical = json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {"configFingerprint": fingerprint, "config": config}


def knowledge_config(conn, agent_id):
    """Content, recall policy and index/model revisions without provider credentials."""
    records: list[dict[str, Any]] = []
    for kind, table in [('business', 'business_knowledge'), ('document', 'agent_knowledge'),
                        ('semantic', 'semantic_model')]:
        flag = 'status' if kind == 'semantic' else 'is_recall'
        deleted = '' if kind == 'semantic' else ' AND b.is_deleted=0'
        rows = conn.execute(text(f'SELECT b.id,b.{flag} AS enabled,s.revision,s.index_revision,'
                                 's.embedding_space,s.embedding_status FROM ' + table + ' b LEFT JOIN python_knowledge_state s '
                                 'ON s.kind=:kind AND s.record_id=b.id WHERE b.agent_id=:aid' + deleted +
                                 ' ORDER BY b.id'), {'kind': kind, 'aid': agent_id}).mappings().all()
        records.extend({'kind': kind, **dict(row)} for row in rows)
    policy = conn.execute(text('SELECT revision,top_k,similarity_threshold FROM python_recall_config '
                               'WHERE agent_id=:aid'), {'aid': agent_id}).mappings().first()
    model = conn.execute(text("SELECT provider,base_url,model_name,embeddings_path FROM model_config "
                              "WHERE model_type='EMBEDDING' AND is_active=1 AND is_deleted=0 LIMIT 1")).mappings().first()
    return {'records': records, 'policy': dict(policy) if policy else None,
            'embeddingModel': dict(model) if model else None}
