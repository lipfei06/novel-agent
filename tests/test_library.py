"""M0 · F17 写作基础库测试。

pytest 兼容：全部为纯 test_* 函数（不使用 pytest fixture），既可用内置运行器
`python tests/run_tests.py` 运行，也可在装有 pytest 的环境直接 `pytest tests/`。

覆盖：CRUD、版本自增、导出、两层叠加（项目覆盖层优先）、索引维护、检索、
人物/章节选型（含题材过滤）、预置 seed。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from novel_agent.library import (
    LibraryIndex,
    LibraryStore,
    NovelToolEntry,
    PersonalityEntry,
    PRESETS,
    pick_for_chapter,
    pick_for_character,
    search_personality,
    search_tool,
)


def _tmp_store() -> LibraryStore:
    return LibraryStore(base_dir=Path(tempfile.mkdtemp()) / "libraries")


def _seeded_store() -> LibraryStore:
    s = _tmp_store()
    s.seed(PRESETS)
    return s


def _indexed_seeded() -> tuple[LibraryStore, LibraryIndex]:
    store = _seeded_store()
    index = LibraryIndex(store.base_dir / ".index")
    index.rebuild(store)
    return store, index


def _expect(exc: type[Exception], fn):
    """断言 fn() 抛出 exc，否则测试失败。"""
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__} to be raised")


# ---- 数据模型 -----------------------------------------------------
def test_personality_model_defaults():
    e = PersonalityEntry(id="p1", name="测试性格")
    assert e.category == ""
    assert e.tags == []
    assert e.version == 1


def test_tool_model_defaults():
    e = NovelToolEntry(id="t1", name="伏笔")
    assert e.chapter_placement == ""
    assert e.version == 1


# ---- CRUD ---------------------------------------------------------
def test_add_get_list():
    store = _tmp_store()
    store.add("personality", PersonalityEntry(id="p1", name="孤僻寡言型", category="内敛"))
    store.add("personality", PersonalityEntry(id="p2", name="热血冲动型", category="外向行动派"))
    assert store.get("personality", "p1").name == "孤僻寡言型"
    assert [e.id for e in store.list("personality")] == ["p1", "p2"]
    assert [e.id for e in store.list("personality", category="内敛")] == ["p1"]


def test_add_duplicate_raises():
    store = _tmp_store()
    store.add("tool", NovelToolEntry(id="t1", name="伏笔"))
    _expect(ValueError, lambda: store.add("tool", NovelToolEntry(id="t1", name="悬念")))


def test_update_version_increments():
    store = _tmp_store()
    store.add("tool", NovelToolEntry(id="t1", name="伏笔", description="旧说明"))
    updated = store.update("tool", "t1", {"description": "新说明"})
    assert updated.version == 2
    assert updated.description == "新说明"
    assert store.get("tool", "t1").version == 2


def test_update_immutable_id_raises():
    store = _tmp_store()
    store.add("tool", NovelToolEntry(id="t1", name="伏笔"))
    _expect(ValueError, lambda: store.update("tool", "t1", {"id": "t2"}))


def test_update_missing_raises():
    store = _tmp_store()
    _expect(KeyError, lambda: store.update("tool", "nope", {"name": "x"}))


def test_delete():
    store = _tmp_store()
    store.add("tool", NovelToolEntry(id="t1", name="伏笔"))
    store.delete("tool", "t1")
    assert store.get("tool", "t1") is None
    _expect(KeyError, lambda: store.delete("tool", "t1"))


def test_export_roundtrip():
    base = Path(tempfile.mkdtemp())
    store = LibraryStore(base_dir=base / "libraries")
    store.add("personality", PersonalityEntry(id="p1", name="冷酷谋略型", category="理智型"))
    out = store.export("personality", base / "backup.json")
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["id"] == "p1"
    assert data[0]["version"] == 1


# ---- 两层存储（共享 + 项目覆盖层）---------------------------------
def test_overlay_precedence():
    base = Path(tempfile.mkdtemp())
    shared = LibraryStore(base_dir=base / "libraries")
    shared.add("tool", NovelToolEntry(id="t1", name="伏笔", description="共享版"))
    overlay = LibraryStore(base_dir=base / "libraries", overlay_dir=base / "overlay")
    overlay.add("tool", NovelToolEntry(id="t1", name="伏笔", description="项目版"))
    assert overlay.get("tool", "t1").description == "项目版"  # 项目层优先
    assert shared.get("tool", "t1").description == "共享版"  # 共享层不受污染
    assert len(overlay.list("tool")) == 1
    assert overlay.list("tool")[0].description == "项目版"


def test_overlay_update_copies_when_absent_in_overlay():
    base = Path(tempfile.mkdtemp())
    shared = LibraryStore(base_dir=base / "libraries")
    shared.add("tool", NovelToolEntry(id="t1", name="伏笔"))
    overlay = LibraryStore(base_dir=base / "libraries", overlay_dir=base / "overlay")
    updated = overlay.update("tool", "t1", {"description": "项目定制"})
    assert updated.version == 2
    assert overlay.get("tool", "t1").description == "项目定制"
    assert shared.get("tool", "t1").description == ""


# ---- 索引 ---------------------------------------------------------
def test_index_rebuild_upsert_remove_clear():
    store = _seeded_store()
    index = LibraryIndex(store.base_dir / ".index")
    index.rebuild(store)
    assert len(index._data["personality"]) == len(PRESETS["personality"])
    assert len(index._data["tool"]) == len(PRESETS["tool"])

    index.upsert("tool", NovelToolEntry(id="tool_new", name="闪回"))
    assert "tool_new" in index._data["tool"]

    index.remove("tool", "tool_new")
    assert "tool_new" not in index._data["tool"]

    index.clear()
    assert index._data == {}


def test_index_persistence():
    store = _seeded_store()
    index = LibraryIndex(store.base_dir / ".index")
    index.rebuild(store)
    reloaded = LibraryIndex(store.base_dir / ".index")
    assert len(reloaded._data["personality"]) == len(PRESETS["personality"])


# ---- 检索 ---------------------------------------------------------
def test_search_personality_relevance():
    store, index = _indexed_seeded()
    results = search_personality("孤僻 寡言 话少", top_k=3, store=store, index=index)
    assert results
    assert results[0].id == "pers_kuangye_guayan"


def test_search_tool_placement_query():
    store, index = _indexed_seeded()
    results = search_tool("结尾 留下悬念 钩子", top_k=3, store=store, index=index)
    assert results
    assert results[0].id in {"tool_gouzi", "tool_xuannian"}


def test_search_tool_no_match_returns_none():
    store, index = _indexed_seeded()
    results = search_tool("zzzqqq不存在词", top_k=3, store=store, index=index)
    assert results == []


# ---- 选型 ---------------------------------------------------------
def test_pick_for_character_genre_filter():
    store, index = _indexed_seeded()
    results = pick_for_character("沉稳 话少 很酷", genres=["仙侠"], top_k=3, store=store, index=index)
    assert results
    for e in results:
        assert "仙侠" in e.applicable_genres


def test_pick_for_chapter():
    store, index = _indexed_seeded()
    packet = {
        "title": "夜探密室",
        "goal": "主角潜入密室寻找线索",
        "hook": "钥匙突然亮起红光",
        "beats": [{"desc": "发现秘密"}, {"desc": "危险逼近"}],
    }
    results = pick_for_chapter(packet, top_k=3, store=store, index=index)
    assert results


def test_pick_for_chapter_empty_packet_returns_top():
    store = _seeded_store()
    results = pick_for_chapter({}, top_k=2, store=store)
    assert len(results) == 2


# ---- 预置 seed ----------------------------------------------------
def test_seed_counts():
    store = _seeded_store()
    assert len(store.list("personality")) == len(PRESETS["personality"])
    assert len(store.list("tool")) == len(PRESETS["tool"])


def test_seed_is_idempotent():
    store = _seeded_store()
    count = store.seed(PRESETS)
    assert count == 0


def test_presets_are_valid():
    assert all(e.id and e.name for e in PRESETS["personality"])
    assert all(e.id and e.name for e in PRESETS["tool"])
    ids = [e.id for e in PRESETS["personality"]]
    assert len(ids) == len(set(ids))
