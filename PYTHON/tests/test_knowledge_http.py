"""Knowledge behavior at the agreed public HTTP/SSE boundary, with real MySQL."""

import io
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from test_stream_query_http import _setup_agent_and_model

from app.main import create_app

pytest_plugins = ["test_stream_query_http"]


@pytest.mark.parametrize("strategy", ["token", "recursive", "sentence", "paragraph", "semantic"])
def test_document_formats_and_splitters(strategy, model_server):
    from docx import Document
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    doc = Document()
    doc.add_paragraph("Paid revenue excludes refunds. Sales policy.")
    doc_bytes = io.BytesIO()
    doc.save(doc_bytes)
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (Paid revenue excludes refunds.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    fixtures = [
        ("rules.docx", doc_bytes.getvalue()),
        ("rules.pdf", pdf_bytes.getvalue()),
        ("rules.txt", b"Paid revenue excludes refunds."),
        ("rules.md", b"Paid revenue excludes refunds."),
    ]
    with TestClient(create_app()) as client:
        activate_embedding(client, model_server)
        aid = client.post("/api/agent", json={"name": "Formats"}).json()["id"]
        for filename, raw in fixtures:
            row = client.post(
                "/api/agent-knowledge/create",
                data={
                    "agentId": aid,
                    "title": filename,
                    "type": "DOCUMENT",
                    "splitterType": strategy,
                },
                files={"file": (filename, raw)},
            ).json()["data"]
            assert row["embeddingStatus"] == "COMPLETED", row
        hits = client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "refunds"}).json()[
            "data"
        ]
        assert len(hits) == 4 and all("refunds" in hit["content"] for hit in hits)


def test_doc_parser_via_http(model_server):
    sample = os.environ.get("DATAAGENT_TEST_DOC_FILE")
    jar = os.environ.get("DATAAGENT_TIKA_APP_JAR")
    if not sample or not jar:
        pytest.skip(
            "Set DATAAGENT_TEST_DOC_FILE and DATAAGENT_TIKA_APP_JAR for legacy DOC verification"
        )
    with TestClient(create_app()) as client:
        activate_embedding(client, model_server)
        aid = client.post("/api/agent", json={"name": "DOC"}).json()["id"]
        row = client.post(
            "/api/agent-knowledge/create",
            data={"agentId": aid, "title": "Legacy", "type": "DOCUMENT"},
            files={"file": ("test.doc", Path(sample).read_bytes())},
        ).json()["data"]
        assert row["embeddingStatus"] == "COMPLETED", row
        assert client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "document"}).json()[
            "data"
        ]


def test_xls_import_partial_json_errors_and_embedding_failure_recovery(
    model_server, business_mysql_db
):
    import xlwt

    with TestClient(create_app()) as client:
        aid, _, _ = _setup_agent_and_model(client, model_server, business_mysql_db)
        activate_embedding(client, model_server)
        book = xlwt.Workbook()
        sheet = book.add_sheet("Import")
        for r, values in enumerate(
            [["表名*", "字段名*", "业务名称*", "数据类型*"], ["sales", "amount", "GMV", "decimal"]]
        ):
            for c, value in enumerate(values):
                sheet.write(r, c, value)
        output = io.BytesIO()
        book.save(output)
        result = client.post(
            "/api/semantic-model/import/excel",
            data={"agentId": aid},
            files={"file": ("import.xls", output.getvalue())},
        ).json()["data"]
        assert result["successCount"] == 1
        model = client.get("/api/model-config/list").json()["data"][0]
        model["apiKey"] = "wrong"
        client.put("/api/model-config/update", json=model)
        row = client.post(
            "/api/agent-knowledge/create",
            data={
                "agentId": aid,
                "title": "Policy",
                "type": "QA",
                "question": "GMV?",
                "content": "Paid sales only",
            },
        ).json()["data"]
        assert row["embeddingStatus"] == "FAILED"
        assert "HTTP 401" in row["errorMsg"]
        assert not client.post(
            f"/api/agent/{aid}/knowledge/search", json={"query": "GMV", "kinds": ["document"]}
        ).json()["data"]
        model["apiKey"] = "fixture-key"
        client.put("/api/model-config/update", json=model)
        client.post("/api/agent-knowledge/retry-embedding/" + str(row["id"]))
        assert (
            client.get("/api/agent-knowledge/" + str(row["id"])).json()["data"]["embeddingStatus"]
            == "COMPLETED"
        )
        result = client.post(
            "/api/semantic-model/batch-import",
            json={
                "agentId": aid,
                "items": [
                    {
                        "tableName": "sales",
                        "columnName": "region",
                        "businessName": "Region",
                        "dataType": "varchar",
                    },
                    {"tableName": "sales"},
                ],
            },
        ).json()["data"]
        assert result["total"] == 2 and result["successCount"] == 1 and result["failCount"] == 1
        assert result["errors"]


def test_import_continues_after_database_rejects_a_row(model_server, business_mysql_db):
    with TestClient(create_app()) as client:
        aid, _, _ = _setup_agent_and_model(client, model_server, business_mysql_db)
        activate_embedding(client, model_server)
        row = {
            "tableName": "sales",
            "columnName": "amount",
            "businessName": "Revenue",
            "dataType": "decimal",
        }
        result = client.post(
            "/api/semantic-model/batch-import",
            json={
                "agentId": aid,
                "items": [
                    row,
                    {**row, "columnName": "bad", "synonyms": "x" * 70000},
                    {**row, "columnName": "region", "businessName": "Region"},
                ],
            },
        ).json()["data"]
        assert result["total"] == 3 and result["successCount"] == 2 and result["failCount"] == 1
        saved = client.get("/api/semantic-model", params={"agentId": aid}).json()["data"]
        assert {item["columnName"] for item in saved} == {"amount", "region"}


def test_query_sse_recalls_evidence_with_enabled_and_selected_table_filters(
    model_server, controlled_chat_server, business_mysql_db
):
    import json

    from test_stream_query_http import _parse_sse

    chat_url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, chat_url, business_mysql_db)
        activate_embedding(client, model_server)
        client.post(
            "/api/business-knowledge",
            json={"agentId": aid, "businessTerm": "GMV", "description": "Paid sales revenue"},
        )
        client.post(
            "/api/semantic-model",
            json={
                "agentId": aid,
                "tableName": "sales",
                "columnName": "amount",
                "businessName": "Revenue",
                "dataType": "decimal",
            },
        )
        client.post(
            "/api/semantic-model",
            json={
                "agentId": aid,
                "tableName": "unauthorized",
                "columnName": "secret",
                "businessName": "Private",
                "dataType": "decimal",
            },
        )
        doc = client.post(
            "/api/agent-knowledge/create",
            data={
                "agentId": aid,
                "title": "Rules",
                "type": "QA",
                "question": "GMV?",
                "content": "Paid revenue only",
            },
        ).json()["data"]
        stream = client.get(
            "/api/stream/search",
            params={"agentId": aid, "conversationId": sid, "query": "GMV by region"},
        )
        events = _parse_sse(stream.text)
        assert events[-1][0] == "complete", stream.text
        evidence = [
            e
            for name, e in events
            if name == "message" and e.get("nodeName") == "EvidenceRecallNode"
        ]
        assert evidence
        hits = json.loads(evidence[0]["text"])
        assert {h["kind"] for h in hits} == {"business", "semantic", "document"}
        assert all(h.get("tableName") != "unauthorized" for h in hits)
        assert evidence[0]["stepId"] and evidence[0]["attempt"] == 1
        client.put("/api/agent-knowledge/recall/" + str(doc["id"]), params={"isRecall": False})
        policy = client.put(
            f"/api/agent/{aid}/knowledge/recall-config",
            json={"topK": 1, "similarityThreshold": 0.5},
        ).json()["data"]
        assert policy["revision"] == 1
        assert (
            len(
                client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "GMV"}).json()[
                    "data"
                ]
            )
            == 1
        )


def test_documents_shared_file_parse_error_retry_and_avatar(model_server):
    from PIL import Image

    with TestClient(create_app()) as client:
        activate_embedding(client, model_server)
        aid = client.post("/api/agent", json={"name": "Docs"}).json()["id"]
        other = client.post("/api/agent", json={"name": "Other"}).json()["id"]
        created = []
        for owner in (aid, other):
            row = client.post(
                "/api/agent-knowledge/create",
                data={
                    "agentId": owner,
                    "title": "Refund rules",
                    "type": "DOCUMENT",
                    "splitterType": "sentence",
                },
                files={"file": ("rules.md", b"Refunds reduce paid revenue.", "text/markdown")},
            ).json()["data"]
            assert row["embeddingStatus"] == "COMPLETED"
            created.append(row)
        url = created[0]["fileUrl"]
        assert url == created[1]["fileUrl"]
        client.delete("/api/agent-knowledge/" + str(created[0]["id"]))
        assert client.get(url).content == b"Refunds reduce paid revenue."
        page = client.post(
            "/api/agent-knowledge/query/page", json={"agentId": other, "type": "DOCUMENT"}
        ).json()
        assert page["total"] == 1 and page["totalPages"] == 1
        empty_filters = client.post(
            "/api/agent-knowledge/query/page",
            json={
                "agentId": other,
                "title": "",
                "type": "",
                "embeddingStatus": "",
                "pageNum": 1,
                "pageSize": 10,
            },
        )
        assert empty_filters.status_code == 200 and empty_filters.json()["total"] == 1
        damaged = client.post(
            "/api/agent-knowledge/create",
            data={"agentId": aid, "title": "Bad", "type": "DOCUMENT"},
            files={"file": ("bad.pdf", b"corrupt pdf", "application/pdf")},
        ).json()["data"]
        assert damaged["embeddingStatus"] == "FAILED"
        assert damaged["errorMsg"]
        # Retry must not falsely mark an unreadable document as searchable.
        client.post("/api/agent-knowledge/retry-embedding/" + str(damaged["id"]))
        assert (
            client.get("/api/agent-knowledge/" + str(damaged["id"])).json()["data"][
                "embeddingStatus"
            ]
            == "FAILED"
        )
        image = Image.new("RGB", (8, 8), "blue")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        avatar = client.post(
            "/api/upload/avatar", files={"file": ("face.png", buf.getvalue(), "image/png")}
        ).json()
        assert avatar["success"]
        read = client.get(avatar["url"])
        assert read.content == buf.getvalue() and read.headers["content-type"] == "image/png"
        assert "inline" in read.headers["content-disposition"]
        assert not client.post(
            "/api/upload/avatar", files={"file": ("bad.png", b"no", "image/png")}
        ).json()["success"]
        assert client.get("/api/upload/files/knowledge/%2e%2e/%2e%2e/.env").status_code == 403
    with TestClient(create_app()) as client:
        assert client.get(url).status_code == 200
        client.delete("/api/agent-knowledge/" + str(created[1]["id"]))
        assert client.get(url).status_code == 404


def test_semantic_excel_upsert_enable_and_batch_delete(model_server, business_mysql_db):
    with TestClient(create_app()) as client:
        aid, _, _ = _setup_agent_and_model(client, model_server, business_mysql_db)
        activate_embedding(client, model_server)
        item = {
            "tableName": "sales",
            "columnName": "amount",
            "businessName": "Revenue",
            "dataType": "decimal",
            "businessDescription": "Paid amount",
        }
        assert (
            client.post("/api/semantic-model", json={**item, "agentId": aid}).json()["data"] is True
        )
        row = client.get("/api/semantic-model", params={"agentId": aid}).json()["data"][0]
        identifier = row["id"]
        assert row["embeddingStatus"] == "COMPLETED"
        assert client.put("/api/semantic-model/disable", json=[identifier]).json()["success"]
        assert (
            client.post(f"/api/agent/{aid}/knowledge/search", json={"query": "Revenue"}).json()[
                "data"
            ]
            == []
        )
        client.put("/api/semantic-model/enable", json=[identifier])
        item["businessName"] = "Net revenue"
        imported = client.post(
            "/api/semantic-model/batch-import", json={"agentId": aid, "items": [item]}
        ).json()["data"]
        assert imported["successCount"] == 1
        assert len(client.get("/api/semantic-model", params={"agentId": aid}).json()["data"]) == 1
        template = client.get("/api/semantic-model/template/download")
        assert template.status_code == 200
        assert "semantic_model_template.xlsx" in template.headers["content-disposition"]
        book = load_workbook(io.BytesIO(template.content))
        sheet = book.active
        assert [sheet.cell(1, c).value for c in range(1, 5)] == [
            "表名*",
            "字段名*",
            "业务名称*",
            "数据类型*",
        ]
        sheet.delete_rows(2, sheet.max_row)
        sheet.append(["sales", "region", "Region", "varchar", "", "Sales region"])
        output = io.BytesIO()
        book.save(output)
        result = client.post(
            "/api/semantic-model/import/excel",
            data={"agentId": aid},
            files={"file": ("semantic.xlsx", output.getvalue())},
        ).json()["data"]
        assert result["successCount"] == 1
        invalid = client.post(
            "/api/semantic-model/import/excel",
            data={"agentId": aid},
            files={"file": ("bad.xlsx", b"not a workbook")},
        ).json()
        assert invalid["success"] is False
        ids = [
            r["id"]
            for r in client.get("/api/semantic-model", params={"agentId": aid}).json()["data"]
        ]
        assert len(ids) == 2
        assert client.request("DELETE", "/api/semantic-model/batch", json=ids).json()["success"]
        assert client.get("/api/semantic-model", params={"agentId": aid}).json()["data"] == []


def activate_embedding(client, model_url):
    assert client.post(
        "/api/model-config/add",
        json={
            "provider": "openai",
            "baseUrl": model_url,
            "apiKey": "fixture-key",
            "modelName": "embedding",
            "modelType": "EMBEDDING",
            "embeddingsPath": "/custom/embed",
        },
    ).json()["success"]
    identifier = client.get("/api/model-config/list").json()["data"][0]["id"]
    assert client.post(f"/api/model-config/activate/{identifier}").json()["success"]


def test_business_failure_retry_recall_update_delete_and_restart(model_server):
    with TestClient(create_app()) as client:
        agent_id = client.post("/api/agent", json={"name": "Knowledge"}).json()["id"]
        body = {
            "agentId": agent_id,
            "businessTerm": "GMV",
            "description": "已支付订单金额",
            "synonyms": "成交额",
        }
        created = client.post("/api/business-knowledge", json=body)
        assert created.status_code == 200
        row = created.json()["data"]
        assert row["embeddingStatus"] == "FAILED"
        assert row["errorMsg"]
        identifier = row["id"]
        activate_embedding(client, model_server)
        assert client.post(f"/api/business-knowledge/retry-embedding/{identifier}").json()[
            "success"
        ]
        assert (
            client.get(f"/api/business-knowledge/{identifier}").json()["data"]["embeddingStatus"]
            == "COMPLETED"
        )
        result = client.post(
            f"/api/agent/{agent_id}/knowledge/search", json={"query": "成交额"}
        ).json()["data"]
        assert result[0]["content"].find("已支付订单金额") >= 0
    with TestClient(create_app()) as client:
        result = client.post(
            f"/api/agent/{agent_id}/knowledge/search", json={"query": "GMV"}
        ).json()["data"]
        assert len(result) == 1
        client.post(f"/api/business-knowledge/recall/{identifier}", params={"isRecall": False})
        assert (
            client.post(f"/api/agent/{agent_id}/knowledge/search", json={"query": "GMV"}).json()[
                "data"
            ]
            == []
        )
        body["description"] = "扣除退款的成交额"
        client.put(f"/api/business-knowledge/{identifier}", json=body)
        client.post(f"/api/business-knowledge/recall/{identifier}", params={"isRecall": True})
        result = client.post(
            f"/api/agent/{agent_id}/knowledge/search", json={"query": "GMV"}
        ).json()["data"]
        assert "扣除退款" in result[0]["content"]
        client.post("/api/business-knowledge/refresh-vector-store", params={"agentId": agent_id})
        assert (
            len(
                client.post(
                    f"/api/agent/{agent_id}/knowledge/search", json={"query": "GMV"}
                ).json()["data"]
            )
            == 1
        )
        client.delete(f"/api/business-knowledge/{identifier}")
        assert (
            client.post(f"/api/agent/{agent_id}/knowledge/search", json={"query": "GMV"}).json()[
                "data"
            ]
            == []
        )
