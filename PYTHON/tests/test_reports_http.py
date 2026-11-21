"""Report export contract through the public HTTP boundary."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_html_export_preserves_unicode_and_rejects_empty_content():
    with TestClient(create_app()) as client:
        aid = client.post("/api/agent", json={"name": "reports"}).json()["id"]
        sid = client.post(f"/api/agent/{aid}/sessions").json()["id"]
        url = f"/api/sessions/{sid}/reports/html"
        response = client.post(
            url, content="<h1>销售额</h1>", headers={"Content-Type": "text/plain;charset=UTF-8"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert ".html" in response.headers["content-disposition"]
        assert "<h1>销售额</h1>" in response.text
        assert "<!doctype html>" in response.text.lower()
        assert client.post(url, content="  ").status_code == 400
        assert client.post(url, content=b"\xff").status_code == 400
