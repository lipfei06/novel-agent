"""质检门单元测试：场景查重（章内/跨窗）、节拍兑现、文风度量。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
os.environ["NOVEL_ENGINE_MOCK"] = "1"

from novel_agent.agents.quality import check_chapter_quality, scene_similarity  # noqa: E402
from novel_agent.config import Config, GenreProfile  # noqa: E402


def _cfg(**quality) -> Config:
    return Config(genre=GenreProfile(id="t", name="t"), quality=quality)


def _chapter(scenes: list[str], vol: int = 1, ch: int = 9) -> dict:
    return {
        "volume": vol, "chapter": ch, "title": "测试章",
        "scenes": [{"id": f"s{i}", "heading": f"场景{i}", "text": t} for i, t in enumerate(scenes)],
    }


DUP_A = ("深夜的会议室里，陈默把那份裁员协议推到桌面中央，李莉的笑容僵住了。"
         "窗外的霓虹灯一盏盏亮起，湘江的风带着湿气灌进来。他想起三年前的那个雨夜。")
DUP_B = ("深夜的会议室里，陈默把那份裁员协议推到桌面中央，李莉的笑容僵住了。"
         "窗外的霓虹灯一盏盏亮起，湘江的风带着湿气灌进来。他想起五年前的那个雪夜。")
OTHER = ("公证处的大厅很安静，叫号机发出规律的嘀声。张红推了推眼镜，"
         "把公证书递出窗口，编号在日光灯下清晰可见。")


def test_scene_similarity_ordering():
    assert scene_similarity(DUP_A, DUP_B) > 0.85  # 复制粘贴级
    assert scene_similarity(DUP_A, OTHER) < 0.2   # 无关场景底噪


def test_intra_duplicate_detected():
    rep = check_chapter_quality(_chapter([DUP_A, OTHER, DUP_B]), None, {}, _cfg())
    intra = [d for d in rep["duplicates"] if d["type"] == "intra"]
    assert len(intra) == 1
    assert intra[0]["a"]["index"] == 0 and intra[0]["b"]["index"] == 2
    assert intra[0]["ratio"] >= 0.85
    assert rep["ok"] is False


def test_cross_duplicate_within_window():
    prior = {"1_8": {"volume": 1, "chapter": 8, "title": "上一章",
                     "scenes": [{"id": "p1", "heading": "旧", "text": DUP_A}]},
             "1_7": {"volume": 1, "chapter": 7, "title": "近章",
                     "scenes": [{"id": "p2", "heading": "另", "text": OTHER}]}}
    rep = check_chapter_quality(_chapter([DUP_B], ch=9), None, prior, _cfg())
    cross = [d for d in rep["duplicates"] if d["type"] == "cross"]
    assert len(cross) == 1
    assert cross[0]["a"]["source"] == "1_8"  # 命中最近窗口内的重复
    assert cross[0]["b"]["index"] == 0


def test_cross_ignored_outside_window():
    # 窗口=3：只对比当前章之前最近的 3 章；更早的 1_2 即使内容重复也不查
    prior = {
        "1_2": {"volume": 1, "chapter": 2, "title": "远章",
                "scenes": [{"id": "f1", "heading": "远", "text": DUP_A}]},
        "1_6": {"volume": 1, "chapter": 6, "title": "近1",
                "scenes": [{"id": "p1", "heading": "近", "text": OTHER}]},
        "1_7": {"volume": 1, "chapter": 7, "title": "近2",
                "scenes": [{"id": "p2", "heading": "近", "text": OTHER}]},
        "1_8": {"volume": 1, "chapter": 8, "title": "近3",
                "scenes": [{"id": "p3", "heading": "近", "text": OTHER}]},
    }
    rep = check_chapter_quality(_chapter([DUP_A], ch=9), None, prior, _cfg(repetition_window=3))
    assert rep["duplicates"] == []  # 1_2 在窗口外，唯一重复源被忽略


def test_threshold_configurable():
    # 阈值提到 0.99 → 近似复制也不再标记
    rep = check_chapter_quality(_chapter([DUP_A, DUP_B]), None, {}, _cfg(repetition_threshold=0.99))
    assert rep["duplicates"] == [] and rep["ok"] is True


def test_missing_beat_flagged():
    packet = {"beats": [
        {"type": "scene", "desc": "仲裁庭上陈默提交公证书反诉华讯违法裁员"},
        {"type": "scene", "desc": "王坚散会后拦住陈默低声威胁他撤诉"},
        {"type": "scene", "desc": "陆远在旁听席目睹全程后决定追加投资"},
    ]}
    scenes = ["仲裁庭上陈默提交公证书反诉华讯违法裁员，仲裁员当场核对证据。",
              "王坚散会后拦住陈默低声威胁他撤诉，陈默平静地把录音键按了下去。"]
    rep = check_chapter_quality(_chapter(scenes), packet, {}, _cfg())
    assert rep["missing_beats"] == ["陆远在旁听席目睹全程后决定追加投资"]


def test_beats_all_covered_passes():
    packet = {"beats": [{"type": "scene", "desc": "仲裁庭上陈默提交公证书反诉华讯违法裁员"}]}
    rep = check_chapter_quality(_chapter(["仲裁庭上陈默提交公证书反诉华讯违法裁员，全场哗然。"]), packet, {}, _cfg())
    assert rep["missing_beats"] == []


def test_style_metric():
    scenes = ["短句。\n又是一句。\n还是一句。", "这是一段正常的描写，有完整的句子和适当的长度，不会触发单句成段的统计口径。"]
    rep = check_chapter_quality(_chapter(scenes), None, {}, _cfg())
    assert rep["style"]["total_paragraphs"] >= 4
    assert rep["style"]["single_sentence_paragraphs"] == 3


def test_report_shape_and_defaults():
    rep = check_chapter_quality(_chapter([OTHER]), None, {}, _cfg())
    assert rep["threshold"] == 0.70 and rep["window"] == 3
    assert rep["words"]["actual"] == len(OTHER)
    assert rep["ok"] is True
