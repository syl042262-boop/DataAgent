"""Deterministic provider responses for the graph's structured model interfaces."""

import json
import re


def workflow_reply(messages):
    system = messages[0]["content"] if messages else ""
    query = messages[-1]["content"] if messages else ""
    if system.startswith(("[SchemaRecallNode]", "[TableRelationNode]")):
        return json.dumps(
            {"tableNames": list(dict.fromkeys(re.findall(r'"tableName": "([^"]+)"', system)))}
        )
    if system.startswith("[IntentRecognitionNode]"):
        return json.dumps({"classification": "analysis", "response": ""})
    if system.startswith("[QueryEnhanceNode]"):
        return json.dumps({"canonicalQuery": query, "expandedQueries": [query]})
    if system.startswith("[FeasibilityAssessmentNode]"):
        return json.dumps({"feasible": True, "response": ""})
    if system.startswith("[PlannerNode]"):
        return json.dumps(
            {
                "thought_process": "Query then report",
                "execution_plan": [
                    {
                        "step": 1,
                        "tool_to_use": "SQL_GENERATE_NODE",
                        "tool_parameters": {"instruction": query},
                    },
                    {
                        "step": 2,
                        "tool_to_use": "REPORT_GENERATOR_NODE",
                        "tool_parameters": {"summary_and_recommendations": "Report actual results"},
                    },
                ],
            }
        )
    if system.startswith("[SemanticConsistencyNode]"):
        return json.dumps({"consistent": True, "reason": ""})
    return None
