"""Read only committed question/plan pairs, scoped to Agent and conversation."""

import json

from sqlalchemy import text


def conversation_messages(engine, agent_id: int, conversation_id: str) -> list[dict[str, str]]:
    # Java DataAgentProperties: maxturnhistory=5, maxplanlength=2000.
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT t.question,t.plan FROM agent_conversation_turn t "
                    "JOIN agent_run r ON r.thread_id=t.thread_id "
                    "WHERE t.agent_id=:aid AND t.conversation_id=:cid "
                    "AND t.memory_status='COMMITTED' AND t.plan IS NOT NULL "
                    "ORDER BY r.finished_at DESC,r.thread_id DESC LIMIT 5"
                ),
                {"aid": agent_id, "cid": conversation_id},
            )
            .mappings()
            .all()
        )
    messages = []
    for row in reversed(rows):
        plan = row["plan"]
        content = plan if isinstance(plan, str) else json.dumps(plan, ensure_ascii=False)
        if len(content) > 2000:
            content = content[:1997] + "..."
        messages.extend(
            [
                {"role": "user", "content": row["question"]},
                {"role": "assistant", "content": content},
            ]
        )
    return messages
