"""M5 · 结构化输出宽松解析测试（不调用真实 LLM）。"""
from __future__ import annotations

from novel_agent.llm.factory import _extract_json, _validate_or_coerce
from novel_agent.types import Outline, WriterPacket


def test_extract_json_clean():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fences():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_prefix_suffix():
    assert _extract_json('好的，结果如下：{"a": 1} 完毕') == {"a": 1}


def test_validate_strict_pass():
    good = {
        "volume": 1, "chapter": 1, "title": "第1章", "goal": "目标",
        "conflicts": ["c1"], "beats": [{"order": 1, "type": "开场", "desc": "建立"}],
        "hook": "钩子", "characters": ["主角"], "pov": "主角",
    }
    packet = _validate_or_coerce(WriterPacket, good)
    assert packet is not None
    assert packet.title == "第1章"


def test_coerce_beats_strings_to_dicts():
    """模型把 beats 输出成字符串数组 → 自动包成 {desc: 字符串}。"""
    bad = {
        "volume": 1, "chapter": 1, "title": "第1章", "goal": "目标",
        "beats": ["场景一：建立", "场景二：冲突"],
        "hook": "钩子",
    }
    packet = _validate_or_coerce(WriterPacket, bad)
    assert packet is not None
    assert all(isinstance(b, dict) and "desc" in b for b in packet.beats)
    assert packet.beats[0]["desc"] == "场景一：建立"


def test_coerce_str_from_dict():
    """模型把 str 字段输出成 dict → 提取 summary/text 等。"""
    bad = {
        "version": 1,
        "structure": {"summary": "三幕结构"},
        "ending": {"summary": "温暖结局"},
        "volumes": [],
    }
    outline = _validate_or_coerce(Outline, bad)
    assert outline is not None
    assert outline.structure == "三幕结构"
    assert outline.ending == "温暖结局"


def test_coerce_unfixable_returns_none():
    assert _validate_or_coerce(WriterPacket, "不是字典") is None
