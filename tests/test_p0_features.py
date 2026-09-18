"""P0 功能 + 人物优化测试：成本/重生成/改写场景/人物模板/状态跟踪。"""
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
  writer:   { model: "w", api_key_env: "K3" }
  cheap:    { model: "c", api_key_env: "K2" }
  editor:   { model: "e", api_key_env: "K4" }
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000, check: 8000, editorial: 10000, state_update: 4000 }
memory: { short_window: 3 }
rag: { top_k: 4 }
library: { personality_top_k: 3 }
export: { epub: false }
"""


def _client():
    root = Path(tempfile.mkdtemp())
    (root / "config.yaml").write_text(CFG, encoding="utf-8")
    return TestClient(create_app(root))


def _setup(c, pid):
    c.post(f"/api/projects/{pid}/start", json={"idea": "x"})
    for _ in range(60):
        v = c.post(f"/api/projects/{pid}/confirm", json={"action": "accept"}).json()
        if v["done"] or v["stage"] == "stage4b":
            break


def test_characters_have_tier():
    with _client() as c:
        c.post("/api/projects", json={"title": "分级", "genre": "short_story", "project_id": "pT"})
        _setup(c, "pT")
        products = c.get("/api/projects/pT/products").json()
        chars = products["characters"]
        assert chars
        assert any(ch.get("tier") == "main" for ch in chars)
        assert any(ch.get("tier") == "supporting" for ch in chars)


def test_character_state_after_accept():
    with _client() as c:
        c.post("/api/projects", json={"title": "状态", "genre": "short_story", "project_id": "pS"})
        _setup(c, "pS")
        c.post("/api/projects/pS/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/pS/chapters/1/1/accept")
        products = c.get("/api/projects/pS/products").json()
        cs = products.get("character_state") or {}
        assert cs.get("entries")
        # 只有 main 被记录；有 status 与弧光阶段
        assert all(e.get("tier") == "main" for e in cs["entries"])
        assert all("status" in e and "arc_stage" in e for e in cs["entries"])


def test_relations_endpoint():
    with _client() as c:
        c.post("/api/projects", json={"title": "关系", "genre": "short_story", "project_id": "pRel"})
        _setup(c, "pRel")
        c.post("/api/projects/pRel/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/pRel/chapters/1/1/accept")
        r = c.get("/api/projects/pRel/relations")
        assert r.status_code == 200
        data = r.json()
        assert data["nodes"]
        # 时序图谱应有关系边（主角×伙伴互动）
        assert any(e.get("chapter") for e in data["edges"])


def test_character_has_appearance_fields():
    with _client() as c:
        c.post("/api/projects", json={"title": "外貌", "genre": "short_story", "project_id": "pA"})
        _setup(c, "pA")
        chars = c.get("/api/projects/pA/products").json()["characters"]
        main = next(ch for ch in chars if ch.get("tier") == "main")
        assert main.get("appearance")
        assert main.get("background")


def test_cost_endpoint():
    with _client() as c:
        c.post("/api/projects", json={"title": "费", "genre": "short_story", "project_id": "pC"})
        r = c.get("/api/projects/pC/cost")
        assert r.status_code == 200
        data = r.json()
        assert "total_tokens" in data and "est_cost_usd" in data


def test_regenerate_chapter():
    with _client() as c:
        c.post("/api/projects", json={"title": "重", "genre": "short_story", "project_id": "pR"})
        _setup(c, "pR")
        c.post("/api/projects/pR/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/pR/chapters/1/1/accept")
        r = c.post("/api/projects/pR/volumes/1/chapters/1/regenerate")
        assert r.status_code == 200
        pending = r.json()["pending"]
        assert pending["scenes"]
        assert c.post("/api/projects/pR/chapters/1/1/accept").status_code == 200


def test_rewrite_scene():
    with _client() as c:
        c.post("/api/projects", json={"title": "改", "genre": "short_story", "project_id": "pW"})
        _setup(c, "pW")
        c.post("/api/projects/pW/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/pW/chapters/1/1/accept")
        products = c.get("/api/projects/pW/products").json()
        scene_id = products["chapters"]["1_1"]["scenes"][0]["id"]
        r = c.post(f"/api/projects/pW/chapters/1/1/scenes/{scene_id}/rewrite", json={"instruction": "改缓和"})
        assert r.status_code == 200
        assert r.json()["new_text"]
        # 未修改的场景保持原样
        ch = c.get("/api/projects/pW/products").json()["chapters"]["1_1"]
        assert ch["scenes"][0]["text"] == r.json()["new_text"]
        # 空指令 → 400；不存在场景 → 404
        assert c.post(f"/api/projects/pW/chapters/1/1/scenes/{scene_id}/rewrite", json={"instruction": "  "}).status_code == 400
        assert c.post("/api/projects/pW/chapters/1/1/scenes/nope/rewrite", json={"instruction": "x"}).status_code == 404


def test_character_template_library():
    with _client() as c:
        # 预置模板
        entries = c.get("/api/library/character_template").json()["entries"]
        assert entries
        # 新增
        r = c.post("/api/library/character_template", json={"id": "ct_t", "name": "测试模板", "role": "ally", "motivation": "m"})
        assert r.status_code == 200
        # 更新
        assert c.put("/api/library/character_template/ct_t", json={"flaw": "f"}).status_code == 200
        # 删除
        assert c.delete("/api/library/character_template/ct_t").status_code == 200


def test_save_character_as_template():
    with _client() as c:
        c.post("/api/projects", json={"title": "存", "genre": "short_story", "project_id": "pV"})
        _setup(c, "pV")
        products = c.get("/api/projects/pV/products").json()
        cid = products["characters"][0]["id"]
        r = c.post(f"/api/projects/pV/characters/{cid}/template")
        assert r.status_code == 200
        assert r.json()["id"].startswith("ct_")
        entries = c.get("/api/library/character_template").json()["entries"]
        assert any(e["id"] == r.json()["id"] for e in entries)


def test_memory_rebuild_endpoint():
    with _client() as c:
        c.post("/api/projects", json={"title": "重建", "genre": "short_story", "project_id": "pRb"})
        _setup(c, "pRb")
        c.post("/api/projects/pRb/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/pRb/chapters/1/1/accept")
        # 非法 scope
        r = c.post("/api/projects/pRb/memory/rebuild", json={"scope": "bad"})
        assert r.status_code == 400
        # 全量重建
        r = c.post("/api/projects/pRb/memory/rebuild", json={"scope": "all"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] and data["chapters"] >= 1
        # 删章后重建：记忆残留被清除、新章重新入库
        assert c.delete("/api/projects/pRb/volumes/1/chapters/1").status_code == 200
        c.post("/api/projects/pRb/volumes/1/chapters", json={"goal": "y"})
        c.post("/api/projects/pRb/chapters/1/1/accept")
        r = c.post("/api/projects/pRb/memory/rebuild", json={"scope": "all"})
        assert r.status_code == 200 and r.json()["chapters"] >= 1
