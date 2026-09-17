"""M4 · 质量链路图测试：stage5→6(一致性+auto-fix)→7(记忆)→下一章。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from novel_agent.config import load_config
from novel_agent.graph import compile_graph

MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  writer:   { model: "m-writer", api_key_env: "K3" }
  cheap:    { model: "m-cheap", api_key_env: "K2" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000, check: 8000 }
memory: { short_window: 3 }
rag: { top_k: 4 }
library: { personality_top_k: 3 }
"""


def _graph(thread: str, project_root: Path | None = None):
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    cfg = load_config(p)
    graph = compile_graph(cfg, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": thread}}
    state = {"project_id": thread, "project_root": str(project_root or Path(tempfile.mkdtemp())),
             "genre": "short_story", "title": "测试",
             "user_idea": "旧书店失忆少女", "messages": []}
    return graph, config, state


def _resume(graph, config: dict, action: dict):
    graph.invoke(Command(resume=action), config)


def _resume_stage(graph, config: dict, target: str, cap: int = 40):
    """推进直到当前挂起点为 target，返回其 interrupt 载荷。"""
    for _ in range(cap):
        st = graph.get_state(config)
        info = st.tasks[-1].interrupts[-1].value
        if info["stage"] == target:
            return info
        _resume(graph, config, {"action": "accept"})
    raise AssertionError(f"未推进到 {target}")


def _accept_until_done(graph, config: dict, cap: int = 200) -> dict:
    for _ in range(cap):
        st = graph.get_state(config)
        if not st.next:
            return st.values
        _resume(graph, config, {"action": "accept"})
    raise AssertionError("未能在限制内完成")


def test_auto_fix_converges_in_chain():
    """注入"设定矛盾"，stage6 自动修复，无需人工。"""
    graph, config, state = _graph("m4_fix")
    graph.invoke(state, config)
    info = _resume_stage(graph, config, "stage5")
    # 注入矛盾标记
    _resume(graph, config, {"action": "edit", "data": {"scene_id": "s1", "instruction": "这里存在设定矛盾"}})
    values = _accept_until_done(graph, config)
    # 修复后正文不再含矛盾标记
    ch1 = values["chapters"]["1_1"]
    assert "设定矛盾" not in ch1["scenes"][0]["text"]
    assert "设定一致" in ch1["scenes"][0]["text"]


def test_human_interrupt_when_unfixable():
    """注入"风格漂移"（不可自动修复）→ 3 次 auto-fix 后转人工确认点。"""
    graph, config, state = _graph("m4_human")
    graph.invoke(state, config)
    info = _resume_stage(graph, config, "stage5")
    _resume(graph, config, {"action": "edit", "data": {"scene_id": "s1", "instruction": "此处风格漂移"}})
    info = _resume_stage(graph, config, "stage6")  # 人工确认点
    assert info["payload"]["needs_human"] is True
    assert info["payload"]["auto_fix_attempts"] == 3
    # 人工接受后继续
    _resume(graph, config, {"action": "accept"})
    values = _accept_until_done(graph, config)
    assert len(values["chapters"]) == 6


def test_memory_updated_per_chapter():
    root = Path(tempfile.mkdtemp())
    graph, config, state = _graph("m4_mem", project_root=root)
    graph.invoke(state, config)
    _accept_until_done(graph, config)
    # 中期记忆：6 章摘要
    mid = root / "data" / "projects" / "m4_mem" / "memory" / "mid_term.json"
    assert mid.exists()
    # 长期记忆非空
    lt = root / "data" / "projects" / "m4_mem" / "vector_stores" / "long_term.json"
    assert lt.exists()
    # 时序图谱有边（主角×伙伴互动）
    tg = root / "data" / "projects" / "m4_mem" / "temporal_graph" / "graph.json"
    assert tg.exists()
    assert "edges" in tg.read_text(encoding="utf-8")
