"""Full graph exits and bounded repair through HTTP/SSE and durable results."""

# ruff: noqa: F401, F811
import pytest
from fastapi.testclient import TestClient
from test_stream_query_http import (
    _parse_sse,
    _setup_agent_and_model,
    business_mysql_db,
    controlled_chat_server,
)

from app.main import create_app


@pytest.mark.parametrize('mode', ['report_error', 'empty_result'])
def test_report_failure_and_empty_results_are_explicit(
    business_mysql_db, controlled_chat_server, mode,
):
    url, state = controlled_chat_server
    state['mode'] = mode
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        events = _parse_sse(client.get('/api/stream/search', params={
            'agentId': aid, 'conversationId': sid, 'query': '销售额报告',
        }).text)
        tid = events[-1][1]['threadId']
        result = client.get(f'/api/sessions/{sid}/runs/{tid}').json()['data']['result']
        if mode == 'report_error':
            assert events[-1][0] == 'error'
            assert result['outcome'] == 'FAILED'
            assert not result['artifacts']
        else:
            assert events[-1][0] == 'complete'
            assert result['artifacts']['resultSet']['data'] == []
            assert '没有数据' in result['artifacts']['report']['content']
            request = next(r for r in state['requests'] if r.get('stream'))
            assert '"data": []' in request['messages'][-1]['content']


@pytest.mark.parametrize(
    "mode,terminal",
    [
        ("many_steps", "complete"),
        ("empty_enhance", "complete"),
        ("empty_schema", "complete"),
        ("invalid_relation", "error"),
    ],
)
def test_review_regressions_have_bounded_and_correct_exits(
    business_mysql_db,
    controlled_chat_server,
    mode,
    terminal,
):
    url, state = controlled_chat_server
    state["mode"] = mode
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        events = _parse_sse(
            client.get(
                "/api/stream/search",
                params={
                    "agentId": aid,
                    "conversationId": sid,
                    "query": "销售额",
                },
            ).text
        )
        assert events[-1][0] == terminal, events[-1]
        if mode == "many_steps":
            executed = [e for _, e in events if e.get("nodeName") == "SqlExecuteNode"]
            assert len(executed) == 11
        if mode in {"empty_schema", "empty_enhance"}:
            assert all(e.get("nodeName") != "SqlExecuteNode" for _, e in events)
            tid = events[-1][1]["threadId"]
            snapshot = client.get(f"/api/sessions/{sid}/runs/{tid}").json()["data"]["result"]
            assert snapshot["outcome"] == "EARLY_END"
        if mode == "invalid_relation":
            assert (
                sum(
                    r["messages"][0]["content"].startswith("[TableRelationNode]")
                    for r in state["requests"]
                )
                == 4
            )


@pytest.mark.parametrize("mode,outcome", [("chat", "EARLY_END"), ("forecast", "UNSUPPORTED")])
def test_early_exit_has_durable_answer_and_no_query_or_report(
    business_mysql_db,
    controlled_chat_server,
    mode,
    outcome,
):
    url, state = controlled_chat_server
    state["mode"] = mode
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        events = _parse_sse(
            client.get(
                "/api/stream/search",
                params={
                    "agentId": aid,
                    "conversationId": sid,
                    "query": "你好或使用预测库训练销量模型",
                },
            ).text
        )
        assert events[-1][0] == "complete"
        assert events[-2][1]["eventType"] == "FINAL_ANSWER"
        assert all(
            e.get("nodeName") not in {"SqlExecuteNode", "ReportGeneratorNode"} for _, e in events
        )
        tid = events[-1][1]["threadId"]
        snapshot = client.get(f"/api/sessions/{sid}/runs/{tid}").json()["data"]["result"]
        assert snapshot["outcome"] == outcome and snapshot["finalAnswer"]


@pytest.mark.parametrize(
    "mode,success",
    [
        ("repair_sql", True),
        ("repair_plan", True),
        ("unknown_tool", False),
        ("inconsistent", False),
    ],
)
def test_repairs_finish_with_a_single_terminal_event(
    business_mysql_db,
    controlled_chat_server,
    mode,
    success,
):
    url, state = controlled_chat_server
    state["mode"] = mode
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        events = _parse_sse(
            client.get(
                "/api/stream/search",
                params={
                    "agentId": aid,
                    "conversationId": sid,
                    "query": "按区域统计销售额",
                },
            ).text
        )
        assert [name for name, _ in events if name in {"complete", "error"}] == [
            "complete" if success else "error"
        ], events[-1]
        assert len(state["requests"]) < 40
        if success:
            attempts = [e for _, e in events if e.get("nodeName") == "SqlGenerateNode"]
            expected_attempts = [1, 2] if mode == 'repair_sql' else [1]
            assert [e["attempt"] for e in attempts] == expected_attempts
            assert len({e["stepId"] for e in attempts}) == len(expected_attempts)
            if mode == 'repair_plan':
                planner_calls = [r for r in state['requests']
                                 if r['messages'][0]['content'].startswith('[PlannerNode]')]
                assert len(planner_calls) == 2
                assert '"tool":' in planner_calls[1]['messages'][0]['content']
            tid = events[-1][1]["threadId"]
            result = client.get(f"/api/sessions/{sid}/runs/{tid}").json()["data"]["result"]
            report = result["artifacts"]["report"]
            downloaded = client.get(report["url"])
            assert downloaded.status_code == 200
            assert report["content"] in downloaded.text
            assert "text/html" in downloaded.headers["content-type"]


def test_report_stream_and_snapshot_survive_restart(business_mysql_db, controlled_chat_server):
    url, state = controlled_chat_server
    state["mode"] = "stream_report"
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        events = _parse_sse(
            client.get(
                "/api/stream/search",
                params={
                    "agentId": aid,
                    "conversationId": sid,
                    "query": "销售额报告",
                },
            ).text
        )
        assert events[-1][0] == "complete"
        tid = events[-1][1]["threadId"]
        chunks = [e for _, e in events if e.get("nodeName") == "ReportGeneratorNode"]
        assert len(chunks) == 2
        assert len({e["stepId"] for e in chunks}) == 1
        assert all(e["textType"] == "HTML" for e in chunks)
    with TestClient(create_app()) as client:
        result = client.get(f"/api/sessions/{sid}/runs/{tid}").json()["data"]["result"]
        report = result["artifacts"]["report"]
        assert len(result['messages']) == 1
        assert result['messages'][0]['messageType'] == 'html'
        assert report["content"] == "".join(e["text"] for e in chunks)
        assert report["content"] in client.get(report["url"]).text
        message = next(m for m in result["messages"] if m["messageType"] == "html")
        message["metadata"]["messageKey"] = message.pop("messageKey")
        for _ in range(2):
            assert client.post(f"/api/sessions/{sid}/messages", json=message).status_code == 200
        assert len(client.get(f"/api/sessions/{sid}/messages").json()) == 1


def test_nl2sql_runs_validation_and_query_without_report_or_review(
    business_mysql_db,
    controlled_chat_server,
):
    url, _ = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        events = _parse_sse(
            client.get(
                "/api/stream/search",
                params={
                    "agentId": aid,
                    "conversationId": sid,
                    "query": "销售额",
                    "nl2sqlOnly": True,
                    "humanFeedback": True,
                },
            ).text
        )
        assert events[-1][0] == "complete"
        nodes = {event.get("nodeName") for _, event in events}
        assert {"SemanticConsistencyNode", "SqlExecuteNode"} <= nodes
        assert "ReportGeneratorNode" not in nodes
        assert not any(e.get("eventType") == "HUMAN_FEEDBACK_REQUIRED" for _, e in events)
