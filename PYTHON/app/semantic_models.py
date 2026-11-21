"""Semantic field management, idempotent import and legacy Excel wire format."""

import io
from datetime import datetime
from itertools import islice
from pathlib import Path
from typing import Annotated, Any

import xlrd
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response
from openpyxl import load_workbook
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.agents import require_agent, response

router = APIRouter(prefix="/api/semantic-model")
TEMPLATE = Path(__file__).resolve().parents[1] / "resources/semantic_model_template.xlsx"
IMPORT_FIELDS = [
    "tableName",
    "columnName",
    "businessName",
    "dataType",
    "synonyms",
    "businessDescription",
    "columnComment",
    "createTime",
]


class SemanticItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    tableName: str = Field(min_length=1, max_length=255)
    columnName: str = Field(min_length=1, max_length=255)
    businessName: str = Field(min_length=1, max_length=255)
    dataType: str = Field(min_length=1, max_length=255)
    synonyms: str | None = None
    businessDescription: str | None = Field(
        default=None,
        validation_alias=AliasChoices("businessDescription", "businessDesc", "description", "desc"),
    )
    columnComment: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1, ge=0, le=1)
    createTime: datetime | None = None


class SemanticInput(SemanticItem):
    agentId: int


class BatchInput(BaseModel):
    agentId: int
    items: list[dict] = Field(min_length=1, max_length=10000)


@router.get("")
def list_models(request: Request, agentId: int | None = None, keyword: str | None = None):
    # Java gives keyword precedence over agentId for this management endpoint.
    return response(
        request.app.state.knowledge.list("semantic", None if keyword else agentId, keyword)
    )


@router.post("")
def create_model(body: SemanticInput, request: Request):
    request.app.state.knowledge.save("semantic", body.model_dump())
    return response(True)


@router.delete("/batch")
def batch_delete(ids: list[int], request: Request):
    if not ids:
        raise ValueError("ID list cannot be empty")
    for identifier in dict.fromkeys(ids):
        request.app.state.knowledge.delete("semantic", identifier)
    return response(True)


@router.put("/enable")
def enable(ids: list[int], request: Request):
    return toggle(ids, True, request)


@router.put("/disable")
def disable(ids: list[int], request: Request):
    return toggle(ids, False, request)


def toggle(ids, enabled, request):
    if not ids:
        raise ValueError("ID list cannot be empty")
    for identifier in dict.fromkeys(ids):
        request.app.state.knowledge.recall("semantic", identifier, enabled)
    return response(True)


@router.post("/batch-import")
def batch_import(body: BatchInput, request: Request):
    store = request.app.state.knowledge
    result: dict[str, Any] = {
        "total": len(body.items),
        "successCount": 0,
        "failCount": 0,
        "errors": [],
    }
    with store.lock:
        with store.engine.connect() as conn:
            require_agent(conn, body.agentId)
        for index, payload in enumerate(body.items, 1):
            try:
                item = SemanticItem.model_validate(payload)
                existing = next(
                    (
                        r
                        for r in store.list("semantic", body.agentId)
                        if r["tableName"] == item.tableName and r["columnName"] == item.columnName
                    ),
                    None,
                )
                values = {**item.model_dump(exclude={"createTime"}), "agentId": body.agentId}
                if not existing and item.createTime is not None:
                    values["createdTime"] = item.createTime
                if existing:
                    values.pop("status", None)
                store.save(
                    "semantic",
                    values,
                    existing["id"] if existing else None,
                )
                result["successCount"] += 1
            except (ValueError, ValidationError, SQLAlchemyError):
                result["failCount"] += 1
                result["errors"].append(
                    f"第{index}条记录失败: invalid fields or datasource unavailable"
                )
    return response(result)


@router.get("/template/download")
def template():
    return Response(
        TEMPLATE.read_bytes(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="semantic_model_template.xlsx"'},
    )


@router.post("/import/excel")
def import_excel(
    request: Request, agentId: Annotated[int, Form()], file: Annotated[UploadFile, File()]
):
    raw = file.file.read(request.app.state.settings.max_upload_bytes + 1)
    if not raw or len(raw) > request.app.state.settings.max_upload_bytes:
        raise ValueError("Empty file or upload exceeds size limit")
    suffix = Path(file.filename or "").suffix.lower()
    try:
        if suffix == ".xlsx":
            book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            try:
                rows = list(islice(book.worksheets[0].iter_rows(values_only=True), 10002))
                if len(rows) > 10001:
                    raise ValueError("Excel exceeds 10000 data rows")
            finally:
                book.close()
        elif suffix == ".xls":
            legacy = xlrd.open_workbook(file_contents=raw)
            sheet = legacy.sheet_by_index(0)
            if sheet.nrows > 10001:
                raise ValueError("Excel exceeds 10000 data rows")
            rows = [sheet.row_values(i) for i in range(sheet.nrows)]
            legacy.release_resources()
        else:
            raise ValueError("Use .xlsx or .xls files")
        if not rows or list(rows[0][:4]) != ["表名*", "字段名*", "业务名称*", "数据类型*"]:
            raise ValueError("Excel headers do not match the template")
        items = [
            {
                key: str(value).strip() if value is not None else None
                for key, value in zip(IMPORT_FIELDS, row)
            }
            for row in rows[1:]
            if any(row)
        ]
        if not items or len(items) > 10000:
            raise ValueError("Excel requires 1 to 10000 data rows")
        # Excel rejects malformed required fields before changing any records.
        for item in items:
            SemanticItem.model_validate(item)
    except Exception:  # noqa: BLE001 -- normalize all third-party parser errors without leaking file contents
        raise ValueError(
            "Excel import failed: invalid format, headers or required fields"
        ) from None
    return batch_import(BatchInput(agentId=agentId, items=items), request)


@router.get("/{identifier}")
def read_model(identifier: int, request: Request):
    try:
        return response(request.app.state.knowledge.get("semantic", identifier))
    except ValueError:
        return response(None)


@router.put("/{identifier}")
def update_model(identifier: int, body: SemanticInput, request: Request):
    return response(request.app.state.knowledge.save("semantic", body.model_dump(), identifier))


@router.delete("/{identifier}")
def delete_model(identifier: int, request: Request):
    request.app.state.knowledge.delete("semantic", identifier)
    return response(True)
