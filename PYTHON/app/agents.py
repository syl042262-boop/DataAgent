"""Agent management and the shared runtime credential/lifecycle boundary."""

import hashlib
import hmac
import secrets

import bcrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text


def response(data=None, message="操作成功", success=True):
    return {"success": success, "message": message, "data": data}


def camel_row(row):
    def camel(name):
        first, *rest = name.split("_")
        return first + "".join(part.title() for part in rest)

    return {camel(key): value for key, value in dict(row).items()}


def require_agent(connection, identifier, lock=False):
    row = (
        connection.execute(
            text("SELECT * FROM agent WHERE id=:id AND NOT EXISTS "
                 "(SELECT 1 FROM agent_lifecycle WHERE agent_id=:id AND lifecycle='DELETED')"
                 + (" FOR UPDATE" if lock else "")),
            {"id": identifier},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(404, "Agent 不存在")
    return row


def lock_agent(connection, identifier):
    require_agent(connection, identifier, lock=True)
    connection.execute(
        text("INSERT IGNORE INTO agent_lifecycle(agent_id) VALUES (:id)"), {"id": identifier}
    )
    lifecycle = connection.execute(
        text("SELECT lifecycle FROM agent_lifecycle WHERE agent_id=:id FOR UPDATE"),
        {"id": identifier},
    ).scalar_one()
    if lifecycle != "OPEN":
        raise HTTPException(409, "Agent 正在清理")


def authorize_agent(connection, identifier, request):
    agent = require_agent(connection, identifier)
    if not agent["api_key_enabled"]:
        return
    supplied = request.headers.get("x-api-key")
    if supplied is None:
        scheme, _, value = request.headers.get("authorization", "").partition(" ")
        supplied = value if scheme.lower() == "bearer" else ""
    digest = "sha256:" + hashlib.sha256(supplied.encode()).hexdigest()
    stored = agent['api_key'] or ''
    valid = hmac.compare_digest(digest, stored)
    if stored.startswith('{bcrypt}'):
        try:
            valid = bool(supplied) and bcrypt.checkpw(supplied.encode(), stored[8:].encode())
        except ValueError:
            valid = False
    if not valid:
        raise HTTPException(401, "API Key 无效或缺失")


def public_agent(row):
    result = camel_row(row)
    result.pop("apiKey", None)
    return result


class AgentInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    avatar: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|published|offline)$")
    prompt: str | None = None
    category: str | None = Field(default=None, max_length=100)
    adminId: int | None = None
    tags: str | None = None


class QuestionInput(BaseModel):
    question: str = Field(min_length=1)
    isActive: bool = True


router = APIRouter(prefix="/api/agent")


@router.get("/list")
def list_agents(request: Request, status: str = "", keyword: str = ""):
    with request.app.state.engine.connect() as connection:
        clause, params = "", {}
        if keyword.strip():
            clause, params = " AND (name LIKE :q OR description LIKE :q)", {"q": f"%{keyword}%"}
        elif status.strip():
            clause, params = " AND status=:s", {"s": status}
        return [
            public_agent(r)
            for r in connection.execute(
                text("SELECT * FROM agent WHERE NOT EXISTS (SELECT 1 FROM agent_lifecycle "
                     "WHERE agent_id=agent.id AND lifecycle='DELETED')"
                     + clause + " ORDER BY create_time DESC, id DESC"), params
            ).mappings()
        ]


@router.post("")
def create_agent(body: AgentInput, request: Request):
    if not body.name or not body.name.strip():
        raise HTTPException(400, "名称不能为空")
    values = body.model_dump()
    values["status"] = body.status or "draft"
    from app.local_files import validate_file_references

    with request.app.state.knowledge.lock, request.app.state.engine.begin() as connection:
        validate_file_references(connection, request.app.state.settings, values.get('avatar'))
        result = connection.execute(
            text(
                "INSERT INTO agent(name,description,avatar,status,prompt,category,admin_id,tags) "
                "VALUES (:name,:description,:avatar,:status,:prompt,:category,:adminId,:tags)"
            ),
            values,
        )
        identifier = result.lastrowid
        lock_agent(connection, identifier)
        return public_agent(require_agent(connection, identifier))


@router.get("/{identifier}")
def get_agent(identifier: int, request: Request):
    with request.app.state.engine.connect() as connection:
        return public_agent(require_agent(connection, identifier))


@router.put("/{identifier}")
def update_agent(identifier: int, body: AgentInput, request: Request):
    values = body.model_dump(exclude_unset=True)
    if "name" in values and (not values["name"] or not values["name"].strip()):
        raise HTTPException(400, "名称不能为空")
    if "status" in values and values["status"] is None:
        raise HTTPException(400, "状态不能为空")
    from app.local_files import validate_file_references

    with request.app.state.knowledge.lock, request.app.state.engine.begin() as connection:
        validate_file_references(connection, request.app.state.settings, values.get('avatar'))
        lock_agent(connection, identifier)
        if values:
            columns = {"adminId": "admin_id"}
            assignments = ",".join(f"{columns.get(k, k)}=:{k}" for k in values)
            connection.execute(
                text("UPDATE agent SET " + assignments + " WHERE id=:id"),
                {**values, "id": identifier},
            )
        return public_agent(require_agent(connection, identifier))


@router.post("/{identifier}/publish")
def publish(identifier: int, request: Request):
    return update_agent(identifier, AgentInput(status="published"), request)


@router.post("/{identifier}/offline")
def offline(identifier: int, request: Request):
    return update_agent(identifier, AgentInput(status="offline"), request)


@router.get("/{identifier}/api-key")
def key_status(identifier: int, request: Request):
    with request.app.state.engine.connect() as connection:
        agent = require_agent(connection, identifier)
        return response(
            {
                "apiKey": "****" if agent["api_key"] else None,
                "apiKeyEnabled": agent["api_key_enabled"],
            }
        )


def generate_key(identifier, request):
    key = "sk-" + secrets.token_hex(24)
    encoded = "sha256:" + hashlib.sha256(key.encode()).hexdigest()
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, identifier)
        connection.execute(
            text("UPDATE agent SET api_key=:key,api_key_enabled=1 WHERE id=:id"),
            {"key": encoded, "id": identifier},
        )
    return response({"apiKey": key, "apiKeyEnabled": 1})


@router.post("/{identifier}/api-key/generate")
def generate(identifier: int, request: Request):
    return generate_key(identifier, request)


@router.post("/{identifier}/api-key/reset")
def reset(identifier: int, request: Request):
    return generate_key(identifier, request)


@router.delete("/{identifier}/api-key")
def delete_key(identifier: int, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, identifier)
        connection.execute(
            text("UPDATE agent SET api_key=NULL,api_key_enabled=0 WHERE id=:id"), {"id": identifier}
        )
    return response({"apiKey": None, "apiKeyEnabled": 0})


@router.post("/{identifier}/api-key/enable")
def enable_key(identifier: int, enabled: bool, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, identifier)
        agent = require_agent(connection, identifier)
        if enabled and not agent["api_key"]:
            raise ValueError("请先生成 API Key")
        connection.execute(
            text("UPDATE agent SET api_key_enabled=:flag WHERE id=:id"),
            {"flag": int(enabled), "id": identifier},
        )
    return key_status(identifier, request)


@router.get("/{identifier}/access")
def check_access(identifier: int, request: Request):
    """Python-only preflight; runtime APIs must also authorize on every request."""
    with request.app.state.engine.connect() as connection:
        authorize_agent(connection, identifier, request)
    return response()


@router.get("/{identifier}/preset-questions")
def questions(identifier: int, request: Request):
    with request.app.state.engine.connect() as connection:
        require_agent(connection, identifier)
        rows = connection.execute(
            text("SELECT * FROM agent_preset_question WHERE agent_id=:id ORDER BY sort_order,id"),
            {"id": identifier},
        ).mappings()
        return [{**camel_row(r), "isActive": bool(r["is_active"])} for r in rows]


@router.post("/{identifier}/preset-questions")
def save_questions(identifier: int, body: list[QuestionInput], request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, identifier)
        connection.execute(
            text("DELETE FROM agent_preset_question WHERE agent_id=:id"), {"id": identifier}
        )
        for position, question in enumerate(body):
            connection.execute(
                text(
                    "INSERT INTO agent_preset_question "
                    "(agent_id,question,sort_order,is_active) VALUES (:id,:q,:n,:a)"
                ),
                {
                    "id": identifier,
                    "q": question.question,
                    "n": position,
                    "a": int(question.isActive),
                },
            )
    return {"message": "预设问题保存成功"}


@router.delete("/{identifier}/preset-questions/{question_id}")
def delete_question(identifier: int, question_id: int, request: Request):
    with request.app.state.engine.begin() as connection:
        lock_agent(connection, identifier)
        connection.execute(
            text("DELETE FROM agent_preset_question WHERE agent_id=:id AND id=:q"),
            {"id": identifier, "q": question_id},
        )
    return {"message": "预设问题删除成功"}
