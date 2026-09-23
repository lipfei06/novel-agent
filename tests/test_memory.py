"""M4 · F09 三层记忆测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

from novel_agent.memory import LongTermMemory, MidTermMemory, get_short_term


def _tmp() -> Path:
    return Path(tempfile.mkdtemp())


def test_long_term_add_search():
    m = LongTermMemory(_tmp() / "long_term.json")
    m.add(["孤僻寡言的主角在雨夜出现", "热血冲动的少年冲入人群"])
    hits = m.search("孤僻寡言", top_k=1)
    assert hits and "孤僻寡言" in hits[0]


def test_long_term_no_match():
    m = LongTermMemory(_tmp() / "long_term.json")
    m.add(["晴天午后", "花园散步"])
    assert m.search("核聚变反应堆", top_k=2) == []


def test_long_term_add_diff():
    m = LongTermMemory(_tmp() / "long_term.json")
    m.add(["旧段落设定矛盾"])
    before = len(m)
    m.add_diff("旧段落设定矛盾", "新段落设定一致")
    assert len(m) == before  # 只替换不增
    hits = m.search("设定一致", top_k=1)
    assert hits and "新段落设定一致" in hits[0]


def test_long_term_clear_and_persist():
    path = _tmp() / "long_term.json"
    m = LongTermMemory(path)
    m.add(["内容甲"])
    m2 = LongTermMemory(path)
    assert len(m2) == 1
    m2.clear()
    assert len(LongTermMemory(path)) == 0


def test_long_term_mode_switch_preserves_corpus():
    """稠密/稀疏后端切换不得丢弃语料：按文本重算向量，检索仍可用。"""
    path = _tmp() / "long_term.json"

    def fake_embed(text: str) -> list[float]:
        return [float(len(text)), 1.0]  # 伪稠密向量

    dense = LongTermMemory(path, embed_fn=fake_embed)
    dense.add(["雨夜老宅的铁盒藏着身世秘密", "机场追击的单程票"])

    sparse = LongTermMemory(path)  # 以稀疏模式打开同一份库
    assert len(sparse) == 2  # 语料无损
    hits = sparse.search("铁盒", top_k=1)
    assert hits and "铁盒" in hits[0]

    redense = LongTermMemory(path, embed_fn=fake_embed)  # 切回稠密：按文本重算
    assert len(redense) == 2
    assert redense.search("单程票", top_k=1)[0].endswith("单程票")


def test_mid_term_add_get_recent():
    path = _tmp() / "mid_term.json"
    m = MidTermMemory(path)
    m.add(1, 1, "第一章摘要")
    m.add(1, 2, "第二章摘要")
    assert m.get(1, 1) == "第一章摘要"
    assert m.recent(1) == ["第二章摘要"]
    m2 = MidTermMemory(path)
    assert m2.recent() == ["第一章摘要", "第二章摘要"]


def test_mid_term_summarize():
    m = MidTermMemory(_tmp() / "mid_term.json")
    summary = m.summarize_chapter(
        {"volume": 1, "chapter": 1, "title": "第一章", "scenes": [{"text": "从前有座山山里有座庙"}, {"text": "庙里有个和尚"}]},
        None,
    )
    assert "第一章" in summary
    assert "从前有座山" in summary


def test_short_term_window():
    chapters = {
        "1_1": {"scenes": [{"text": "第1章正文"}]},
        "1_2": {"scenes": [{"text": "第2章正文"}]},
        "1_3": {"scenes": [{"text": "第3章正文"}]},
    }
    short = get_short_term(chapters, window=2)
    assert "第2章正文" in short
    assert "第3章正文" in short
    assert "第1章正文" not in short
