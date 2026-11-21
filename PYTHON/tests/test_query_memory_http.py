"""Successful query context survives a new graph thread and application restart."""

# ruff: noqa: F401, F811
import json

from fastapi.testclient import TestClient
from test_stream_query_http import (
    _setup_agent_and_model,
    business_mysql_db,
    controlled_chat_server,
)

from app.main import create_app


def test_followup_reads_successful_plan_but_not_failed_turn(
    business_mysql_db,
    controlled_chat_server,
):
    url, state = controlled_chat_server
    with TestClient(create_app()) as client:
        aid, sid, _ = _setup_agent_and_model(client, url, business_mysql_db)
        params = {"agentId": aid, "conversationId": sid, "query": "FIRST_SUCCESS_销售额"}
        assert "event: complete" in client.get("/api/stream/search", params=params).text
        state["mode"] = "provider_error"
        assert (
            "event: error"
            in client.get(
                "/api/stream/search",
                params={
                    **params,
                    "query": "FAILED_TURN_不应记住",
                },
            ).text
        )
    state["mode"] = "normal"
    state["requests"].clear()
    with TestClient(create_app()) as client:
        response = client.get("/api/stream/search", params={**params, "query": "那西部呢"})
        assert "event: complete" in response.text
        for node in (
            "IntentRecognitionNode",
            "QueryEnhanceNode",
            "TableRelationNode",
            "FeasibilityAssessmentNode",
            "PlanExecutorNode",
            "SemanticConsistencyNode",
        ):
            assert node in response.text
        sent = json.dumps(state["requests"], ensure_ascii=False)
        assert "FIRST_SUCCESS_销售额" in sent
        assert "FAILED_TURN_不应记住" not in sent
