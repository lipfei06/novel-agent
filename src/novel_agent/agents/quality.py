"""章节质检门：写手产出后、作者预览前的机器审核（纯代码检测，零 LLM 成本）。

检测项：
- 场景查重：章内两两 + 与最近 repetition_window 章的场景两两（difflib 序列相似度，
  归一化空白后比较）。跨章只看最近窗口——与写手上下文对齐，更早的章节读者与
  写手都已淡忘，查了只会制造误报。
- 节拍兑现：packet.beats 与场景的中文二元组重叠启发式（零成本确定性判定），
  低于覆盖阈值的节拍标记为"规划了但未写"。
- 文风度量：单句成段占比（只读指标，供作者与后续文风约束对照）。

报告只标记、不阻断：修复与裁决由作者在预览页完成（并排对比 → 采用/编辑/AI 重写）。
"""
from __future__ import annotations

import difflib
import re
import time


def _norm(text: str | None) -> str:
    return "".join((text or "").split())


def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}


def scene_similarity(a: str | None, b: str | None) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _key_sort(k: str) -> tuple[int, int]:
    try:
        v, c = str(k).split("_")
        return (int(v), int(c))
    except ValueError:
        return (0, 0)


def _scene_entry(source: str, index: int, scene: dict) -> dict:
    return {
        "source": source,  # "current" 或章节键（如 "1_5"）
        "index": index,
        "heading": scene.get("heading") or "",
        "text": scene.get("text") or "",
    }


def _check_duplicates(chapter: dict, prior_chapters: dict, threshold: float, window: int) -> list[dict]:
    scenes = chapter.get("scenes") or []
    duplicates: list[dict] = []
    # 章内两两
    for i in range(len(scenes)):
        for j in range(i + 1, len(scenes)):
            r = scene_similarity(scenes[i].get("text"), scenes[j].get("text"))
            if r >= threshold:
                duplicates.append({
                    "type": "intra",
                    "ratio": round(r, 3),
                    "a": _scene_entry("current", i, scenes[i]),
                    "b": _scene_entry("current", j, scenes[j]),
                })
    # 跨章：只对比当前章之前的最近 window 章（与写手上下文对齐）
    if window > 0:
        key = f"{chapter.get('volume', '?')}_{chapter.get('chapter', '?')}"
        cur = _key_sort(key)
        prior_keys = sorted((k for k in prior_chapters if k != key and _key_sort(k) < cur), key=_key_sort)
        for pk in prior_keys[-window:]:
            for pi, ps in enumerate(prior_chapters[pk].get("scenes") or []):
                for ci, s in enumerate(scenes):
                    r = scene_similarity(ps.get("text"), s.get("text"))
                    if r >= threshold:
                        duplicates.append({
                            "type": "cross",
                            "ratio": round(r, 3),
                            "a": _scene_entry(pk, pi, ps),
                            "b": _scene_entry("current", ci, s),
                        })
    duplicates.sort(key=lambda d: -d["ratio"])
    return duplicates


def _check_beats(packet: dict | None, scenes: list[dict], coverage: float = 0.25) -> list[str]:
    """节拍兑现：节拍描述的二元组与场景二元组的最大重叠低于阈值 → 未写。"""
    beats = (packet or {}).get("beats") or []
    if not beats or not scenes:
        return []
    scene_grams = []
    for s in scenes:
        scene_grams.append(_bigrams(_norm((s.get("heading") or "") + (s.get("text") or ""))))
    missing = []
    for b in beats:
        desc = ""
        if isinstance(b, dict):
            desc = (b.get("desc") or b.get("type") or "").strip()
        elif isinstance(b, str):
            desc = b.strip()
        # 过短/占位式节拍（如"转折"）信息量不足，参与匹配只会制造误报
        if len(_norm(desc)) < 10:
            continue
        grams = _bigrams(_norm(desc))
        if not grams:
            continue
        best = max((len(grams & sg) / len(grams) for sg in scene_grams), default=0.0)
        if best < coverage:
            missing.append(desc)
    return missing


_SENT_SPLIT = re.compile(r"[。！？…\n]+")


def _check_style(scenes: list[dict]) -> dict:
    """单句成段占比：以换行分段，段内句子数 ≤1 且较短视为单句段。"""
    paras = 0
    single = 0
    for s in scenes:
        for line in (s.get("text") or "").split("\n"):
            line = line.strip()
            if not line:
                continue
            paras += 1
            sents = [x for x in _SENT_SPLIT.split(line) if x.strip()]
            if len(sents) <= 1 and len(line) <= 30:
                single += 1
    return {
        "single_sentence_paragraphs": single,
        "total_paragraphs": paras,
        "ratio": round(single / paras, 3) if paras else 0.0,
    }


def check_chapter_quality(chapter: dict, packet: dict | None, prior_chapters: dict, cfg) -> dict:
    """章节质检门主入口：返回可 JSON 序列化的报告（不抛异常，失败降级为空报告）。"""
    qcfg = getattr(cfg, "quality", None) or {}
    threshold = float(qcfg.get("repetition_threshold", 0.70))
    window = int(qcfg.get("repetition_window", 3))
    try:
        scenes = chapter.get("scenes") or []
        duplicates = _check_duplicates(chapter, prior_chapters or {}, threshold, window)
        missing_beats = _check_beats(packet, scenes)
        style = _check_style(scenes)
        words = sum(len(s.get("text") or "") for s in scenes)
        target = 0
        genre = getattr(cfg, "genre", None)
        if genre is not None:
            target = int(getattr(genre, "words_per_chapter", 0) or 0)
        return {
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "threshold": threshold,
            "window": window,
            "duplicates": duplicates,
            "missing_beats": missing_beats,
            "style": style,
            "words": {"actual": words, "target": target},
            "ok": not duplicates and not missing_beats,
        }
    except Exception:
        return {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": True,
                "duplicates": [], "missing_beats": [], "error": "质检失败已降级"}
