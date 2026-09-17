"""叙事蓝图生成：明线主题、象征意象与暗线列表（机制型手法"暗线"的结构化数据）。

蓝图是作者视角资产：truth 字段只有作者与系统知道，正文只允许"表象"级别的暗示。
"""
from __future__ import annotations

import json
import uuid

from pydantic import BaseModel, Field

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured

from . import is_mock

SYSTEM_PROMPT = """你是小说的叙事架构师。基于立项书、总纲与已写章节，设计这份小说的叙事蓝图：
1. theme：一句话主题（作品真正想表达的东西）
2. motifs：可反复出现的象征意象（2-4 个，要有具体物件感，如"红色手环"）
3. dark_threads：暗线列表（1-3 条）。每条暗线包含：
   - name：暗线名（如"身世之秘"）
   - truth：隐藏真相（只有作者知道的事实，必须与已有设定自洽、可被已有细节支撑）
   - surface：读者可见表象（表面上呈现为什么，读者误以为是什么）
   - reveal_plan：揭示计划（大约哪一卷/哪种契机揭开，以及揭示前需要哪些铺垫）
   - related：关联人物名
要求：真相必须能从已有设定合理推出（不能凭空发明与世界观冲突的事实）；
表象与真相之间要有落差；各暗线揭示时机错开，不要挤在同一卷。"""


class DarkThread(BaseModel):
    id: str = ""
    name: str = ""
    truth: str = ""  # 隐藏真相（作者视角）
    surface: str = ""  # 读者可见表象
    reveal_plan: str = ""  # 揭示计划
    related: list[str] = Field(default_factory=list)


class NarrativeBlueprintModel(BaseModel):
    theme: str = ""
    motifs: list[str] = Field(default_factory=list)
    dark_threads: list[DarkThread] = Field(default_factory=list)


def generate_blueprint(
    concept: dict,
    outline: dict,
    chapters: dict,
    characters: list[dict],
    cfg: Config,
) -> dict:
    """生成叙事蓝图，返回 dict（含 theme/motifs/dark_threads，暗线带稳定 id）。"""
    if is_mock():
        return _mock_blueprint(concept, outline, chapters)
    user = (
        f"立项书：{json.dumps(concept, ensure_ascii=False)}\n"
        f"总纲：{json.dumps(outline, ensure_ascii=False)}\n"
        f"主要人物：{json.dumps([c.get('name') for c in characters or []], ensure_ascii=False)}\n"
        f"已写章节数：{len(chapters or {})}（章节约定见总纲/摘要，设计暗线时不得与其冲突）\n"
        "请生成叙事蓝图。"
    )
    messages = build_messages(SYSTEM_PROMPT, user, "blueprint", cfg.token_budget)
    llm = get_chat_model("creative", cfg)
    result = invoke_structured(llm, messages, schema=NarrativeBlueprintModel)
    return _with_ids(result.model_dump())


def _with_ids(bp: dict) -> dict:
    """为暗线补稳定 id（缺 id 时按名称生成）。"""
    for t in bp.get("dark_threads") or []:
        if not t.get("id"):
            t["id"] = "dt_" + uuid.uuid4().hex[:6]
    return bp


def dark_line_directive(blueprint: dict | None) -> str:
    """暗线蓝图 → 章节"暗示任务与揭示纪律"指令段（供规划与写作 prompt 注入）。

    蓝图是作者视角：真相对写手可见（否则暗示易穿帮），但纪律禁止正文直接点破。
    """
    if not blueprint:
        return ""
    threads = [
        t for t in (blueprint.get("dark_threads") or [])
        if isinstance(t, dict) and t.get("name")
    ]
    if not threads:
        return ""
    lines = [
        f"- 《{t['name']}》｜真相（仅作者知，正文严禁直接点破）：{t.get('truth', '')}｜"
        f"读者可见表象：{t.get('surface', '')}｜揭示计划：{t.get('reveal_plan', '')}"
        for t in threads
    ]
    motifs = blueprint.get("motifs") or []
    motif_line = f"\n象征意象（可在场景中自然复现，不解释）：{'、'.join(str(m) for m in motifs)}" if motifs else ""
    return (
        "<暗线蓝图（作者视角。正文对暗线只做自然暗示，任何人物不得直接说出真相）>\n"
        + "\n".join(lines)
        + motif_line
        + "\n本章纪律：每条暗线至多 1-2 处自然细节暗示，不解释、不强调；接近揭示计划的章节才加强暗示密度；"
        '若为某暗线埋点，在 foreshadow 中加一条 {kind: "暗线·线名", desc: 具体暗示}。\n</暗线蓝图（作者视角）>'
    )


def _mock_blueprint(concept: dict, outline: dict, chapters: dict) -> dict:
    title = concept.get("title_idea") or concept.get("logline") or "本作"
    return _with_ids(
        {
            "theme": f"围绕「{str(title)[:20]}」探讨身份与选择的代价（示例暗线蓝图）",
            "motifs": ["反复出现的旧物件", "一句被不同人复述的话"],
            "dark_threads": [
                {
                    "id": "dt_mock01",
                    "name": "身世之秘（示例）",
                    "truth": "主角在意的人与核心事件有隐藏关联（示例真相，请编辑）",
                    "surface": "读者以为两人只是偶然相遇的陌生人",
                    "reveal_plan": "第 2 卷末借旧物揭示，第 1 卷内每 3-4 章埋一处细节",
                    "related": [],
                }
            ],
        }
    )
