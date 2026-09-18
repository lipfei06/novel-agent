"""M4 · F09 双 RAG 测试。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("NOVEL_ENGINE_MOCK", "1")  # rebuild 走关系抽取，保持离线确定性

from novel_agent.memory import LongTermMemory, rebuild_memory
from novel_agent.rag import TemporalGraph, retrieve


def _tmp() -> Path:
    return Path(tempfile.mkdtemp())


def test_temporal_graph_add_and_persist():
    path = _tmp() / "graph.json"
    g = TemporalGraph(path)
    g.add_edge("莫长老", "主角", "敌人", vol=1, ch=3, note="初遇即敌")
    g.add_edge("莫长老", "主角", "盟友", vol=1, ch=20, note="化敌为友")
    g2 = TemporalGraph(path)
    assert len(g2) == 2
    # 时序感知：第5章仍是敌人
    rel5 = {r["kind"] for r in g2.neighbors("莫长老", 1, 5)}
    assert rel5 == {"敌人"}
    # 第20章已成盟友
    rel20 = {r["kind"] for r in g2.neighbors("莫长老", 1, 20)}
    assert rel20 == {"敌人", "盟友"}


def test_temporal_graph_evolution():
    path = _tmp() / "graph.json"
    g = TemporalGraph(path)
    g.add_edge("A", "B", "敌人", vol=1, ch=3)
    g.add_edge("A", "B", "盟友", vol=1, ch=20)
    ev = g.evolution("A", "B")
    assert [e["ch"] for e in ev] == [3, 20]
    assert [e["kind"] for e in ev] == ["敌人", "盟友"]


def test_temporal_graph_rollback_by_chapter():
    path = _tmp() / "graph.json"
    g = TemporalGraph(path)
    g.add_edge("主角", "师父", "师徒", vol=1, ch=1)
    g.add_edge("主角", "反派", "冲突", vol=1, ch=2)
    g.add_edge("主角", "挚友", "盟友", vol=2, ch=2)  # 跨卷同章号，不得误伤
    removed = g.remove_chapter(1, 2)
    assert removed == 1
    assert len(g) == 2
    assert {e["kind"] for e in g.edges} == {"师徒", "盟友"}


def test_temporal_graph_legacy_migration():
    """旧格式（仅 chapter 字段）加载后自动迁移为卷1，行为与迁移前一致。"""
    path = _tmp() / "graph.json"
    path.write_text(
        json.dumps(
            {
                "nodes": ["主角", "师父"],
                "edges": [{"a": "主角", "b": "师父", "kind": "师徒", "chapter": 3, "note": ""}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    g = TemporalGraph(path)
    rel = g.neighbors("主角", 1, 5)
    assert rel and rel[0]["entity"] == "师父" and rel[0]["kind"] == "师徒"
    # 时序过滤依旧生效
    assert g.neighbors("主角", 1, 2) == []


def test_retrieve_combines_vector_and_graph():
    path = _tmp()
    long_term = LongTermMemory(path / "long_term.json")
    long_term.add(["主角在雨夜习得剑法"])
    graph = TemporalGraph(path / "graph.json")
    graph.add_edge("主角", "师父", "师徒", vol=1, ch=1)

    ctx = retrieve(["剑法", "主角"], long_term, graph, top_k=2, current_vol=1, current_chapter=2)
    assert "剑法" in ctx
    assert "师徒" in ctx
    assert "主角→师父" in ctx


def test_retrieve_respects_chapter():
    path = _tmp()
    long_term = LongTermMemory(path / "long_term.json")
    graph = TemporalGraph(path / "graph.json")
    graph.add_edge("主角", "师父", "师徒", vol=1, ch=10)
    ctx = retrieve(["主角"], long_term, graph, top_k=2, current_vol=1, current_chapter=5)
    assert "师徒" not in ctx  # 第5章时关系尚未建立


def test_long_term_split_and_rollback():
    """超长场景自动二次切分；meta 附 part/parts；按章回滚精准移除。"""
    path = _tmp() / "long_term.json"
    m = LongTermMemory(path)
    long_scene = "\n".join(f"第{i}段：主角在雨夜赶路，回想白天发生的冲突细节。" * 4 for i in range(30))
    assert len(long_scene) > 1200
    short_scene = "短场景：街角偶遇。"
    m.add([long_scene, short_scene], metas=[{"vol": 1, "ch": 3, "scene": 1, "key": "1_3"},
                                           {"vol": 1, "ch": 3, "scene": 2, "key": "1_3"}])
    assert len(m) > 2  # 长场景被切开
    hits = m.search("雨夜赶路", top_k=2, with_source=True)
    assert hits and hits[0].startswith("[第1卷第3章]")
    # 按章回滚：该章全部块（含切分块）移除
    before = len(m)
    removed = m.remove_chapter(1, 3)
    assert removed == before and len(m) == 0
    assert len(LongTermMemory(path)) == 0  # 持久化生效


def test_long_term_meta_persist():
    path = _tmp() / "long_term.json"
    m = LongTermMemory(path)
    m.add(["内容一", "内容二"], metas=[{"vol": 2, "ch": 5, "scene": 1, "key": "2_5"}, None])
    m2 = LongTermMemory(path)
    assert len(m2) == 2
    assert m2.remove_chapter(2, 5) == 1  # 无 meta 的块不受影响
    assert len(m2) == 1


def test_long_term_old_format_compat():
    """旧格式（无 meta 字段）加载后功能正常。"""
    from novel_agent.memory.long_term import _bigrams

    path = _tmp() / "long_term.json"
    text = "旧格式的场景文本"
    path.write_text(
        json.dumps({"mode": "sparse", "chunks": [text], "vectors": [_bigrams(text)]}, ensure_ascii=False),
        encoding="utf-8",
    )
    m = LongTermMemory(path)
    assert len(m) == 1
    assert m.search("旧格式", top_k=1) == [text]
    assert m.search("旧格式", top_k=1, with_source=True) == [text]  # 无 meta 不加前缀


def test_long_term_add_diff_by_meta():
    """文本已改动时，按元数据仍能定位替换旧块。"""
    path = _tmp() / "long_term.json"
    m = LongTermMemory(path)
    m.add(["原始场景文本ABC"], metas=[{"vol": 1, "ch": 2, "scene": 1, "key": "1_2"}])
    m.add_diff("已经改得完全不同的旧文本", "修订后的场景文本XYZ",
               meta={"vol": 1, "ch": 2, "scene": 1, "key": "1_2"})
    assert len(m) == 1  # 替换而非追加
    hits = m.search("修订后的场景", top_k=1)
    assert hits and "XYZ" in hits[0]


def test_rebuild_memory_all_restores_after_rollback():
    """删除残留 → rebuild(all) → 两库恢复完整（一致性兜底阀）。"""
    path = _tmp()
    chapters = {
        "1_1": {"volume": 1, "chapter": 1, "title": "一", "scenes": [{"text": "主角在雨夜拾到怀表"}]},
        "1_2": {"volume": 1, "chapter": 2, "title": "二", "scenes": [{"text": "主角与盟友因怀表争执"}]},
    }
    lt = LongTermMemory(path / "long_term.json")
    g = TemporalGraph(path / "graph.json")
    rebuild_memory(chapters, None, long_term=lt, graph=g, characters=[])
    total = len(lt)
    assert total >= 2
    lt.remove_chapter(1, 1)  # 模拟删除残留
    assert len(lt) < total
    stats = rebuild_memory(chapters, None, long_term=lt, graph=g, characters=[])
    assert stats["chapters"] == 2 and stats["scenes"] == 2
    assert len(lt) == total  # 重建后恢复
    assert lt.search("怀表", top_k=4)  # 两章内容均可召回


def test_rebuild_memory_scope_isolation():
    """scope=graph 不动向量库；scope=vector 不动图谱。"""
    path = _tmp()
    chapters = {"1_1": {"volume": 1, "chapter": 1, "title": "一", "scenes": [{"text": "场景内容甲"}]}}
    chars = [{"name": "主角", "role": "protagonist"}, {"name": "盟友", "role": "ally"}]
    lt = LongTermMemory(path / "long_term.json")
    g = TemporalGraph(path / "graph.json")
    rebuild_memory(chapters, None, long_term=lt, graph=g, characters=chars)
    assert len(lt) == 1 and len(g) == 1  # mock 关系抽取每章一条边

    # 仅重建图谱：边重算、向量不动
    g.add_edge("多余", "边", "测试", vol=9, ch=9)  # 制造图谱脏数据
    stats = rebuild_memory(chapters, None, long_term=None, graph=g, characters=chars)
    assert stats["scenes"] == 0  # 向量部分未执行
    assert len(lt) == 1  # 向量库未被触碰
    assert len(g) == 1  # 图谱被清空重算，脏边消失

    # 仅重建向量：图谱不动
    g.add_edge("多余", "边", "测试", vol=9, ch=9)
    stats = rebuild_memory(chapters, None, long_term=lt, graph=None, characters=chars)
    assert stats["relations"] == 0
    assert len(g) == 2  # 图谱未被触碰（含脏边）
    assert len(lt) == 1
