"""Local immutable uploads, bounded parsers and reference-aware cleanup."""

import hashlib
import html
import io
import json
import mimetypes
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

import tiktoken
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
from sqlalchemy import text

router = APIRouter(prefix="/api/upload")
DOCUMENT_TYPES = {".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"}
SPLITTERS = {"token", "recursive", "sentence", "paragraph", "semantic"}


def file_references(*values):
    """Recognize local upload URLs in display HTML/text and nested JSON metadata."""
    references: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            references.update(file_references(*value.values()))
        elif isinstance(value, (list, tuple)):
            references.update(file_references(*value))
        elif isinstance(value, str):
            try:
                decoded = json.loads(value)
            except (ValueError, RecursionError):
                decoded = None
            if isinstance(decoded, (dict, list)):
                references.update(file_references(decoded))
            for match in re.finditer(r'''/api/upload/files/([^\s"'<>?#)]+)''', unquote(html.unescape(value))):
                relative = match.group(1)
                if relative.startswith(('knowledge/', 'avatars/', 'reports/')) and '..' not in relative.split('/'):
                    references.add(relative)
    return references


def validate_file_references(conn, settings, *values):
    """Caller holds the file lifecycle lock until publishing the new reference."""
    for relative in file_references(*values):
        present = conn.execute(text('SELECT 1 FROM python_local_file WHERE path=:path'),
                               {'path': relative}).scalar()
        if not present or not file_path(settings, relative).is_file():
            raise HTTPException(400, '引用的本地文件已清理，请重新上传或选择有效文件')


def file_path(settings, relative):
    base = (settings.data_dir / "files").resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or path == base:
        raise HTTPException(403, "Invalid file path")
    return path


def store_file(engine, settings, filename, raw, mime=None, category="knowledge"):
    if not raw or len(raw) > settings.max_upload_bytes:
        raise ValueError("Empty file or upload exceeds size limit")
    filename = Path(filename.replace("\\", "/")).name[:255]
    suffix = Path(filename).suffix.lower()
    relative = f"{category}/{hashlib.sha256(raw).hexdigest()}{suffix}"
    path = file_path(settings, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Content-addressed bytes are immutable, shared references never overwrite them.
    if not path.exists():
        import uuid

        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(raw)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT IGNORE INTO python_local_file(path,original_name,mime_type,size_bytes) "
                "VALUES (:path,:name,:mime,:size)"
            ),
            {
                "path": relative,
                "name": filename,
                "mime": mime or mimetypes.guess_type(filename)[0] or "application/octet-stream",
                "size": len(raw),
            },
        )
    return relative


def cleanup_unreferenced_file(engine, settings, relative):
    """Reusable by ticket 08; caller holds the knowledge/file lifecycle lock."""
    with engine.begin() as conn:
        used = conn.execute(
            text("SELECT COUNT(*) FROM agent_knowledge WHERE file_path=:path AND is_deleted=0"),
            {"path": relative},
        ).scalar()
        avatar = conn.execute(
            text("SELECT COUNT(*) FROM agent WHERE avatar=:url"),
            {"url": "/api/upload/files/" + relative},
        ).scalar()
        reports = conn.execute(text(
            "SELECT COUNT(*) FROM agent_run_result WHERE JSON_SEARCH(artifacts,'one',:url) IS NOT NULL"
        ), {'url': '/api/upload/files/' + relative}).scalar()
        staged = conn.execute(text(
            "SELECT COUNT(*) FROM graph_effect WHERE effect_key='v1:report_file:main:0' "
            "AND status='COMMITTED' AND JSON_UNQUOTE(JSON_EXTRACT(result_ref,'$.url'))=:url"
        ), {'url': '/api/upload/files/' + relative}).scalar()
        messages = conn.execute(text(
            "SELECT m.content,m.metadata FROM chat_message m JOIN chat_session s ON s.id=m.session_id "
            "WHERE s.status<>'deleted'"
        )).mappings()
        history = any(relative in file_references(row['content'], row['metadata']) for row in messages)
        if used or avatar or reports or staged or history:
            return False
        file_path(settings, relative).unlink(missing_ok=True)
        conn.execute(text("DELETE FROM python_local_file WHERE path=:path"), {"path": relative})
        conn.execute(
            text(
                "UPDATE agent_knowledge SET is_resource_cleaned=1 "
                "WHERE file_path=:path AND is_deleted=1"
            ),
            {"path": relative},
        )
    return True


def parse_document(settings, relative):
    path = file_path(settings, relative)
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        raw = path.read_bytes()
        content = None
        encodings = (
            ["utf-16"] if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ["utf-8-sig", "gb18030"]
        )
        for encoding in encodings:
            try:
                content = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if content is None or "\x00" in content:
            raise ValueError("Text encoding is invalid; use UTF-8")
    elif suffix in {".pdf", ".docx"}:
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("document_parser.py")),
                    str(path),
                    str(settings.max_document_chars),
                ],
                capture_output=True,
                timeout=settings.parser_timeout,
                check=True,
            )
            content = result.stdout.decode("utf-8")
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
            raise ValueError("Document parsing failed, exceeded limits or timed out") from None
    elif suffix == ".doc":
        tika_jar = settings.tika_app_jar or settings.data_dir / "tools/tika-app-3.3.3.jar"
        if not tika_jar.is_file():
            raise ValueError(
                "DOC parser unavailable: configure DATAAGENT_TIKA_APP_JAR and Java 17+"
            )
        try:
            result = subprocess.run(
                ["java", "-Xmx256m", "-jar", str(tika_jar), "--text", str(path)],
                capture_output=True,
                timeout=settings.parser_timeout,
                check=True,
            )
            content = result.stdout.decode("utf-8")
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
            raise ValueError("DOC parsing failed or timed out") from None
    else:
        raise ValueError("Unsupported document format")
    if not content.strip():
        raise ValueError("Document has no extractable text (scanned PDFs require OCR)")
    if len(content) > settings.max_document_chars:
        raise ValueError("Extracted document exceeds text limit")
    return content.strip()


def split_document(content, strategy, embedding=None):
    if strategy not in SPLITTERS:
        raise ValueError("Unsupported splitter type")
    if strategy == "token":
        codec = tiktoken.get_encoding("cl100k_base")
        tokens = codec.encode(content, disallowed_special=())
        return [codec.decode(tokens[start : start + 800]) for start in range(0, len(tokens), 700)]
    if strategy == "paragraph":
        pieces = re.split(r"\n\s*\n", content)
    elif strategy in {"sentence", "semantic"}:
        pieces = re.split(r"(?<=[。！？.!?])\s*|\n+", content)
    else:
        pieces = re.split(r"\n\s*\n|\n|(?<=[。！？])", content)
    chunks = []
    current = ""
    previous = None
    for piece in filter(str.strip, pieces):
        boundary = False
        if strategy == "semantic":
            from app.knowledge_store import cosine

            if embedding is None:
                raise ValueError("Semantic splitter requires embedding model")
            vector = embedding(piece)
            boundary = (
                previous is not None and len(current) >= 200 and cosine(previous, vector) < 0.5
            )
            previous = vector
        if current and (boundary or len(current) + len(piece) > 1000):
            chunks.append(current)
            current = ""
        for start in range(0, len(piece), 1000):
            part = piece[start : start + 1000]
            if current and len(current) + len(part) > 1000:
                chunks.append(current)
                current = ""
            current = (current + "\n" + part).strip()
    if current:
        chunks.append(current)
    return chunks


@router.post("/avatar")
def upload_avatar(request: Request, file: Annotated[UploadFile, File()]):
    raw = file.file.read(request.app.state.settings.max_upload_bytes + 1)
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image_format = image.format or ""
        extension = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp"}.get(
            image_format
        )
        if not extension or not (file.content_type or "").startswith("image/"):
            raise ValueError("Only PNG, JPEG, GIF and WEBP images are supported")
        if len(raw) > request.app.state.settings.max_avatar_bytes:
            raise ValueError("Avatar exceeds size limit")
        with request.app.state.knowledge.lock:
            relative = store_file(
                request.app.state.engine,
                request.app.state.settings,
                "avatar" + extension,
                raw,
                Image.MIME[image_format],
                "avatars",
            )
        return {
            "success": True,
            "message": "上传成功",
            "url": "/api/upload/files/" + relative,
            "filename": Path(relative).name,
        }
    except (ValueError, OSError, Image.DecompressionBombError):
        return JSONResponse(
            {"success": False, "message": "Invalid image or image size exceeds limit"},
            status_code=400,
        )


@router.get("/files/{relative:path}")
def read_file(relative: str, request: Request):
    path = file_path(request.app.state.settings, relative)
    with request.app.state.engine.connect() as conn:
        row = (
            conn.execute(
                text("SELECT * FROM python_local_file WHERE path=:path"), {"path": relative}
            )
            .mappings()
            .first()
        )
    if row is None or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path,
        media_type=row["mime_type"],
        filename=row["original_name"],
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", **(
            {"Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"}
            if relative.startswith('reports/') else {}
        )},
    )
