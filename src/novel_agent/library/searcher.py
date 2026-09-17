"""Searcher：写作基础库的检索入口。

供写作环节按用途引用：
- pick_for_character：人物设定选性格原型（含题材过滤）
- pick_for_chapter：章级规划选叙事技法
- search_personality / search_tool：通用检索

store 未显式传入时，用 default_store()（根目录下的共享库）。
"""
from __future__ import annotations

from pathlib import Path

from .index import LibraryIndex
from .personality import PersonalityEntry
from .store import Kind, LibraryStore
from .tools import NovelToolEntry

_DEFAULT_LIBRARIES = Path("output/libraries")


def default_store(root: str | Path = ".") -> LibraryStore:
    """默认共享库：<root>/output/libraries。"""
    return LibraryStore(Path(root) / _DEFAULT_LIBRARIES)


def _rank(store: LibraryStore, index: LibraryIndex | None, kind: Kind, query: str, top_k: int) -> list[object]:
    """按索引排名返回命中条目。

    索引存在时以索引为准（无命中则返回空，不回退）；仅当没有索引时，
    才退化为按 id 排序的线性取前 top_k。
    """
    if index is not None:
        results: list[object] = []
        for hit in index.search(query, kind, top_k=top_k):
            entry = store.get(kind, hit["id"])
            if entry is not None:
                results.append(entry)
        return results
    return list(store.list(kind))[:top_k]


def search_personality(
    query: str, top_k: int = 3, store: LibraryStore | None = None, index: LibraryIndex | None = None
) -> list[PersonalityEntry]:
    store = store or default_store()
    return [e for e in _rank(store, index, "personality", query, top_k) if isinstance(e, PersonalityEntry)]


def search_tool(
    query: str, top_k: int = 3, store: LibraryStore | None = None, index: LibraryIndex | None = None
) -> list[NovelToolEntry]:
    store = store or default_store()
    return [e for e in _rank(store, index, "tool", query, top_k) if isinstance(e, NovelToolEntry)]


def pick_for_character(
    spec: str,
    genres: list[str] | None = None,
    top_k: int = 3,
    store: LibraryStore | None = None,
    index: LibraryIndex | None = None,
) -> list[PersonalityEntry]:
    """按人物需求选性格原型。genres 非空时，先过滤 applicable_genres 匹配的条目再排序。"""
    store = store or default_store()
    all_entries = [e for e in store.list("personality") if isinstance(e, PersonalityEntry)]
    if genres:
        wanted = set(genres)
        candidates = [
            e
            for e in all_entries
            if not e.applicable_genres or bool(wanted & set(e.applicable_genres))
        ]
        if not candidates:
            candidates = all_entries
    else:
        candidates = all_entries
    if index is not None:
        query = " ".join([spec, *(genres or [])])
        hits = index.search(query, "personality", top_k=max(top_k, len(candidates)))
        hit_ids = {h["id"]: i for i, h in enumerate(hits)}
        ordered = sorted(candidates, key=lambda e: hit_ids.get(e.id, len(candidates)))
        candidates = ordered
    return candidates[:top_k]


def pick_for_chapter(
    packet: dict,
    top_k: int = 3,
    store: LibraryStore | None = None,
    index: LibraryIndex | None = None,
) -> list[NovelToolEntry]:
    """按章节 writer_packet 目标选叙事技法。query 由 packet 的目标/冲突/钩子构成。"""
    store = store or default_store()
    parts = [
        str(packet.get(k, ""))
        for k in ("goal", "hook", "pov", "title")
    ]
    beats = packet.get("beats")
    if isinstance(beats, list):
        parts.extend(str(b.get("desc", "")) for b in beats if isinstance(b, dict))
    query = " ".join(p for p in parts if p)
    if not query:
        return [e for e in store.list("tool") if isinstance(e, NovelToolEntry)][:top_k]
    return [e for e in _rank(store, index, "tool", query, top_k) if isinstance(e, NovelToolEntry)]


# ---- 带自动建索引的便捷取数（供规划/写作链路直接使用） --------------------

def store_and_index(root: str | Path, kind: Kind) -> tuple[LibraryStore, LibraryIndex]:
    """返回共享库 store 与索引；索引缺该 kind 数据时自动全量重建。"""
    base = Path(root) / "output" / "libraries"
    store = LibraryStore(base)
    index = LibraryIndex(base / ".index")
    if not index.has_kind(kind):
        index.rebuild(store)
    return store, index


def tools_for_chapter(root: str | Path, packet_like: dict, top_k: int = 3) -> list[dict]:
    """按章节目标/钩子从工具库检索叙事技法（返回条目快照 dict 列表）。"""
    store, index = store_and_index(root, "tool")
    return [e.model_dump() for e in pick_for_chapter(packet_like, top_k=top_k, store=store, index=index)]


def personality_for(root: str | Path, spec: str, genres: list[str] | None = None, top_k: int = 3) -> list[dict]:
    """按需求描述检索性格原型（返回条目快照 dict 列表）。"""
    store, index = store_and_index(root, "personality")
    return [e.model_dump() for e in pick_for_character(spec, genres=genres, top_k=top_k, store=store, index=index)]


def templates_for(root: str | Path) -> list[dict]:
    """人物模板库全部条目（快照 dict 列表），供人物设计时参考/起步。"""
    store, index = store_and_index(root, "character_template")
    return [e.model_dump() for e in store.list("character_template")]
