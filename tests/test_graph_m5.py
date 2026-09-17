"""M5 · 收尾链路图测试：审校→导出 + SQLite 断点续写（跨实例）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from langgraph.types import Command

from novel_agent.config import load_config
from novel_agent.graph import compile_graph, compile_persistent_graph

MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  writer:   { model: "m-writer", api_key_env: "K3" }
  cheap:    { model: "m-cheap", api_key_env: "K2" }
  editor:   { model: "m-editor", api_key_env: "K4" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000, check: 8000, editorial: 10000 }
memory: { short_window: 3 }
rag: { top_k: 4 }
library: { personality_top_k: 3 }
export: { epub: true }
"""


def _cfg():
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    return load_config(p)


def _root() -> Path:
    return Path(tempfile.mkdtemp())


def _resume(graph, config: dict, action: dict):
    graph.invoke(Command(resume=action), config)


def _accept_until_done(graph, config: dict, cap: int = 300) -> dict:
    for _ in range(cap):
        st = graph.get_state(config)
        if not st.next:
            return st.values
        _resume(graph, config, {"action": "accept"})
    raise AssertionError("未能在限制内完成")


def test_full_chain_to_export():
    graph = compile_graph(_cfg())
    config = {"configurable": {"thread_id": "m5_full"}}
    state = {"project_id": "m5_full", "project_root": str(_root()), "genre": "short_story",
             "title": "完整流程测试", "user_idea": "x", "messages": []}
    graph.invoke(state, config)
    values = _accept_until_done(graph, config)
    assert values["editorial_report"]["scope"] == "final"
    assert values["final_paths"]
    assert any(f.endswith(".md") for f in values["final_paths"])
    assert any(f.endswith(".txt") for f in values["final_paths"])
    assert any(f.endswith(".epub") for f in values["final_paths"])
    assert values["current_stage"] == "done"


def test_export_files_written_to_disk():
    root = _root()
    graph = compile_graph(_cfg())
    config = {"configurable": {"thread_id": "m5_disk"}}
    state = {"project_id": "m5_disk", "project_root": str(root), "genre": "short_story",
             "title": "落盘测试", "user_idea": "x", "messages": []}
    graph.invoke(state, config)
    values = _accept_until_done(graph, config)
    for path in values["final_paths"]:
        assert Path(path).exists()


def test_sqlite_resume_across_instances():
    """同一 SQLite 库、两个独立编译实例：断点续写。"""
    root = _root()
    db = root / "checkpoint.sqlite"
    cfg = _cfg()
    config = {"configurable": {"thread_id": "m5_sql"}}

    # 实例 A：启动并推进到第 5 章正文确认后停
    graph_a = compile_persistent_graph(cfg, db)
    state = {"project_id": "m5_sql", "project_root": str(root), "genre": "short_story",
             "title": "续写测试", "user_idea": "x", "messages": []}
    graph_a.invoke(state, config)
    for _ in range(15):
        st = graph_a.get_state(config)
        if st.tasks[-1].interrupts[-1].value["stage"] == "stage5":
            break
        _resume(graph_a, config, {"action": "accept"})
    st = graph_a.get_state(config)
    assert st.next  # 挂起在第5章

    # 实例 B：重新编译（模拟新进程），从 checkpoint 续写
    graph_b = compile_persistent_graph(cfg, db)
    st_b = graph_b.get_state(config)
    assert st_b.next  # 能读到中断点
    values = _accept_until_done(graph_b, config)
    assert values["current_stage"] == "done"
    assert len(values["chapters"]) == 6
