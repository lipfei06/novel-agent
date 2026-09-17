"""Stage4b 章级 packet Agent（小章节规划）。"""
from __future__ import annotations

import json

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured, style_directive
from novel_agent.types import Character, Outline, VolumePlan, WriterPacket

from . import is_mock

SYSTEM_PROMPT = """你是一位章节规划师。为单章生成 writer_packet：场景目标、冲突、情绪节拍、章节钩子、
埋/收伏笔、出场人物与视角。内容服务于本卷事件弧。

【防剧透规则】
- 你只能看到当前卷的规划与全书结构的概览，**不知道后文/结局**——不要把后文真相、结局、未来的
  核心转折提前泄露到本章设计中
- foreshadow 只填【本章要埋下的伏笔种子】，不要写将来如何回收（payoff）"""


def _scoped_outline(outline: dict, volume: int) -> dict:
    """裁剪总纲：只给当前卷，隐藏结局/未来卷/核心转折/全局伏笔回收点，防止前文剧透后文。"""
    vols = outline.get("volumes") or []
    current = next((v for v in vols if v.get("volume") == volume), None)
    scoped_vols = []
    if current:
        v = dict(current)
        v.pop("foreshadow_payoff", None)  # 伏笔回收点属于未来，隐藏
        scoped_vols.append(v)
    return {
        "premise": outline.get("premise", ""),
        "structure": outline.get("structure", ""),
        "volumes": scoped_vols,
        # 隐去：ending、core_events（未来转折）、foreshadowing（全局伏笔清单含 payoff）
    }


def collect_pending_foreshadow(writer_packets: dict | None) -> list[dict]:
    """从已生成的章节规划中汇总"已埋下"的伏笔，供后续章节规划参考回收。

    返回 [{chapter: "1_3", desc: ...}, ...]；这是防"挖坑不填"的账本。
    """
    items: list[dict] = []
    for key, pk in (writer_packets or {}).items():
        for f in (pk or {}).get("foreshadow") or []:
            if isinstance(f, dict) and (f.get("desc") or "").strip():
                items.append({"chapter": key, "kind": f.get("kind", "seed"), "desc": f["desc"].strip()})
    return items


def generate_writer_packet(
    volume_plan: VolumePlan | dict,
    outline: Outline | dict,
    characters: list[Character] | list[dict],
    chapter_no: int,
    cfg: Config,
    discussion: str = "",
    pending_foreshadow: list[dict] | None = None,
    techniques: list[dict] | None = None,
    blueprint: dict | None = None,
    tools: list[dict] | None = None,
) -> WriterPacket:
    vp = volume_plan.model_dump() if hasattr(volume_plan, "model_dump") else dict(volume_plan)
    outline_data = outline.model_dump() if hasattr(outline, "model_dump") else dict(outline)
    chars = [c.model_dump() if hasattr(c, "model_dump") else dict(c) for c in characters]
    if is_mock():
        return _mock_packet(vp, chars, chapter_no)
    scoped = _scoped_outline(outline_data, int(vp.get("volume", 1)))
    extra = f"\n<作者与AI讨论的设计>\n{discussion}\n</作者与AI讨论的设计>" if discussion else ""
    from novel_agent.agents.blueprint import dark_line_directive
    from novel_agent.library.techniques import stage_guidance

    tech_note = stage_guidance(techniques, ("planning",))
    if tech_note:
        tech_note = f"\n<写作手法要求>\n{tech_note}\n</写作手法要求>"
    dark_note = dark_line_directive(blueprint)
    tool_note = ""
    if tools:
        refs = [f"- {t.get('name')}（{t.get('category', '')}）：{t.get('usage_guidelines', '')}" for t in tools]
        tool_note = "\n<可用叙事技法参考（按本章需要取用，不强塞）>\n" + "\n".join(refs) + "\n</可用叙事技法参考>"
    foreshadow_note = ""
    if pending_foreshadow:
        foreshadow_note = (
            f"\n<已埋伏笔清单（此前章节埋下、尚未回收）。若本卷规划要求回收某条且本章合适，"
            f"可设计回收（foreshadow 填 kind=payoff）；否则不要强行回收，但也不要写出与其矛盾的内容："
            f"{json.dumps(pending_foreshadow, ensure_ascii=False)}>"
        )
    user = (
        f"卷计划：{json.dumps(vp, ensure_ascii=False)}\n"
        f"总纲（仅当前卷，后文已隐去）：{json.dumps(scoped, ensure_ascii=False)}\n"
        f"人物：{json.dumps(chars, ensure_ascii=False)}\n"
        f"请为第 {chapter_no} 章生成 packet。{extra}{foreshadow_note}{tech_note}{dark_note}{tool_note}"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "packet", cfg.token_budget, style=style_directive(cfg))
    llm = get_chat_model("creative", cfg)
    return invoke_structured(llm, messages, schema=WriterPacket)


def _mock_packet(vp: dict, chars: list[dict], chapter_no: int) -> WriterPacket:
    names = [c.get("name", "") for c in chars if c.get("name")]
    arc = vp.get("event_arc") or ["推进卷情节"]
    return WriterPacket(
        volume=int(vp.get("volume", 1)),
        chapter=chapter_no,
        title=f"第{chapter_no}章",
        goal=arc[0],
        conflicts=["示例冲突"],
        beats=[{"order": 1, "type": "开场", "desc": "场景建立"}, {"order": 2, "type": "冲突", "desc": "矛盾升级"}],
        hook="章节钩子",
        foreshadow=[{"kind": "seed", "desc": "示例伏笔"}],
        characters=names,
        pov=names[0] if names else "主角",
        reference_seeds=["示例"],
    )
