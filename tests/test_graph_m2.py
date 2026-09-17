"""M2 · 创意链路图测试：interrupt 确认点 + resume（accept/edit）。

注：M3 起创意链路后接 stage4a，此处验证 stage0-4a 五个创意确认点。
"""
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
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000 }
library: { personality_top_k: 3 }
"""


def _initial(thread: str):
    d = Path(tempfile.mkdtemp())
    p = d / "config.yaml"
    p.write_text(MINIMAL_CONFIG, encoding="utf-8")
    cfg = load_config(p)
    graph = compile_graph(cfg, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": thread}}
    state = {"project_id": thread, "project_root": str(Path(tempfile.mkdtemp())),
             "genre": "short_story", "title": "测试",
             "user_idea": "修仙少年逆天改命", "messages": []}
    return graph, config, state


def _accept(graph, config: dict, times: int) -> dict:
    for _ in range(times):
        st = graph.get_state(config)
        if not st.next:
            break
        graph.invoke(Command(resume={"action": "accept"}), config)
    return graph.get_state(config).values


def test_creative_chain_products():
    graph, config, state = _initial("t_accept")
    graph.invoke(state, config)
    values = _accept(graph, config, 5)  # stage0-4a
    assert values.get("concept")
    assert values.get("world_bible")
    assert values.get("characters")
    assert values.get("outline")
    assert values.get("volume_plans")
    assert values["outline"]["version"] == 1
    msgs = [m for m in values.get("messages", []) if m.startswith("stage")]
    assert len(msgs) == 5  # stage0-4a 各一条


def test_creative_confirmation_points():
    graph, config, state = _initial("t_points")
    graph.invoke(state, config)
    stages = []
    for _ in range(5):
        st = graph.get_state(config)
        if not st.next:
            break
        info = st.tasks[-1].interrupts[-1].value
        stages.append(info["stage"])
        graph.invoke(Command(resume={"action": "accept"}), config)
    assert stages == ["stage0", "stage1", "stage2", "stage3", "stage4a"]


def test_edit_overrides_payload():
    graph, config, state = _initial("t_edit")
    graph.invoke(state, config)
    st = graph.get_state(config)
    info = st.tasks[-1].interrupts[-1].value
    assert info["stage"] == "stage0"
    payload = dict(info["payload"])
    payload["title_idea"] = "被人工修改的立意"
    graph.invoke(Command(resume={"action": "edit", "data": payload}), config)
    values = _accept(graph, config, 6)
    assert values["concept"]["title_idea"] == "被人工修改的立意"


def test_interrupt_payload_shape():
    graph, config, state = _initial("t_shape")
    graph.invoke(state, config)
    st = graph.get_state(config)
    info = st.tasks[-1].interrupts[-1].value
    assert info["stage"] == "stage0"
    assert info["stage_label"] == "选题立项"
    assert "payload" in info
