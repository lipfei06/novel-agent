"""M1 · F04 LangGraph 图基础测试（M2 起图需要 cfg + mock）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.types import Command

from novel_agent.config import load_config
from novel_agent.graph import STAGES, build_graph, compile_graph

MINIMAL_CONFIG = """\
genre: webnovel
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000 }
library: { personality_top_k: 3 }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def test_stages_list():
    assert "stage0" in STAGES
    assert len(STAGES) == 11  # stage0-9 + 4a/4b


def test_build_graph_is_statgraph():
    assert isinstance(build_graph(_cfg()), StateGraph)


def test_graph_compiles_and_runs():
    graph = compile_graph(_cfg())
    config = {"configurable": {"thread_id": "g1"}}
    graph.invoke(
        {"project_id": "p1", "project_root": str(Path(tempfile.mkdtemp())), "messages": [], "user_idea": "测试"},
        config,
    )
    st = graph.get_state(config)
    assert st.next  # 停在第 1 个确认点
    graph.invoke(Command(resume={"action": "accept"}), config)
    values = graph.get_state(config).values
    assert values.get("concept")


def test_graph_checkpoint_persists_state():
    mem = MemorySaver()
    graph = compile_graph(_cfg(), checkpointer=mem)
    config = {"configurable": {"thread_id": "g2"}}
    graph.invoke({"project_id": "p1", "project_root": str(Path(tempfile.mkdtemp())), "messages": [], "user_idea": "x"}, config)
    state = graph.get_state(config)
    assert state.next
    # 重新构造图也能从 checkpoint 读回（同一 checkpointer）
    graph2 = compile_graph(_cfg(), checkpointer=mem)
    state2 = graph2.get_state(config)
    assert state2.next
