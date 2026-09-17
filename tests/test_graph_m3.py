"""M3 · 写作链路图测试：卷细纲→章packet→正文循环 + 每章确认 + 定点修改。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from novel_agent.config import load_config
from novel_agent.graph import compile_graph

# short_story：1 卷 × 6 章，确认点可控
MINIMAL_CONFIG = """\
genre: short_story
llm:
  creative: { model: "m-creative", api_key_env: "K1" }
  writer:   { model: "m-writer", api_key_env: "K3" }
  cheap:    { model: "m-cheap", api_key_env: "K2" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000 }
library: { personality_top_k: 3 }
"""


def _graph(thread: str):
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    cfg = load_config(p)
    graph = compile_graph(cfg, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": thread}}
    state = {"project_id": thread, "project_root": str(Path(tempfile.mkdtemp())),
             "genre": "short_story", "title": "测试",
             "user_idea": "深夜咖啡馆的失忆少女", "messages": []}
    return graph, config, state


def _accept_until_done(graph, config: dict, cap: int = 200) -> dict:
    for _ in range(cap):
        st = graph.get_state(config)
        if not st.next:
            return st.values
        graph.invoke(Command(resume={"action": "accept"}), config)
    raise AssertionError(f"未能在 {cap} 次确认内完成")


def test_writing_chain_completes():
    graph, config, state = _graph("m3_chain")
    graph.invoke(state, config)
    values = _accept_until_done(graph, config)
    # 6 章全部写完
    assert len(values["chapters"]) == 6
    assert set(values["chapters"].keys()) == {f"1_{i}" for i in range(1, 7)}
    assert len(values["writer_packets"]) == 6
    # 每章有场景块
    for key, ch in values["chapters"].items():
        assert len(ch["scenes"]) >= 2


def test_confirmation_order():
    graph, config, state = _graph("m3_order")
    graph.invoke(state, config)
    seen = []
    for _ in range(40):
        st = graph.get_state(config)
        if not st.next:
            break
        info = st.tasks[-1].interrupts[-1].value
        seen.append(info["stage"])
        graph.invoke(Command(resume={"action": "accept"}), config)
    # 创意 5 个确认点 + 每章 4b/5
    assert seen[:5] == ["stage0", "stage1", "stage2", "stage3", "stage4a"]
    assert seen[5:7] == ["stage4b", "stage5"]


def test_scene_edit_in_chain():
    graph, config, state = _graph("m3_scene")
    graph.invoke(state, config)
    # 推进到第一个 stage5
    for _ in range(6):
        st = graph.get_state(config)
        if st.tasks[-1].interrupts[-1].value["stage"] == "stage5":
            break
        graph.invoke(Command(resume={"action": "accept"}), config)
    st = graph.get_state(config)
    info = st.tasks[-1].interrupts[-1].value
    assert info["stage"] == "stage5"
    # 定点修改 s1
    graph.invoke(Command(resume={"action": "edit", "data": {"scene_id": "s1", "instruction": "改柔和"}}), config)
    values = _accept_until_done(graph, config)
    ch1 = values["chapters"]["1_1"]
    assert "改柔和" in ch1["scenes"][0]["text"]
    # 其余场景未被改动（mock 生成的原始文本仍在）
    assert ch1["scenes"][1]["text"].startswith("（第1章）冲突升级")


def test_quit_then_resume():
    graph, config, state = _graph("m3_resume")
    graph.invoke(state, config)
    # 走到 stage5 后 "退出"
    for _ in range(6):
        st = graph.get_state(config)
        if st.tasks[-1].interrupts[-1].value["stage"] == "stage5":
            break
        graph.invoke(Command(resume={"action": "accept"}), config)
    st = graph.get_state(config)
    assert st.next  # 挂起中
    # 等价于重跑 project run：直接用原 graph 从 checkpoint 续写
    graph.invoke(Command(resume={"action": "accept"}), config)
    values = _accept_until_done(graph, config)
    assert len(values["chapters"]) == 6
