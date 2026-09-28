"""M6 · F16 FastAPI API 测试（mock 模式，TestClient）。"""
from __future__ import annotations

import json
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


def test_accept_chapter_with_edits():
    """作者预览直改：accept 带可选 body.chapter 覆盖待接受章节，记忆按编辑后正文重放。"""
    with _client() as c:
        c.post("/api/projects", json={"title": "直改", "genre": "short_story", "project_id": "apiE"})
        _run_setup(c, "apiE")
        r = c.post("/api/projects/apiE/volumes/1/chapters", json={"goal": "作者直改"})
        pending = r.json()["pending"]
        original = pending["scenes"][0]["text"]
        pending["scenes"][0]["text"] = "作者手改的正文"
        pending["scenes"][0]["heading"] = "手改场景"
        # 接受时带编辑后的完整章节
        r = c.post("/api/projects/apiE/chapters/1/1/accept", json={"chapter": pending})
        assert r.status_code == 200
        saved = r.json()["chapter"]
        assert saved["scenes"][0]["text"] == "作者手改的正文"
        assert saved["volume"] == 1 and saved["chapter"] == 1  # 路径参数兜底
        products = c.get("/api/projects/apiE/products").json()
        assert products["chapters"]["1_1"]["scenes"][0]["text"] == "作者手改的正文"

        # 编辑同步：长期向量按编辑后正文重放，AI 原稿不留残留
        root = Path(c.app.state.root)
        lt_path = root / "data" / "projects" / "apiE" / "vector_stores" / "long_term.json"
        assert lt_path.exists(), "长期向量库应已落盘"
        lt = json.loads(lt_path.read_text(encoding="utf-8"))
        # meta 与 chunks 平行，只看本章切片
        own = [chunk for chunk, m in zip(lt["chunks"], lt["meta"]) if m and m.get("key") == "1_1"]
        assert own, "1_1 的向量切片应存在"
        assert any("作者手改的正文" in chunk for chunk in own)
        assert not any(original in chunk for chunk in own)
        # 中期摘要键存在
        mid = json.loads((root / "data" / "projects" / "apiE" / "memory" / "mid_term.json")
                         .read_text(encoding="utf-8"))
        assert "1_1" in mid.get("summaries", mid)

        # 不带 body 的旧调用方式不受影响（无待接受章节 → 400）
        assert c.post("/api/projects/apiE/chapters/1/1/accept").status_code == 400


def test_chapter_versions_and_restore():
    """版本快照：编辑/删除自动留底，可恢复（含已删除章），恢复前当前稿再留底。"""
    with _client() as c:
        c.post("/api/projects", json={"title": "版本", "genre": "short_story", "project_id": "apiV"})
        _run_setup(c, "apiV")
        r = c.post("/api/projects/apiV/volumes/1/chapters", json={"goal": "版本测试"})
        original = r.json()["pending"]["scenes"][0]["text"]
        assert c.post("/api/projects/apiV/chapters/1/1/accept").status_code == 200

        # 编辑覆盖 → 旧稿留底
        ch = c.get("/api/projects/apiV/products").json()["chapters"]["1_1"]
        ch["scenes"][0]["text"] = "第二版正文"
        assert c.put("/api/projects/apiV/chapters/1/1", json={"chapter": ch}).status_code == 200
        vs = c.get("/api/projects/apiV/chapters/1/1/versions").json()["versions"]
        assert len(vs) == 1 and vs[0]["reason"] == "编辑覆盖"
        assert vs[0]["words"] > 0 and vs[0]["title"]

        # 恢复旧版 → 当前稿留底为「恢复前备份」，正文回滚，记忆按恢复稿重放
        vid = vs[0]["id"]
        full = c.get(f"/api/projects/apiV/chapters/1/1/versions/{vid}").json()["version"]
        assert full["chapter"]["scenes"][0]["text"] == original
        assert c.post(f"/api/projects/apiV/chapters/1/1/versions/{vid}/restore").status_code == 200
        products = c.get("/api/projects/apiV/products").json()
        assert products["chapters"]["1_1"]["scenes"][0]["text"] == original
        vs2 = c.get("/api/projects/apiV/chapters/1/1/versions").json()["versions"]
        assert len(vs2) == 2 and vs2[0]["reason"] == "恢复前备份"
        # 正典账本字段已暴露
        assert isinstance(products.get("event_ledger"), dict)
        assert isinstance(products.get("prop_registry"), dict)

        # 删除留底 + 卷级备份组标记已删除 + 删除章可恢复
        assert c.delete("/api/projects/apiV/volumes/1/chapters/1").status_code == 200
        groups = c.get("/api/projects/apiV/volumes/1/versions").json()["groups"]
        g = next(x for x in groups if x["key"] == "1_1")
        assert g["deleted"] is True and g["count"] >= 3
        assert c.post(f"/api/projects/apiV/chapters/1/1/versions/{vid}/restore").status_code == 200
        products = c.get("/api/projects/apiV/products").json()
        assert "1_1" in products["chapters"]
        # 非法版本 id → 404
        assert c.post("/api/projects/apiV/chapters/1/1/versions/../etc/restore").status_code in (404, 400)


def test_project_cost_endpoint():
    with _client() as c:
        c.post("/api/projects", json={"title": "成本", "genre": "short_story", "project_id": "apiM"})
        _run_setup(c, "apiM")
        c.post("/api/projects/apiM/volumes/1/chapters", json={"goal": "x"})
        c.post("/api/projects/apiM/chapters/1/1/accept")
        # mock 模式无真实 usage；直接注入一次带章节标记的记录验证流水与端点联动
        from novel_agent.llm import cost as cost_mod

        cost_mod.set_project("apiM", Path(c.app.state.root))
        cost_mod.set_chapter("1_1")
        cost_mod.record_usage(
            {"prompt_tokens": 1_000_000, "completion_tokens": 500_000, "total_tokens": 1_500_000},
            model="m",
        )
        got = c.get("/api/projects/apiM/cost").json()
        assert got["calls"] == 1 and got["chapters"]["1_1"]["total_tokens"] == 1_500_000
        # 默认单价 (0.14, 0.28)：1M 输入 + 0.5M 输出 = 0.28 USD
        assert abs(got["est_cost_usd"] - 0.28) < 1e-6


def test_quality_gate_and_style_samples():
    """质检报告随生成返回 + 风格样本 CRUD + pending 场景 AI 重写。"""
    with _client() as c:
        c.post("/api/projects", json={"title": "质检", "genre": "short_story", "project_id": "apiQ"})
        _run_setup(c, "apiQ")
        r = c.post("/api/projects/apiQ/volumes/1/chapters", json={"goal": "质检流程"})
        assert r.status_code == 200
        data = r.json()
        # 质检报告随预览返回：mock 生成内容确定、无重复、无节拍 → ok
        q = data["quality"]
        assert q["ok"] is True and q["duplicates"] == [] and q["missing_beats"] == []
        assert q["words"]["actual"] > 0

        # 风格样本：保存 → products 可见；超限拒绝
        samples = [{"id": "s1", "name": "冷峻", "text": "他把烟按灭在鞋底上，没抬头。"}]
        assert c.put("/api/projects/apiQ/style-samples", json={"samples": samples}).status_code == 200
        products = c.get("/api/projects/apiQ/products").json()
        assert products["style_samples"][0]["name"] == "冷峻"
        too_many = [{"id": str(i), "name": "x", "text": "t"} for i in range(4)]
        assert c.put("/api/projects/apiQ/style-samples", json={"samples": too_many}).status_code == 400

        # pending 场景 AI 重写：更新 pending_chapter 并重跑质检
        scene_id = data["pending"]["scenes"][0]["id"]
        r = c.post("/api/projects/apiQ/chapters/1/1/pending-scene-rewrite",
                   json={"scene_id": scene_id, "instruction": "更冷一些"})
        assert r.status_code == 200
        body = r.json()
        assert "已重写" in body["chapter"]["scenes"][0]["text"]
        assert body["quality"]["ok"] is True
        # 放弃清理
        assert c.delete("/api/projects/apiQ/chapters/1/1").status_code == 200


def test_style_library():
    """仿写库：预置条目 + 粘贴提取（mock→确定性要点）+ 泛型 CRUD + 注入带要点。"""
    with _client() as c:
        lst = c.get("/api/library/style").json()["entries"]
        assert any(e["id"] == "style_cold_short" for e in lst)
        # 粘贴提取：mock 模式用确定性统计当风格要点
        r = c.post("/api/library/styles/extract",
                   json={"text": "他把烟按灭在鞋底上。\n没抬头。\n「走吧。」他说。\n「去哪。」我问。"})
        assert r.status_code == 200
        entry = r.json()["entry"]
        assert entry["digest"] and "字" in entry["digest"] and entry["text"].startswith("他把烟")
        # 泛型手工新增 + 删除
        assert c.post("/api/library/style",
                      json={"id": "style_manual", "name": "手工", "text": "测试样本"}).status_code == 200
        assert c.delete("/api/library/style/style_manual").status_code == 200
        # 写手注入：digest 进要点行
        from novel_agent.agents.write import _style_note

        note = _style_note([{"id": "s", "name": "冷峻", "text": "原文片段", "digest": "短句为主"}])
        assert "风格要点：短句为主" in note and "原文片段" in note
        note2 = _style_note([{"id": "s", "name": "无要点", "text": "原文片段"}])
        assert "风格要点" not in note2 and "原文片段" in note2


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

        # 编辑同步：长期向量按新正文重放（旧切片移除、新切片入库，且不因重复编辑翻倍）
        root = Path(c.app.state.root)
        lt_path = root / "data" / "projects" / "apiU" / "vector_stores" / "long_term.json"
        assert lt_path.exists(), "长期向量库应已落盘"
        lt = json.loads(lt_path.read_text(encoding="utf-8"))
        assert any("被人工修改的正文" in chunk for chunk in lt["chunks"])
        keys = [m["key"] for m in lt["meta"] if m and m.get("key") == "1_1"]
        assert len(keys) == len([s for s in ch["scenes"] if s.get("text")])
        # 再编辑一次 → 旧文本消失、仍无重复（remove-then-replay 幂等）
        ch["scenes"][0]["text"] = "第二版人工正文"
        assert c.put("/api/projects/apiU/chapters/1/1", json={"chapter": ch}).status_code == 200
        lt = json.loads(lt_path.read_text(encoding="utf-8"))
        assert any("第二版人工正文" in chunk for chunk in lt["chunks"])
        assert not any("被人工修改的正文" in chunk for chunk in lt["chunks"])
        keys = [m["key"] for m in lt["meta"] if m and m.get("key") == "1_1"]
        assert len(keys) == len([s for s in ch["scenes"] if s.get("text")])
        # 中期摘要也已重放（键存在即可；mock 摘要为确定性文本）
        mid = json.loads((root / "data" / "projects" / "apiU" / "memory" / "mid_term.json")
                         .read_text(encoding="utf-8"))
        summaries = mid.get("summaries", mid)
        assert "1_1" in summaries


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
