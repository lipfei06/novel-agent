"""仿写风格库：作者提供的风格样本条目，注入写手 prompt 作 few-shot 风格锚点。

设计与分工（详见对话记录）：
- 样本原文是**作者资产**（运行时粘贴的长文本），因此放库而不是 skill——skill 是
  包内静态 md，承载程序性知识；样本条目里的 digest（AI 提取的风格要点）才是
  skill 式知识，用"声线采样法"提取后随条目存储。
- 注入时原文（few-shot）+ 要点（directive）一起给写手：模仿口吻与节奏，
  情节仍服从章节规划。
- 文本上限 800 字/段：风格锚点贵在精准不在冗长，也控制 token 预算。
"""
from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured

from novel_agent.agents import is_mock

MAX_SAMPLE_CHARS = 800


class StyleEntry(BaseModel):
    """仿写风格条目：text 是模仿对象原文，digest 是提取出的风格要点。"""

    id: str
    name: str  # 样本名（如"我的文风"/"余华节奏"）
    text: str  # 样本原文（≤800 字）
    digest: str = ""  # 风格要点（声线采样法：人称/句式节奏/用词密度/对话比例/情绪温度）
    tags: list[str] = Field(default_factory=list)
    as_of: str = ""  # 入库时间 YYYY-MM


STYLE_PRESETS: list[StyleEntry] = [
    StyleEntry(
        id="style_cold_short",
        name="示例·冷峻短句",
        text=(
            "会议室的门关上时，我闻到了消毒水和廉价咖啡混合的气味。"
            "她把协议推过来。我没有动。窗外的天阴着，像一块没拧干的抹布。"
            "「签了，大家好聚好散。」她的声音很轻，轻得像在念一份快递单。"
            "我拿起笔，又放下。笔帽「咔」的一声，在安静的房间里格外清楚。"
        ),
        digest=(
            "第一人称过去式；句均 15 字以内的短句为主，动作句与对话句交替；"
            "情绪不直接说破，藏在物件与动作里（笔帽/天气/声音类比）；"
            "对话占比约四成，对白后常接一个动作细节收束。"
        ),
        tags=["职场", "冷峻", "第一人称"],
        as_of="2026-09",
    ),
    StyleEntry(
        id="style_zhihu_flow",
        name="示例·知乎体叙述",
        text=(
            "那年我二十八岁，在一家中厂做后端，手握三百万日活的推荐系统。"
            "裁员那天我没有吵，也没有闹，只是掏出手机拍了两张照片。"
            "后来证明，这两张照片值三百万。"
            "很多人问我怕不怕。怕。但我更怕的是：忍了这一次，下一次连拍的资格都没有。"
        ),
        digest=(
            "知乎回答式开场（年龄+身份+悬念数字）；先抑后扬的节奏；"
            "每段一个信息增量，段尾常埋短钩子；说理句与叙事句交替，金句收段。"
        ),
        tags=["知乎体", "第一人称", "爽文"],
        as_of="2026-09",
    ),
]


def _stat_digest(text: str) -> tuple[str, list[str]]:
    """确定性风格统计（mock 模式与 LLM 失败时的兜底要点）。"""
    t = (text or "").strip()
    sents = [s for s in re.split(r"[。！？…\n]+", t) if s.strip()]
    avg = round(len(t.replace("\n", "")) / max(1, len(sents)), 1)
    dialogue = sum(1 for s in sents if "「" in s or '"' in s or "“”" in s)
    ratio = round(dialogue / max(1, len(sents)) * 100)
    paras = len([p for p in t.split("\n") if p.strip()])
    digest = f"共 {len(t)} 字 / {paras} 段；句均 {avg} 字；对话句占比约 {ratio}%。"
    tags = []
    if avg <= 18:
        tags.append("短句")
    if ratio >= 35:
        tags.append("对话密集")
    return digest, tags


def analyze_style_sample(text: str, cfg: Config) -> dict:
    """声线采样法：从样本提取风格要点 + 标签。mock/失败时退回确定性统计。"""
    t = (text or "").strip()[:MAX_SAMPLE_CHARS]
    fallback_digest, fallback_tags = _stat_digest(t)
    if is_mock():
        return {"digest": fallback_digest, "tags": fallback_tags}
    try:
        system = (
            "你是文风分析师。对给定文本用'声线采样法'提取风格要点，输出 JSON："
            '{"digest": str, "tags": [str]}。digest 描述：叙述人称、句式节奏（句均长度/长短交错）、'
            "用词密度与惯用词类、对话占比与对白风格、情绪温度与表达方式，120 字以内；"
            "tags 给 2-4 个风格标签。只描述可模仿的形式特征，不复述内容。"
        )
        messages = build_messages(system, t, "cheap", cfg.token_budget)
        llm = get_chat_model("cheap", cfg)

        class _Out(BaseModel):
            digest: str = ""
            tags: list[str] = Field(default_factory=list)

        out = invoke_structured(llm, messages, schema=_Out)
        digest = (out.digest or "").strip() or fallback_digest
        tags = [x for x in out.tags if x.strip()][:4] or fallback_tags
        return {"digest": digest, "tags": tags}
    except Exception:
        return {"digest": fallback_digest, "tags": fallback_tags}


def new_style_entry(text: str, name: str = "", digest: str = "", tags: list[str] | None = None) -> StyleEntry:
    """从粘贴文本建条目：默认名 + 时效锚点。"""
    t = (text or "").strip()[:MAX_SAMPLE_CHARS]
    return StyleEntry(
        id=f"style_{datetime.now().strftime('%Y%m%d%H%M%S%f')[-10:]}",
        name=(name or "").strip() or f"样本 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        text=t,
        digest=digest,
        tags=tags or [],
        as_of=datetime.now().strftime("%Y-%m"),
    )
