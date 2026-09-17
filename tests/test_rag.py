"""M4 · F09 双 RAG 测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from novel_agent.memory import LongTermMemory
from novel_agent.rag import TemporalGraph, retrieve


def _tmp() -> Path:
    return Path(tempfile.mkdtemp())


def test_temporal_graph_add_and_persist():
    path = _tmp() / "graph.json"
    g = TemporalGraph(path)
    g.add_edge("莫长老", "主角", "敌人", chapter=3, note="初遇即敌")
    g.add_edge("莫长老", "主角", "盟友", chapter=20, note="化敌为友")
    g2 = TemporalGraph(path)
    assert len(g2) == 2
    # 时序感知：第5章仍是敌人
    rel5 = {r["kind"] for r in g2.neighbors("莫长老", 5)}
    assert rel5 == {"敌人"}
    # 第20章已成盟友
    rel20 = {r["kind"] for r in g2.neighbors("莫长老", 20)}
    assert rel20 == {"敌人", "盟友"}


def test_temporal_graph_evolution():
    path = _tmp() / "graph.json"
    g = TemporalGraph(path)
    g.add_edge("A", "B", "敌人", 3)
    g.add_edge("A", "B", "盟友", 20)
    ev = g.evolution("A", "B")
    assert [e["chapter"] for e in ev] == [3, 20]
    assert [e["kind"] for e in ev] == ["敌人", "盟友"]


def test_retrieve_combines_vector_and_graph():
    path = _tmp()
    long_term = LongTermMemory(path / "long_term.json")
    long_term.add(["主角在雨夜习得剑法"])
    graph = TemporalGraph(path / "graph.json")
    graph.add_edge("主角", "师父", "师徒", chapter=1)

    ctx = retrieve(["剑法", "主角"], long_term, graph, top_k=2, current_chapter=2)
    assert "剑法" in ctx
    assert "师徒" in ctx
    assert "主角→师父" in ctx


def test_retrieve_respects_chapter():
    path = _tmp()
    long_term = LongTermMemory(path / "long_term.json")
    graph = TemporalGraph(path / "graph.json")
    graph.add_edge("主角", "师父", "师徒", chapter=10)
    ctx = retrieve(["主角"], long_term, graph, top_k=2, current_chapter=5)
    assert "师徒" not in ctx  # 第5章时关系尚未建立
