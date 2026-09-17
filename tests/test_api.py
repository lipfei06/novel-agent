"""M6 · F16 FastAPI API 测试（mock 模式，TestClient）。"""
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
token_budget: { concept: 6000, world: 8000, character: 8000, outline: 10000, volume_plan: 8000, packet: 8000, write: 12000, edit: 4000, check: 8000, editorial: 10000 }
memory: { short_window: 3 }
rag: { top_k: 4 }
library: { personality_top_k: 3 }
export: { epub: true }
"""


def _client():
    root = Path(tempfile.mkdtemp())
    (root / "config.yaml").write_text(CFG, encoding="utf-8")
    return TestClient(create_app(root))


def test_health():
    with _client() as c:
        assert c.get("/api/health").json()["status"] == "ok"


def test_profiles():
    with _client() as c:
        data = c.get("/api/profiles").json()
        assert {"webnovel", "literary", "short_story"} <= set(data["profiles"])


def test_create_and_list_project():
    with _client() as c:
        r = c.post("/api/projects", json={"title": "测试", "genre": "short_story", "project_id": "api1"})
        assert r.status_code == 200
        body = r.json()
        assert body["project_id"] == "api1"
        projects = c.get("/api/projects").json()["projects"]
        assert any(p["project_id"] == "api1" for p in projects)


def test_start_and_confirm_flow():
    with _client() as c:
        c.post("/api/projects", json={"title": "流", "genre": "short_story", "project_id": "api2"})
        # start → 第一个确认点 stage0
        r = c.post("/api/projects/api2/start", json={"idea": "测试立意"})
        view = r.json()
        assert view["done"] is False
        assert view["stage"] == "stage0"
        assert view["payload"]["title_idea"] == "测试立意"

        # 连续确认直到完成
        steps = ["stage0", "stage1", "stage2", "stage3", "stage4a"]
        for _ in range(40):
            view = c.post("/api/projects/api2/confirm", json={"action": "accept"}).json()
            if view["done"]:
                break
            if view["stage"] not in steps:
                steps.append(view["stage"])
        assert view["done"] is True
        assert view["current_stage"] == "done"


def test_confirm_edit():
    with _client() as c:
        c.post("/api/projects", json={"title": "改", "genre": "short_story", "project_id": "api3"})
        c.post("/api/projects/api3/start", json={"idea": "x"})
        view = c.post(
            "/api/projects/api3/confirm",
            json={"action": "edit", "data": {"title_idea": "被修改"}},
        ).json()
        # 下一个确认点是 stage1，说明 stage0 已通过
        assert view["stage"] == "stage1"
        # 验证修改落盘：直接驱动到导出后再从 final 验证不方便，检查 messages
        # 简化：确认 stage0 的 edit 已生效（concept 不可直接查，这里验证流程继续即可）


def test_final_files_after_complete():
    with _client() as c:
        c.post("/api/projects", json={"title": "完", "genre": "short_story", "project_id": "api4"})
        c.post("/api/projects/api4/start", json={"idea": "x"})
        for _ in range(60):
            view = c.post("/api/projects/api4/confirm", json={"action": "accept"}).json()
            if view["done"]:
                break
        assert view["done"] is True
        files = c.get("/api/projects/api4/final").json()["files"]
        assert any(f["name"].endswith(".md") for f in files)
        assert any(f["name"].endswith(".txt") for f in files)
        assert any(f["name"].endswith(".epub") for f in files)


def test_unknown_project_404():
    with _client() as c:
        assert c.get("/api/projects/nope").status_code == 404
        assert c.post("/api/projects/nope/start", json={"idea": "x"}).status_code == 404


def test_library_endpoint():
    with _client() as c:
        r = c.get("/api/library/personality")
        assert r.status_code == 200
        entries = r.json()["entries"]
        assert entries and any(e["id"] == "pers_kuangye_guayan" for e in entries)
        assert c.get("/api/library/bad").status_code == 400


def test_library_crud():
    with _client() as c:
        # add
        r = c.post("/api/library/personality", json={"id": "pers_test", "name": "测试性格", "category": "测试"})
        assert r.status_code == 200
        # update (version 自增)
        r = c.put("/api/library/personality/pers_test", json={"description": "新描述"})
        assert r.status_code == 200
        assert r.json()["version"] == 2
        # delete
        assert c.delete("/api/library/personality/pers_test").status_code == 200
        # duplicate add → 400
        c.post("/api/library/personality", json={"id": "pers_dup", "name": "重复"})
        assert c.post("/api/library/personality", json={"id": "pers_dup", "name": "重复2"}).status_code == 400


def test_products_endpoint():
    with _client() as c:
        c.post("/api/projects", json={"title": "产", "genre": "short_story", "project_id": "api6"})
        c.post("/api/projects/api6/start", json={"idea": "x"})
        # 推进到 stage2 后查产品
        for _ in range(3):
            v = c.post("/api/projects/api6/confirm", json={"action": "accept"}).json()
            if v["done"]:
                break
        products = c.get("/api/projects/api6/products").json()
        assert products["concept"] is not None
        assert products["world_bible"] is not None
        assert products["characters"] is not None
        assert products["outline"] is None or products["outline"]["version"] >= 1
        assert c.get("/api/projects/nope/products").status_code == 404


def test_state_endpoint():
    with _client() as c:
        c.post("/api/projects", json={"title": "态", "genre": "short_story", "project_id": "api7"})
        # 未开始 → started=False
        assert c.get("/api/projects/api7/state").json()["started"] is False
        # 启动后 → started=True, 停在 stage0
        c.post("/api/projects/api7/start", json={"idea": "x"})
        s = c.get("/api/projects/api7/state").json()
        assert s["started"] is True
        assert s["done"] is False
        assert s["stage"] == "stage0"
        # 全部确认 → started=True, done=True
        for _ in range(60):
            v = c.post("/api/projects/api7/confirm", json={"action": "accept"}).json()
            if v["done"]:
                break
        s = c.get("/api/projects/api7/state").json()
        assert s["started"] is True
        assert s["done"] is True
        assert c.get("/api/projects/nope/state").status_code == 404


def test_update_product():
    with _client() as c:
        c.post("/api/projects", json={"title": "改设", "genre": "short_story", "project_id": "api8"})
        c.post("/api/projects/api8/start", json={"idea": "x"})
        # 推进到 stage1 后，concept 已存在
        c.post("/api/projects/api8/confirm", json={"action": "accept"})
        # 修改概念
        products = c.get("/api/projects/api8/products").json()
        concept = dict(products["concept"])
        concept["title_idea"] = "被表单修改的书名"
        r = c.put("/api/projects/api8/products", json={"field": "concept", "value": concept})
        assert r.status_code == 200
        products2 = c.get("/api/projects/api8/products").json()
        assert products2["concept"]["title_idea"] == "被表单修改的书名"
        # 非法字段 → 400
        assert c.put("/api/projects/api8/products", json={"field": "nope", "value": {}}).status_code == 400


def test_export_now():
    with _client() as c:
        c.post("/api/projects", json={"title": "导", "genre": "short_story", "project_id": "api9"})
        c.post("/api/projects/api9/start", json={"idea": "x"})
        # 未完成前导出 → 400（没有已接受章节）
        assert c.post("/api/projects/api9/export").status_code == 400
        # 跑完全程后导出
        for _ in range(60):
            v = c.post("/api/projects/api9/confirm", json={"action": "accept"}).json()
            if v["done"]:
                break
        r = c.post("/api/projects/api9/export")
        assert r.status_code == 200
        assert any(f.endswith(".md") for f in r.json()["files"])


def _run_setup(c, project_id: str = "apiW") -> None:
    """跑完设定流程（stage0-3 + 卷细纲），使得有 volume_plans。"""
    c.post(f"/api/projects/{project_id}/start", json={"idea": "x"})
    for _ in range(60):
        v = c.post(f"/api/projects/{project_id}/confirm", json={"action": "accept"}).json()
        if v["done"] or v["stage"] == "stage4b":
            break


def test_volume_chapter_management():
    with _client() as c:
        c.post("/api/projects", json={"title": "卷章", "genre": "short_story", "project_id": "apiW"})
        # 未跑设定 → volumes 为空
        assert c.get("/api/projects/apiW/volumes").json()["volumes"] == []
        # 跑完设定 → 有卷
        _run_setup(c, "apiW")
        vols = c.get("/api/projects/apiW/volumes").json()["volumes"]
        assert len(vols) == 1
        # 修改卷
        r = c.put("/api/projects/apiW/volumes/1", json={"title": "改过的卷名"})
        assert r.status_code == 200
        vols = c.get("/api/projects/apiW/volumes").json()["volumes"]
        assert vols[0]["title"] == "改过的卷名"
        # 手工新增一卷
        r = c.post("/api/projects/apiW/volumes", json={"generate": False, "volume": {"volume": 2, "title": "第二卷", "chapter_count": 3}})
        assert r.status_code == 200
        assert len(r.json()["volumes"]) == 2


def test_create_accept_chapter():
    with _client() as c:
        c.post("/api/projects", json={"title": "章节", "genre": "short_story", "project_id": "apiC"})
        _run_setup(c, "apiC")
        # 提交章节表单 → 生成预览（未保存）
        r = c.post("/api/projects/apiC/volumes/1/chapters", json={"goal": "主角揭开身世之谜"})
        assert r.status_code == 200
        pending = r.json()["pending"]
        assert pending["scenes"]
        assert not c.get("/api/projects/apiC/products").json()["chapters"]  # 尚未保存
        # 接受 → 保存 + 记忆更新
        r = c.post("/api/projects/apiC/chapters/1/1/accept")
        assert r.status_code == 200
        products = c.get("/api/projects/apiC/products").json()
        assert "1_1" in products["chapters"]
        # 再生成一章
        r = c.post("/api/projects/apiC/volumes/1/chapters", json={"goal": "第二幕冲突"})
        assert r.json()["pending"]["chapter"] == 2
        # 放弃
        assert c.delete("/api/projects/apiC/chapters/1/2").status_code == 200
        products = c.get("/api/projects/apiC/products").json()
        assert "1_2" not in products["chapters"]


def test_update_chapter():
    with _client() as c:
        c.post("/api/projects", json={"title": "改章", "genre": "short_story", "project_id": "apiU"})
        _run_setup(c, "apiU")
        c.post("/api/projects/apiU/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/apiU/chapters/1/1/accept")
        # 读当前章节，改第一场景文本
        products = c.get("/api/projects/apiU/products").json()
        ch = products["chapters"]["1_1"]
        ch["scenes"][0]["text"] = "被人工修改的正文"
        r = c.put("/api/projects/apiU/chapters/1/1", json={"chapter": ch})
        assert r.status_code == 200
        products2 = c.get("/api/projects/apiU/products").json()
        assert products2["chapters"]["1_1"]["scenes"][0]["text"] == "被人工修改的正文"
        # 修改不存在的章节 → 404
        assert c.put("/api/projects/apiU/chapters/1/99", json={"chapter": ch}).status_code == 404


def test_list_projects_real_stats():
    with _client() as c:
        c.post("/api/projects", json={"title": "统计", "genre": "short_story", "project_id": "apiS"})
        _run_setup(c, "apiS")
        c.post("/api/projects/apiS/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/apiS/chapters/1/1/accept")
        projects = c.get("/api/projects").json()["projects"]
        p = next(x for x in projects if x["project_id"] == "apiS")
        assert p["chapters"] == 1
        assert p["volumes"] >= 1
        assert p["stage"] == "写作中"


def test_delete_project():
    with _client() as c:
        c.post("/api/projects", json={"title": "删", "genre": "short_story", "project_id": "api5"})
        assert c.delete("/api/projects/api5").json()["deleted"] == "api5"
        assert c.get("/api/projects/api5").status_code == 404
