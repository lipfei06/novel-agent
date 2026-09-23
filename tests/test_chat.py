"""M1 · 创作对话系统测试（mock 模式）。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["NOVEL_ENGINE_MOCK"] = "1"

from fastapi.testclient import TestClient

from novel_agent.api import create_app

CFG = """\
genre: short_story
llm:
  creative: { model: "m", api_key_env: "K1" }
  cheap:    { model: "c", api_key_env: "K2" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000, check: 8000, editorial: 10000, state_update: 4000, character_archive: 4000 }
memory: { short_window: 3 }
rag: { top_k: 4 }
library: { personality_top_k: 3 }
"""


def _client():
    root = Path(tempfile.mkdtemp())
    (root / "config.yaml").write_text(CFG, encoding="utf-8")
    return TestClient(create_app(root))


def test_chat_roundtrip_and_history():
    with _client() as c:
        c.post("/api/projects", json={"title": "聊", "genre": "short_story", "project_id": "pC1"})
        r = c.post("/api/projects/pC1/chat", json={"context": "concept", "message": "我想写真假千金加玄幻"})
        assert r.status_code == 200
        assert r.json()["reply"]
        assert len(r.json()["messages"]) == 2
        # 历史
        hist = c.get("/api/projects/pC1/chat?context=concept").json()["messages"]
        assert len(hist) == 2
        # 再发一条 → 4 条
        c.post("/api/projects/pC1/chat", json={"context": "concept", "message": "再加个身世秘密"})
        hist = c.get("/api/projects/pC1/chat?context=concept").json()["messages"]
        assert len(hist) == 4


def test_chat_propose_concept():
    with _client() as c:
        c.post("/api/projects", json={"title": "议", "genre": "short_story", "project_id": "pC2"})
        c.post("/api/projects/pC2/chat", json={"context": "concept", "message": "帮我把选题聊清楚"})
        r = c.post("/api/projects/pC2/chat/propose", json={"context": "concept", "target": "concept"})
        assert r.status_code == 200
        assert "proposal" in r.json()


def test_chat_propose_chapter_after_writing():
    with _client() as c:
        c.post("/api/projects", json={"title": "章", "genre": "short_story", "project_id": "pC3"})
        # 跑完设定
        c.post("/api/projects/pC3/start", json={"idea": "x"})
        for _ in range(60):
            v = c.post("/api/projects/pC3/confirm", json={"action": "accept"}).json()
            if v["done"] or v["stage"] == "stage4b":
                break
        # 章节场景对话 → 提出章节方案
        r = c.post("/api/projects/pC3/chat", json={"context": "chapter_1_1", "message": "这章怎么写更有张力"})
        assert r.status_code == 200
        r = c.post("/api/projects/pC3/chat/propose", json={"context": "chapter_1_1", "target": "chapter"})
        assert r.status_code == 200


def test_chat_reset_and_unknown_context():
    with _client() as c:
        c.post("/api/projects", json={"title": "清", "genre": "short_story", "project_id": "pC4"})
        c.post("/api/projects/pC4/chat", json={"context": "outline", "message": "hi"})
        assert c.post("/api/projects/pC4/chat/reset?context=outline").status_code == 200
        assert c.get("/api/projects/pC4/chat?context=outline").json()["messages"] == []
        assert c.get("/api/projects/pC4/chat?context=bad").status_code == 400
        assert c.post("/api/projects/nope/chat", json={"context": "concept", "message": "x"}).status_code == 404


def test_chapter_generation_uses_discussion():
    with _client() as c:
        c.post("/api/projects", json={"title": "讨", "genre": "short_story", "project_id": "pC5"})
        # 跑完设定
        c.post("/api/projects/pC5/start", json={"idea": "x"})
        for _ in range(60):
            v = c.post("/api/projects/pC5/confirm", json={"action": "accept"}).json()
            if v["done"] or v["stage"] == "stage4b":
                break
        # 先与 AI 讨论章节
        c.post("/api/projects/pC5/chat", json={"context": "chapter_1_1", "message": "这章我想写身世揭晓"})
        # 提交生成并带 chat_context
        r = c.post("/api/projects/pC5/volumes/1/chapters", json={"goal": "x", "chat_context": "chapter_1_1"})
        assert r.status_code == 200
        assert r.json()["pending"]["scenes"]


def test_chat_stream_sse():
    import json as _json

    with _client() as c:
        c.post("/api/projects", json={"title": "流", "genre": "short_story", "project_id": "pC7"})
        r = c.post("/api/projects/pC7/chat/stream", json={"context": "concept", "message": "聊聊立意"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = [ln[6:] for ln in r.text.splitlines() if ln.startswith("data: ")]
        types = [_json.loads(e)["type"] for e in events]
        assert types == ["token", "done"]  # mock 一次整段 token + done
        # 历史仍整体落盘：1 轮 = 2 条
        hist = c.get("/api/projects/pC7/chat?context=concept").json()["messages"]
        assert len(hist) == 2
        # 非法场景 → 400
        assert c.post("/api/projects/pC7/chat/stream", json={"context": "nope", "message": "x"}).status_code == 400


def test_chat_agent_action_parsing():
    from novel_agent.api.chat import _parse_action, _strip_action

    fenced = '我先查证一下。\n```json\n{"tool": "get_prop_facts", "args": {"name": "玉佩"}}\n```\n'
    a = _parse_action(fenced)
    assert a and a["tool"] == "get_prop_facts" and a["args"]["name"] == "玉佩"
    bare = '思考中…\n{"tool": "spawn_writer", "args": {"note": "加点反转"}}'
    assert _parse_action(bare)["tool"] == "spawn_writer"
    # 最终回答（无工具块）→ None；多个工具块取最后一个
    assert _parse_action("正常回答，没有工具。") is None
    two = fenced + '```json\n{"tool": "query_vector", "args": {}}\n```'
    assert _parse_action(two)["tool"] == "query_vector"
    # 剥离后不残留调用块
    assert _strip_action(fenced).strip() == "我先查证一下。"
    assert '{"tool"' not in _strip_action(bare)
    assert "思考中…" in _strip_action(bare)