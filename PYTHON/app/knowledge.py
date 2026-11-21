"""Legacy-compatible business/document management and explicit recall extensions."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.agents import authorize_agent, require_agent, response
from app.local_files import DOCUMENT_TYPES, SPLITTERS, store_file

router = APIRouter()


class BusinessInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    agentId: int
    businessTerm: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    synonyms: str | None = None
    isRecall: bool = True


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)


class KnowledgePage(BaseModel):
    agentId: int
    title: str | None = None
    type: Literal["DOCUMENT", "QA", "FAQ", ""] | None = None
    embeddingStatus: str | None = None
    pageNum: int = Field(default=1, ge=1)
    pageSize: int = Field(default=10, ge=1, le=200)


class RecallPolicy(BaseModel):
    topK: int = Field(default=8, ge=1, le=100)
    similarityThreshold: float = Field(default=0, ge=-1, le=1, allow_inf_nan=False)


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    kinds: list[Literal["business", "semantic", "document"]] | None = None


@router.get("/api/business-knowledge")
def business_list(request: Request, agentId: int, keyword: str | None = None):
    return response(request.app.state.knowledge.list("business", agentId, keyword))


@router.post("/api/business-knowledge")
def create_business(body: BusinessInput, request: Request):
    return response(request.app.state.knowledge.save("business", body.model_dump()))


@router.post("/api/business-knowledge/refresh-vector-store")
def refresh_business(agentId: int, request: Request):
    store = request.app.state.knowledge
    for row in store.list("business", agentId):
        if row["isRecall"]:
            store.rebuild("business", row["id"])
    failed = [
        r
        for r in store.list("business", agentId)
        if r["isRecall"] and r["embeddingStatus"] != "COMPLETED"
    ]
    return response(
        success=not failed, message="Index refresh failed" if failed else "Index refreshed"
    )


@router.post("/api/business-knowledge/recall/{identifier}")
def recall_business(identifier: int, isRecall: bool, request: Request):
    request.app.state.knowledge.recall("business", identifier, isRecall)
    return response()


@router.post("/api/business-knowledge/retry-embedding/{identifier}")
def retry_business(identifier: int, request: Request):
    request.app.state.knowledge.rebuild("business", identifier)
    return response()


@router.get("/api/business-knowledge/{identifier}")
def read_business(identifier: int, request: Request):
    return response(request.app.state.knowledge.get("business", identifier))


@router.put("/api/business-knowledge/{identifier}")
def update_business(identifier: int, body: BusinessInput, request: Request):
    # Recall has its own endpoint and must survive editing the content.
    return response(
        request.app.state.knowledge.save(
            "business", body.model_dump(exclude={"isRecall"}), identifier
        )
    )


@router.delete("/api/business-knowledge/{identifier}")
def delete_business(identifier: int, request: Request):
    request.app.state.knowledge.delete("business", identifier)
    return response()


@router.post("/api/agent-knowledge/create")
def create_document(
    request: Request,
    agentId: int = Form(...),
    title: str = Form(...),
    type: Literal["DOCUMENT", "QA", "FAQ"] = Form(...),
    question: str | None = Form(None),
    content: str | None = Form(None),
    splitterType: str = Form("token"),
    isRecall: bool = Form(True),
    file: Annotated[UploadFile | None, File()] = None,
):
    if not title.strip() or len(title) > 255 or splitterType not in SPLITTERS:
        raise ValueError("Invalid title or splitter type")
    with request.app.state.engine.connect() as conn:
        require_agent(conn, agentId)
    values: dict[str, Any] = {
        "agentId": agentId,
        "title": title,
        "type": type,
        "question": question,
        "content": content,
        "splitterType": splitterType,
        "isRecall": isRecall,
    }
    with request.app.state.knowledge.lock:
        if type == "DOCUMENT":
            from pathlib import Path

            if file is None or Path(file.filename or "").suffix.lower() not in DOCUMENT_TYPES:
                raise ValueError(
                    "Document file required; supported: pdf, doc, docx, txt, md, markdown"
                )
            raw = file.file.read(request.app.state.settings.max_upload_bytes + 1)
            path = store_file(
                request.app.state.engine,
                request.app.state.settings,
                file.filename or "document",
                raw,
            )
            values.update(
                sourceFilename=file.filename,
                filePath=path,
                fileSize=len(raw),
                fileType=Path(path).suffix.lstrip("."),
            )
        elif not question or not question.strip() or not content or not content.strip():
            raise ValueError("Question and content are required for QA/FAQ")
        return response(request.app.state.knowledge.save("document", values))


@router.post("/api/agent-knowledge/query/page")
def page_document(body: KnowledgePage, request: Request):
    rows = request.app.state.knowledge.list("document", body.agentId, body.title)
    rows = [
        r
        for r in rows
        if (not body.type or r["type"] == body.type)
        and (not body.embeddingStatus or r["embeddingStatus"] == body.embeddingStatus)
    ]
    start = (body.pageNum - 1) * body.pageSize
    return {
        **response(rows[start : start + body.pageSize]),
        "total": len(rows),
        "pageNum": body.pageNum,
        "pageSize": body.pageSize,
        "totalPages": (len(rows) + body.pageSize - 1) // body.pageSize,
    }


@router.put("/api/agent-knowledge/recall/{identifier}")
def recall_document(identifier: int, isRecall: bool, request: Request):
    request.app.state.knowledge.recall("document", identifier, isRecall)
    return response(request.app.state.knowledge.get("document", identifier))


@router.post("/api/agent-knowledge/retry-embedding/{identifier}")
def retry_document(identifier: int, request: Request):
    request.app.state.knowledge.rebuild("document", identifier)
    return response()


@router.get("/api/agent-knowledge/{identifier}")
def read_document(identifier: int, request: Request):
    return response(request.app.state.knowledge.get("document", identifier))


@router.put("/api/agent-knowledge/{identifier}")
def update_document(identifier: int, body: DocumentUpdate, request: Request):
    values = body.model_dump(exclude_none=True)
    if not values:
        return response(request.app.state.knowledge.get("document", identifier))
    return response(request.app.state.knowledge.save("document", values, identifier))


@router.delete("/api/agent-knowledge/{identifier}")
def delete_document(identifier: int, request: Request):
    try:
        request.app.state.knowledge.delete("document", identifier)
    except ValueError as exc:
        if str(exc) != "Knowledge record not found":
            raise
    return response()


@router.get("/api/agent/{agent_id}/knowledge/recall-config")
def get_policy(agent_id: int, request: Request):
    with request.app.state.engine.connect() as conn:
        require_agent(conn, agent_id)
        row = (
            conn.execute(
                text("SELECT * FROM python_recall_config WHERE agent_id=:id"), {"id": agent_id}
            )
            .mappings()
            .first()
        )
    return response(
        {
            "topK": row["top_k"],
            "similarityThreshold": row["similarity_threshold"],
            "revision": row["revision"],
        }
        if row
        else {**RecallPolicy().model_dump(), "revision": 0}
    )


@router.put("/api/agent/{agent_id}/knowledge/recall-config")
def set_policy(agent_id: int, body: RecallPolicy, request: Request):
    with request.app.state.engine.begin() as conn:
        require_agent(conn, agent_id)
        conn.execute(
            text(
                "INSERT INTO python_recall_config(agent_id,top_k,similarity_threshold) "
                "VALUES (:id,:top,:threshold) ON DUPLICATE KEY UPDATE "
                "top_k=:top,similarity_threshold=:threshold,revision=revision+1"
            ),
            {"id": agent_id, "top": body.topK, "threshold": body.similarityThreshold},
        )
    return get_policy(agent_id, request)


@router.post("/api/agent/{agent_id}/knowledge/search")
def search(agent_id: int, body: SearchInput, request: Request):
    with request.app.state.engine.connect() as conn:
        authorize_agent(conn, agent_id, request)
    return response(request.app.state.knowledge.search(agent_id, body.query, body.kinds))


@router.post("/api/agent/{agent_id}/knowledge/rebuild")
def rebuild_index(agent_id: int, request: Request):
    with request.app.state.engine.connect() as conn:
        authorize_agent(conn, agent_id, request)
    store = request.app.state.knowledge
    failed = []
    with store.lock:
        for kind in ("business", "semantic", "document"):
            for row in store.list(kind, agent_id):
                store.rebuild(kind, row["id"])
                if store.get(kind, row["id"])["embeddingStatus"] != "COMPLETED":
                    failed.append({"kind": kind, "id": row["id"]})
    return response({"failed": failed}, success=not failed)
