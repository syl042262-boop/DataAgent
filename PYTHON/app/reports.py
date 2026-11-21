"""Compatible HTML export for current and historical report fragments."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

router = APIRouter()


def html_document(content: str) -> str:
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>分析报告</title></head><body>" + content + "</body></html>"
    )


@router.post("/api/sessions/{session_id}/reports/html")
async def export_html(session_id: str, request: Request):
    # The original endpoint exports a supplied fragment, including historical reports;
    # it does not require an extant session or generate fresh model output.
    try:
        content = (await request.body()).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "报告必须为 UTF-8 文本") from None
    if not content.strip():
        return Response(status_code=400)
    filename = "report_" + datetime.now().strftime("%Y%m%d%H%M%S") + ".html"
    return Response(
        html_document(content),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
