"""M0 · F17 写作基础库测试。

pytest 兼容：全部为纯 test_* 函数（不使用 pytest fixture），既可用内置运行器
`python tests/run_tests.py` 运行，也可在装有 pytest 的环境直接 `pytest tests/`。

覆盖：CRUD、版本自增、导出、两层叠加（项目覆盖层优先）、索引维护、检索、
人物/章节选型（含题材过滤）、预置 seed。
"""
from __future__ import annotations

import json
import os
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


# ---- 梗库 ----

def test_meme_seed_and_search():
    os.environ.setdefault("NOVEL_ENGINE_MOCK", "1")
    from novel_agent.library import MEME_PRESETS, MemeEntry, memes_for_chapter

    assert MEME_PRESETS and all(e.risk in ("safe", "caution", "avoid") for e in MEME_PRESETS)
    root = Path(tempfile.mkdtemp())
    from novel_agent.library import LibraryStore
    store = LibraryStore(root / "output" / "libraries")
    from novel_agent.library import PRESETS as P
    store.seed(P)
    hits = memes_for_chapter("职场裁员被抛弃自嘲", top_k=3, store=store)
    assert hits and all(isinstance(e, MemeEntry) for e in hits)
    # 检索命中的不应含 avoid 条目过滤问题（候选块再过滤一次）
    from novel_agent.library import meme_candidates_text
    block = meme_candidates_text("职场裁员被抛弃自嘲", root=root)
    assert block.startswith("<可用梗候选>")
    assert "不要生造网络热梗" in block


def test_populate_memes_mock_dedupes():
    os.environ.setdefault("NOVEL_ENGINE_MOCK", "1")
    from novel_agent.config import load_config
    from novel_agent.library import LibraryStore, populate_memes

    root = Path(tempfile.mkdtemp())
    (root / "config.yaml").write_text(
        "genre: short_story\nllm:\n  cheap: { model: c, api_key_env: K }\n"
        "token_budget: { state_update: 20000 }\n",
        encoding="utf-8",
    )
    cfg = load_config(root / "config.yaml")
    store = LibraryStore(root / "output" / "libraries")
    added = populate_memes(root, "职场", 5, cfg, store=store)
    assert len(added) == 5
    before = len(store.list("meme"))
    added2 = populate_memes(root, "职场", 5, cfg, store=store)
    # mock 名称含序号会重复 → 全部被去重，不新增
    assert len(store.list("meme")) == before if added2 else True


def test_populate_memes_dedupes_by_name():
    """重名条目（含预置）不得重复入库。"""
    os.environ.setdefault("NOVEL_ENGINE_MOCK", "1")
    from novel_agent.config import load_config
    from novel_agent.library import LibraryStore, MemeEntry, PRESETS, populate_memes

    root = Path(tempfile.mkdtemp())
    (root / "config.yaml").write_text(
        "genre: short_story\nllm:\n  cheap: { model: c, api_key_env: K }\n"
        "token_budget: { state_update: 20000 }\n",
        encoding="utf-8",
    )
    cfg = load_config(root / "config.yaml")
    store = LibraryStore(root / "output" / "libraries")
    store.seed(PRESETS)
    before = len(store.list("meme"))
    # 构造一条与预置重名的"LLM 输出"
    from unittest.mock import patch
    import novel_agent.library.memes as mm

    dup = MemeEntry(id="x", name=mm.MEME_PRESETS[0].name, content="dup")
    with patch.object(mm, "is_mock", lambda: False), patch.object(
        mm, "invoke_structured", lambda llm, msgs, schema=None, **kw: mm.MemeList(items=[dup])
    ):
        added = populate_memes(root, "职场", 3, cfg, store=store)
    assert added == []  # 重名全部被去重
    assert len(store.list("meme")) == before
