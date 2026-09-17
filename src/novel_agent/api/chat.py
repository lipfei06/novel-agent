"""创作对话系统：每个"场景"一个多轮对话，AI 辅助讨论设定，可提出结构化方案供应用到表单。

场景（context）：
- concept 选题设计 / world 世界观 / characters 人物 / outline 总纲
- volume_{vol} 分卷 / chapter_{vol}_{ch} 章节编辑
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured
from novel_agent.storage import ProjectPaths

MAX_HISTORY = 20  # 每次发给模型的历史条数上限（超出只发最近 N 条）

CHAT_CONTEXTS = ("concept", "world", "characters", "outline")

# 动态场景白名单：chapter_{vol}_{ch} / volume_{vol}
_CONTEXT_RE = re.compile(r"^(?:chapter_\d+_\d+|volume_\d+)$")


def valid_context(context: str) -> bool:
    """对话场景白名单：固定场景 或 chapter_{vol}_{ch} / volume_{vol}。"""
    return context in CHAT_CONTEXTS or bool(_CONTEXT_RE.fullmatch(context))


def _chat_path(root: Path, project_id: str, context: str) -> Path:
    if not valid_context(context):
        raise ValueError(f"未知的对话场景: {context!r}")
    return ProjectPaths(root, project_id).data_dir / "chat" / f"{context}.json"


def load_history(path: Path) -> list[dict]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(path: Path, messages: list[dict]) -> None:
    from novel_agent.storage import write_json_atomic

    write_json_atomic(path, messages)


def _outline_grounding(values: dict, root: Path) -> str:
    """总纲助手的资料包：立项书/世界观/人物/蓝图/伏笔账本/手法/技法参考。"""
    from novel_agent.agents.packet import collect_pending_foreshadow
    from novel_agent.library.techniques import stage_guidance
    from novel_agent.library.searcher import tools_for_chapter

    parts = []
    c = values.get("concept")
    if c:
        parts.append("立项书：" + json.dumps(c, ensure_ascii=False)[:1800])
    w = values.get("world_bible")
    if w:
        parts.append("世界观概要：" + json.dumps(w, ensure_ascii=False)[:1200])
    chars = [x.get("name") for x in values.get("characters") or [] if isinstance(x, dict) and x.get("name")]
    if chars:
        parts.append("人物名册：" + "、".join(chars))
    chapters = values.get("chapters") or {}
    if chapters:
        parts.append(f"已写章节数：{len(chapters)}")
    bp = values.get("narrative_blueprint")
    if bp:
        parts.append("叙事蓝图（主题/意象/暗线）：" + json.dumps(bp, ensure_ascii=False)[:1200])
    ledger = collect_pending_foreshadow(values.get("writer_packets"))
    if ledger:
        parts.append("伏笔账本（已埋未收）：" + json.dumps(ledger, ensure_ascii=False)[:800])
    tech = stage_guidance(values.get("techniques"), ("planning",))
    if tech:
        parts.append(tech[:800])
    try:
        refs = tools_for_chapter(root, {"goal": c.get("logline", "") if c else "", "title": c.get("title_idea", "") if c else ""},
                                 top_k=3)
        if refs:
            parts.append("可参考的叙事技法：" + "；".join(
                f"{t['name']}（{t.get('usage_guidelines', '')[:60]}）" for t in refs))
    except Exception:
        pass
    if not parts:
        return ""
    return "\n<项目资料（建议必须基于这些资料，引用具体设定）>\n" + "\n".join(parts) + "\n</项目资料>\n"


def _volume_grounding(values: dict, root: Path, project_id: str, vol: int) -> str:
    """卷助手的资料包：全书结构概览（未来卷防剧透）+ 前情摘要 + 已写章节 + 伏笔账本。"""
    from novel_agent.memory import MidTermMemory
    from novel_agent.storage import ProjectPaths
    from novel_agent.agents.packet import collect_pending_foreshadow

    parts = []
    outline = values.get("outline") or {}
    vols = outline.get("volumes") or []
    past = [v for v in vols if v.get("volume", 0) < vol]
    future = [v.get("title", f"卷{v.get('volume')}") for v in vols if v.get("volume", 0) > vol]
    if past:
        past_brief = [
            {k: v.get(k) for k in ("volume", "title", "event_arc") if k in v}
            for v in past
        ]
        parts.append("之前各卷事件弧：" + json.dumps(past_brief, ensure_ascii=False)[:1200])
    if future:
        parts.append("后续卷（仅标题，防剧透勿展开）：" + "、".join(future))
    plans = values.get("volume_plans") or []
    plan = next((p for p in plans if p.get("volume") == vol), None)
    if plan:
        parts.append("本卷规划：" + json.dumps(
            {k: plan.get(k) for k in ("title", "event_arc", "foreshadow_seed", "foreshadow_payoff",
                                      "chapter_count", "ending_hook")},
            ensure_ascii=False)[:1200])
    recent = MidTermMemory(ProjectPaths(root, project_id).memory_dir / "mid_term.json").recent(8)
    if recent:
        parts.append("前情章节摘要：\n" + "\n".join(recent)[:1600])
    ledger = collect_pending_foreshadow(values.get("writer_packets"))
    if ledger:
        parts.append("伏笔账本（已埋未收）：" + json.dumps(ledger, ensure_ascii=False)[:800])
    if not parts:
        return ""
    return "\n<项目资料（建议必须基于这些资料，引用具体设定与伏笔）>\n" + "\n".join(parts) + "\n</项目资料>\n"


def _system_for(context: str, values: dict, cfg: Config, root: Path, project_id: str) -> str:
    if context == "concept":
        c = values.get("concept")
        current = f"当前立项书：{json.dumps(c, ensure_ascii=False)}\n" if c else "尚未生成立项书。\n"
        return (
            "你是小说选题策划助手。通过对话帮用户把立意聊成完整、可执行的立项书"
            "（核心卖点/目标读者/篇幅/基调/敏感红线）。" + current +
            "主动给建议、提问题引导用户明确想法。用户满意后可让系统「提出方案」输出正式立项书。"
        )
    if context == "world":
        w = values.get("world_bible")
        current = f"当前世界观：{json.dumps(w, ensure_ascii=False)}\n" if w else "尚未构建世界观。\n"
        return (
            "你是世界观构建助手。基于立项书帮用户完善世界观"
            "（地理/势力/力量体系/历史/习俗/术语）。" + current +
            "给出具体条目建议，用户满意后可「提出方案」输出完整世界观。"
        )
    if context == "characters":
        chars = values.get("characters")
        current = f"当前人物：{json.dumps(chars, ensure_ascii=False)}\n" if chars else "尚未设计人物。\n"
        return (
            "你是人物设计助手。基于立项书与世界观帮用户设计/完善人物（含分级：主/次/路人，含外貌与动机）。" + current +
            "给出人物建议，用户满意后可「提出方案」输出人物方案。"
        )
    if context == "outline":
        o = values.get("outline")
        current = f"当前总纲：{json.dumps(o, ensure_ascii=False)}\n" if o else "尚未生成总纲。\n"
        grounding = _outline_grounding(values, root)
        return (
            "你是全书架构助手。帮用户讨论并完善总纲（结构/分卷/转折/伏笔/结局）。" + current +
            grounding +
            "给出分卷与情节建议时必须基于上述资料，引用具体设定与伏笔，不要空泛。"
            "用户满意后可「提出方案」输出完整总纲。"
        )
    if context.startswith("volume_"):
        vol = int(context.split("_")[1])
        plans = values.get("volume_plans") or []
        plan = next((p for p in plans if p.get("volume") == vol), None)
        current = f"当前卷{vol}规划：{json.dumps(plan, ensure_ascii=False)}\n" if plan else f"卷{vol} 尚未规划。\n"
        grounding = _volume_grounding(values, root, project_id, vol)
        return (
            f"你是分卷规划助手。围绕卷{vol}帮用户完善事件弧/伏笔/章数/卷末悬念。{current}"
            + grounding +
            f"建议必须基于上述资料引用具体设定与伏笔，不要空泛。"
            f"用户满意后可「提出方案」输出该卷规划。"
        )
    if context.startswith("chapter_"):
        parts = context.split("_")
        vol, ch = int(parts[1]), int(parts[2])
        from novel_agent.types import WriterPacket

        from .routes import _build_writing_context  # 延迟导入避免循环

        packet = WriterPacket(volume=vol, chapter=ch)
        mem, rag = _build_writing_context(values, packet, cfg, root, project_id)
        chapter = (values.get("chapters") or {}).get(f"{vol}_{ch}")
        current = f"当前章节：{json.dumps(chapter, ensure_ascii=False)}\n" if chapter else f"第{vol}卷第{ch}章（尚未写）\n"
        # 本卷规划（近期目标，不剧透后文）
        plans = values.get("volume_plans") or (values.get("outline") or {}).get("volumes") or []
        plan = next((p for p in plans if p.get("volume") == vol), None)
        vol_info = f"当前卷{vol}规划：{json.dumps(plan, ensure_ascii=False)}\n" if plan else ""
        return (
            f"你是章节创作助手。帮用户讨论第{vol}卷第{ch}章怎么写/怎么改。参考以下项目上下文：\n"
            f"{vol_info}{current}{mem}\n{rag}\n给出具体建议。用户满意后可让系统「提出方案」输出新章节。"
        )
    return "你是创作助手，帮用户讨论并完善设定。"


def chat_reply(project_id: str, context: str, message: str, root: Path, cfg: Config, values: dict) -> tuple[str, list[dict]]:
    """发一条消息，返回回复与更新后的历史。"""
    from novel_agent.agents import is_mock
    from novel_agent.llm.cost import record_usage

    path = _chat_path(root, project_id, context)
    history = load_history(path)
    history.append({"role": "user", "content": message})

    if is_mock():
        reply = f"（模拟）已收到：{message}。可以继续补充想法，满意后让我「提出方案」整理成正式设定。"
    else:
        system = _system_for(context, values, cfg, root, project_id)
        system += (
            "\n\n【格式要求】请用清晰的结构化 Markdown 回复，像资深编辑和作者交流那样："
            "善用**加粗**强调关键结论、用 `-` 列表罗列要点、适当使用小节标题（## 或 ###）、"
            "用编号步骤说明方案，让作者一目了然、便于快速阅读。"
        )
        msgs = [{"role": "system", "content": system}] + history[-MAX_HISTORY:]
        # 规划类助手（总纲/卷）用 creative 档提升讨论质量，其余保持 cheap
        tier = "creative" if (context == "outline" or context.startswith("volume_")) else "cheap"
        llm = get_chat_model(tier, cfg)
        resp = llm.invoke(msgs)
        record_usage((getattr(resp, "response_metadata", {}) or {}).get("usage"))
        content = resp.content
        # 兼容 content 为列表（部分 OpenAI 兼容模型返回结构化片段）
        if isinstance(content, list):
            texts = [
                (p.get("text") if isinstance(p, dict) else str(p))
                for p in content
                if (isinstance(p, dict) and p.get("text")) or not isinstance(p, dict)
            ]
            reply = "\n".join(t for t in texts if t)
        else:
            reply = str(content)

    history.append({"role": "assistant", "content": reply})
    save_history(path, history)
    return reply, history


def propose(project_id: str, context: str, target: str, root: Path, cfg: Config, values: dict) -> dict:
    """根据对话历史，让 AI 输出某目标 schema 的完整方案（JSON），供前端应用到表单。"""
    from novel_agent.agents import is_mock
    from novel_agent.agents.character import CharacterList
    from novel_agent.agents.volume_plan import VolumePlanList
    from novel_agent.types import Chapter, Concept, Outline, WorldBible

    schema_map = {
        "concept": Concept,
        "world_bible": WorldBible,
        "characters": CharacterList,
        "outline": Outline,
        "volume_plan": VolumePlanList,
        "chapter": Chapter,
    }
    schema = schema_map.get(target)
    if schema is None:
        raise ValueError(f"不支持的目标：{target}")

    path = _chat_path(root, project_id, context)
    history = load_history(path)

    if is_mock():
        return _mock_proposal(target, values)

    system = _system_for(context, values, cfg, root, project_id)
    user = f"请根据以上对话与当前设定，输出一份完整的「{target}」方案（严格 JSON）。"
    msgs = [{"role": "system", "content": system}] + history[-MAX_HISTORY:] + [{"role": "user", "content": user}]
    llm = get_chat_model("creative", cfg)
    result = invoke_structured(llm, msgs, schema=schema)
    if isinstance(result, CharacterList) or isinstance(result, VolumePlanList):
        return result.model_dump()
    return result.model_dump()


def _mock_proposal(target: str, values: dict) -> dict:
    """mock 方案：在当前设定基础上带「AI 修订」标记，让应用后有可见变化（便于测试）。"""
    current = values.get(target)

    if target == "concept":
        if current:
            c = dict(current)
            c["logline"] = f"{c.get('logline', '')}【AI 修订：补强人物弧光与主题落点】"
            return c
        return {
            "genre": values.get("genre", "short_story"),
            "title_idea": "示例修订立意",
            "logline": "一个关于身份错位的故事（AI 修订版）",
            "core_selling": "修订后的核心卖点",
            "target_reader": "示例读者",
            "target_words": 15000,
            "volumes": 1,
            "tone": "示例基调",
            "red_lines": ["示例红线"],
        }
    if target == "world_bible":
        w = dict(current) if current else {}
        glossary = list(w.get("glossary", []))
        glossary.append({"name": "修订术语", "desc": "AI 修订新增"})
        w["glossary"] = glossary
        return w
    if target == "characters":
        items = list(values.get("characters") or [])
        return {"items": items}
    if target == "outline":
        o = dict(current) if current else {}
        o["structure"] = f"{o.get('structure', '起承转合')}【AI 修订：强化第三幕冲突】"
        return o
    if target == "volume_plan":
        return {"items": list(values.get("volume_plans") or [])}
    if target == "chapter":
        ch = dict(current) if current else {}
        return ch
    return current or {"_mock": True, "note": "（模拟方案）"}


def summarize_chat_design(messages: list[dict], cfg: Config) -> str:
    """把整段章节讨论提炼成【本章设计要点】（已共识的目标/冲突/钩子/注意点）。"""
    from novel_agent.agents import is_mock
    from novel_agent.llm.cost import record_usage

    if not messages:
        return ""
    if is_mock():
        for m in reversed(messages):
            if m.get("role") == "user":
                return f"（对话要点）{m['content']}"
        return ""

    system = (
        "你是创作协调人。把作者与 AI 关于某一章的讨论，提炼成简洁的【本章设计要点】：\n"
        "- 已达成共识的章节目标（本章要推进什么）\n"
        "- 冲突 / 关键情节\n"
        "- 章节钩子 / 结尾悬念\n"
        "- 需要注意的风格、细节或伏笔\n"
        "忽略客套与来回试探，只保留最终达成的共识。用中文输出，简洁、要点化。"
    )
    transcript = "\n".join(
        f"{'作者' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}" for m in messages
    )
    user = f"对话记录：\n{transcript}"
    llm = get_chat_model("cheap", cfg)
    resp = llm.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}])
    record_usage((getattr(resp, "response_metadata", {}) or {}).get("usage"))
    return str(resp.content)


def reset(project_id: str, context: str, root: Path) -> None:
    path = _chat_path(root, project_id, context)
    if path.exists():
        path.unlink()
