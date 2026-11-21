"""Verify the pinned saver by interrupting and resuming in separate processes."""

import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    question: str
    approved: bool


def review(state: State):
    decision = interrupt({"planRevision": 1, "question": state["question"]})
    return {"approved": decision}


async def phase(path: str, action: str):
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        await saver.setup()
        graph = StateGraph(State)
        graph.add_node("review", review)
        graph.add_edge(START, "review")
        graph.add_edge("review", END)
        runnable = graph.compile(checkpointer=saver)
        config: RunnableConfig = {"configurable": {"thread_id": "ticket01-saver-compatibility"}}
        if action == "interrupt":
            initial: State = {"question": "Review this plan", "approved": False}
            await runnable.ainvoke(initial, config)
            saved = await runnable.aget_state(config)
            assert saved.next == ("review",)
            assert saved.tasks[0].interrupts[0].value["planRevision"] == 1
        else:
            before = await runnable.aget_state(config)
            assert before.values["question"] == "Review this plan"
            result = await runnable.ainvoke(Command(resume=True), config)
            assert result["approved"] is True
            assert not (await runnable.aget_state(config)).next


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["interrupt", "resume"])
    parser.add_argument("--path")
    args = parser.parse_args()
    if args.phase:
        asyncio.run(phase(args.path, args.phase))
    else:
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "checkpoints.sqlite")
            for action in ("interrupt", "resume"):
                subprocess.run(
                    [sys.executable, __file__, "--phase", action, "--path", path], check=True
                )
        print("Persistent interrupt resumed successfully in a second process")
