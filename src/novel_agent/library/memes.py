"""梗库：网络热梗/流行句式的结构化条目，供写手按章检索运用。

设计与约束（详见对话记录与 docs/智能体Skill体系需求分析.md §4 梗相关条目）：
- 热梗有强时效性，模型自带的梗天然过时——**梗由本库供给，写手只用候选，不生造**；
- 条目带 risk 分级（safe=化用 / caution=明梗注意平台尺度 / avoid=直接引用，禁用）；
- populate_memes 用 LLM 批量生成条目并按名称去重，减少人工录入；
  生成条目的时效以 as_of（入库年月）为锚，由使用者自行判断是否仍流行。
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from novel_agent.config import Config
from novel_agent.llm import build_messages, get_chat_model, invoke_structured

from novel_agent.agents import is_mock

RISK_LEVELS = ("safe", "caution", "avoid")
MEME_KINDS = ("句式梗", "名场面梗", "谐音梗", "情绪梗", "行话梗")


class MemeEntry(BaseModel):
    """梗库条目。description 供索引与卡片展示；content 是梗本体。"""

    id: str
    name: str  # 梗名（去重键）
    category: str = "通用"  # 题材类目：职场 / 情感 / 校园 / 通用 …
    kind: str = "句式梗"  # MEME_KINDS 之一
    description: str = ""  # 一句话说明（索引 + 卡片）
    content: str = ""  # 梗本体（示例句/用法式）
    usage: str = ""  # 告诉写手怎么用（什么剧情/什么情绪下用）
    emotion: str = ""  # 情绪色彩：喜 / 丧 / 讽 / 燃 …
    risk: str = "safe"  # safe / caution / avoid
    as_of: str = ""  # 时效锚点 YYYY-MM（入库时间，流行性由使用者判断）
    tags: list[str] = Field(default_factory=list)


class MemeList(BaseModel):
    items: list[MemeEntry] = Field(default_factory=list)


MEME_PRESETS: list[MemeEntry] = [
    MemeEntry(
        id="meme_youhua",
        name="被优化了",
        category="职场",
        kind="行话梗",
        description="用企业裁员的委婉语'优化/N+1'自嘲被抛弃，反差感自带黑色幽默",
        content="示例句：「我被亲妈优化了。N+1呢？我连N都没有。」",
        usage="角色遭遇抛弃/裁员/被牺牲时的一句自嘲；适合丧中带讽的情绪转折点",
        emotion="讽",
        risk="safe",
        as_of="2026-09",
        tags=["职场", "裁员", "自嘲"],
    ),
    MemeEntry(
        id="meme_huayibing",
        name="画大饼",
        category="职场",
        kind="句式梗",
        description="用'画饼/饼太大了吃不消'吐槽空头承诺",
        content="示例句：「他又开始画饼了，这块饼够我吃到退休。」",
        usage="上级/长辈空头许愿的场面；适合吐槽型角色",
        emotion="讽",
        risk="safe",
        as_of="2026-09",
        tags=["职场", "承诺", "吐槽"],
    ),
    MemeEntry(
        id="meme_neijuan",
        name="内卷/卷王",
        category="职场",
        kind="行话梗",
        description="用'卷'形容过度竞争，'卷王'指竞争中最狠的人",
        content="示例句：「凌晨三点的写字楼里，卷王还在卷，我选择躺平当个卧龙。」",
        usage="职场/校园竞争剧情的氛围词；也可作角色标签",
        emotion="丧",
        risk="safe",
        as_of="2026-09",
        tags=["职场", "竞争", "躺平"],
    ),
    MemeEntry(
        id="meme_tangping",
        name="躺平",
        category="职场",
        kind="情绪梗",
        description="用'躺平/摆烂'表达放弃内卷的姿态",
        content="示例句：「他们卷他们的，我先躺为敬。」",
        usage="角色放弃挣扎/以退为进的表态；常与内卷对仗使用",
        emotion="丧",
        risk="safe",
        as_of="2026-09",
        tags=["职场", "态度", "反差"],
    ),
    MemeEntry(
        id="meme_pUA",
        name="职场PUA",
        category="职场",
        kind="行话梗",
        description="用'PUA/画饼+打压套餐'指精神控制式管理",
        content="示例句：「打击你、再给你画个饼，经典PUA套餐，一步都没少。」",
        usage="主角识破操纵时的一句点破；适合觉醒/反转场景",
        emotion="讽",
        risk="safe",
        as_of="2026-09",
        tags=["职场", "操纵", "觉醒"],
    ),
    MemeEntry(
        id="meme_shechu",
        name="社死",
        category="通用",
        kind="情绪梗",
        description="'社会性死亡'缩写，形容当众尴尬到想原地消失",
        content="示例句：「那一秒我当众社死，恨不得当场注册个新身份。」",
        usage="出糗场景的夸张化处理；喜剧调剂首选",
        emotion="喜",
        risk="safe",
        as_of="2026-09",
        tags=["尴尬", "搞笑", "日常"],
    ),
    MemeEntry(
        id="meme_fanersai",
        name="凡尔赛",
        category="通用",
        kind="句式梗",
        description="用抱怨的壳炫耀的核，'凡尔赛文学'式低调炫富",
        content="示例句：「好烦哦，老公又把黑卡给我随便刷，一点都不心疼。」",
        usage="炫富/装X角色的说话方式；可整段模仿制造喜剧感",
        emotion="喜",
        risk="safe",
        as_of="2026-09",
        tags=["炫耀", "反讽", "日常"],
    ),
    MemeEntry(
        id="meme_jiarenmen",
        name="家人们谁懂啊",
        category="通用",
        kind="句式梗",
        description="短视频式开场白，'家人们谁懂啊'引出吐槽，自带倾诉感",
        content="示例句：「家人们谁懂啊，相亲对象简历上写的是'吃喝玩乐十级学者'。」",
        usage="第一人称叙事的吐槽开场/内心OS；知乎体适配度高",
        emotion="喜",
        risk="safe",
        as_of="2026-09",
        tags=["吐槽", "第一人称", "开场"],
    ),
    MemeEntry(
        id="meme_yifa_ruwei",
        name="听我说谢谢你",
        category="通用",
        kind="名场面梗",
        description="'听我说谢谢你'从感恩手势舞异化为阴阳怪气的'感谢'",
        content="示例句：「他递来辞职信，我内心默默放起了《听我说谢谢你》。」",
        usage="表面感谢实则送客/泄愤的反讽场景",
        emotion="讽",
        risk="caution",
        as_of="2026-09",
        tags=["反讽", "歌曲", "阴阳怪气"],
    ),
    MemeEntry(
        id="meme_yuanmen",
        name="命运的齿轮开始转动",
        category="通用",
        kind="句式梗",
        description="'命运的齿轮开始转动'用于标记重大转折，自带宿命感解说腔",
        content="示例句：「他按下接听键的那一刻，命运的齿轮开始转动——虽然当时他只是在点外卖。」",
        usage="章节转折点的旁白式标记；后接反差内容可产喜剧效果",
        emotion="燃",
        risk="safe",
        as_of="2026-09",
        tags=["转折", "旁白", "宿命"],
    ),
]


_POPULATE_SYSTEM = (
    "你是网络流行文化研究员。根据给定的题材方向，整理当前（以入库时间为准）中文网文/社交媒体上"
    "常见、可直接用于小说对白与叙述的网络热梗与流行句式。\n"
    "要求：\n"
    "- 每条给：梗名（name）、题材类目（category）、类型 kind（句式梗/名场面梗/谐音梗/情绪梗/行话梗）、"
    "一句话说明 description、梗本体 content（含示例句）、用法 usage（什么剧情/情绪下用）、"
    "情绪色彩 emotion（喜/丧/讽/燃等）、风险 risk（safe=化用安全；caution=明梗可能被平台限流；avoid=涉及直接引用他人作品台词，不要给 avoid 的条目）、"
    "标签 tags\n"
    "- 只整理结构化知识，不创作小说内容；每条 content 是梗的用法示例，不是正文\n"
    "- 不要与已有条目重名。只输出 JSON。"
)


def populate_memes(root, topic: str, count: int, cfg: Config, store=None) -> list[MemeEntry]:
    """用 LLM 批量生成梗条目入库（按名称去重）。返回实际新增条目。"""
    from novel_agent.library.searcher import default_store

    store = store or default_store(root)
    count = max(1, min(int(count or 10), 30))
    topic = str(topic or "通用").strip()[:60]
    existing = {e.name for e in store.list("meme")}

    if is_mock():
        new = [
            MemeEntry(
                id=f"meme_mock_{i}_{datetime.now().strftime('%m%d%H%M%S')}",
                name=f"（模拟梗{topic}{i}）",
                category=topic,
                kind="句式梗",
                description=f"模拟填充的{topic}类梗条目 {i}",
                content=f"示例句：这也太{topic}了",
                usage=f"{topic}类剧情的情绪调剂",
                emotion="喜",
                risk="safe",
                as_of=datetime.now().strftime("%Y-%m"),
                tags=[topic, "模拟"],
            )
            for i in range(1, count + 1)
        ]
    else:
        user = (
            f"题材方向：{topic}\n"
            f"已有梗名（勿重复）：{ '、'.join(sorted(existing))[:1200] or '（空）' }\n"
            f"请整理 {count} 条梗条目。"
        )
        llm = get_chat_model("cheap", cfg)
        messages = build_messages(_POPULATE_SYSTEM, user, "state_update", cfg.token_budget)
        result = invoke_structured(llm, messages, schema=MemeList)
        new = []
        now = datetime.now().strftime("%Y-%m")
        for e in result.items:
            if not e.name.strip() or e.name in existing:
                continue
            if e.risk not in RISK_LEVELS or e.risk == "avoid":
                e = e.model_copy(update={"risk": "safe"})
            existing.add(e.name)
            new.append(e.model_copy(update={
                "id": f"meme_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(new)}",
                "as_of": e.as_of or now,
            }))

    added = []
    for entry in new:
        try:
            store.add("meme", entry)
            added.append(entry)
        except ValueError:
            continue  # 同 id 极小概率撞车，跳过
    return added


_EXTRACT_SYSTEM = (
    "你是网络流行文化研究员。作者会粘贴一段素材（网页摘录/段子/梗的罗列/聊天记录等），"
    "从中提取可复用于小说写作的网络梗与流行句式，输出结构化条目。\n"
    "要求：\n"
    "- 每条给：梗名（name）、题材类目（category）、类型 kind（句式梗/名场面梗/谐音梗/情绪梗/行话梗）、"
    "一句话说明 description、梗本体 content（含示例句）、用法 usage、情绪色彩 emotion、"
    "风险 risk（素材里是化用/自创 → safe；明确指向某个流行梗原句 → caution；"
    "内容是直接引用他人作品台词/歌词 → avoid）、标签 tags\n"
    "- 提取素材里真实存在的梗，不要自己发明新梗；素材里没有可用梗就返回空列表\n"
    "- 与已有梗重名的跳过。只输出 JSON。"
)


def extract_memes_from_text(root, text: str, cfg: Config, store=None) -> list[MemeEntry]:
    """从作者粘贴的素材中提取梗条目入库（按名称去重）。返回实际新增条目。"""
    from novel_agent.library.searcher import default_store

    store = store or default_store(root)
    text = str(text or "").strip()
    if not text:
        return []
    existing = {e.name for e in store.list("meme")}

    if is_mock():
        new = [
            MemeEntry(
                id=f"meme_extract_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                name=f"（模拟提取）{text[:12]}",
                category="通用",
                kind="句式梗",
                description="模拟从粘贴素材提取的条目",
                content=text[:60],
                usage="素材原文出现，用法待补充",
                emotion="喜",
                risk="safe",
                as_of=datetime.now().strftime("%Y-%m"),
                tags=["提取"],
            )
        ]
    else:
        user = (
            f"已有梗名（勿重复）：{'、'.join(sorted(existing))[:1200] or '（空）'}\n"
            f"粘贴素材：\n{text[:4000]}\n请提取梗条目。"
        )
        llm = get_chat_model("cheap", cfg)
        messages = build_messages(_EXTRACT_SYSTEM, user, "state_update", cfg.token_budget)
        result = invoke_structured(llm, messages, schema=MemeList)
        new = []
        now = datetime.now().strftime("%Y-%m")
        for e in result.items:
            if not e.name.strip() or e.name in existing:
                continue
            if e.risk not in RISK_LEVELS:
                e = e.model_copy(update={"risk": "safe"})
            existing.add(e.name)
            new.append(e.model_copy(update={
                "id": f"meme_x_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(new)}",
                "as_of": e.as_of or now,
            }))

    added = []
    for entry in new:
        try:
            store.add("meme", entry)
            added.append(entry)
        except ValueError:
            continue
    return added


def must_use_memes_text(root, names: list[str]) -> str:
    """作者为本章指定的必用梗：按名称在梗库精确查找并渲染为硬性写作指令块。

    库中找不到的名称列入"未找到"并忽略——必用梗必须来自库（有用法说明与风险分级），
    不接受裸文本直塞写作提示。
    """
    from novel_agent.library.searcher import default_store

    wanted = [str(n or "").strip() for n in (names or [])]
    wanted = [n for n in wanted if n]
    if not wanted:
        return ""
    store = default_store(root)
    found: dict[str, MemeEntry] = {}
    for e in store.list("meme"):
        if e.name in wanted and e.risk != "avoid":
            found[e.name] = e
    missing = [n for n in wanted if n not in found]
    if not found:
        return ""
    lines = [
        "以下梗为作者指定，本章正文**必须**至少使用其中每一个一次："
        "自然融入对白或叙述，放在合适的情绪转折点，不可生硬堆砌，不要解释梗本身。"
    ]
    for i, e in enumerate(found.values(), 1):
        line = f"{i}. [{e.name}] {e.kind}：{e.content}"
        if e.usage:
            line += f" —— 用法：{e.usage}"
        if e.risk == "caution":
            line += "（caution：注意平台尺度，可化用结构不直接引用原句）"
        lines.append(line)
    if missing:
        lines.append(f"（作者指定但梗库中未找到、已忽略：{'、'.join(missing)}）")
    return "<本章必用梗>\n" + "\n".join(lines) + "\n</本章必用梗>"
