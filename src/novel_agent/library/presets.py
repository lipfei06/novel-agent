"""预置写作基础库条目：性格库 + 小说工具库 + 人物模板库 + 写作手法库 + 梗库。

作为 seed 写入共享库（仅当对应 id 不存在）。开发者/用户可继续用 CLI 增补；
梗库另支持 AI 填充（library.memes.populate_memes）。
"""
from __future__ import annotations

from .memes import MEME_PRESETS
from .styles import STYLE_PRESETS
from .personality import PersonalityEntry
from .techniques import TechniqueEntry
from .tools import NovelToolEntry
from novel_agent.types.character_template import CharacterTemplate

PERSONALITY_PRESETS: list[PersonalityEntry] = [
    PersonalityEntry(
        id="pers_wenhe_zhengyi",
        name="温和正直型",
        category="理想主义",
        tags=["正直", "温和", "善良", "信念"],
        description="重视原则与正义，待人温和，但可能因过于理想化而吃亏。",
        behavior_patterns=["路见不平会出手", "宁可自己受损也不违背原则", "对弱者有天然保护欲"],
        dialogue_style="语气温和，多讲道理与承诺，少用嘲讽与威胁",
        strengths=["有凝聚力", "令人信赖", "坚持原则"],
        weaknesses=["天真", "容易轻信", "不愿妥协"],
        growth_direction="在坚守信念的同时学会审时度势与提防人心",
        example_reference=["传统侠客", "救赎者原型"],
        applicable_genres=["玄幻", "仙侠", "都市", "传统"],
    ),
    PersonalityEntry(
        id="pers_kuangye_guayan",
        name="孤僻寡言型",
        category="内敛",
        tags=["孤僻", "寡言", "戒备", "高冷"],
        description="话少、边界感强，内心有创伤或秘密，习惯独来独往。",
        behavior_patterns=["回避群体场合", "用行动代替言语", "对信任极度谨慎"],
        dialogue_style="句子短，常省略主语，多用沉默与眼神动作描写",
        strengths=["观察敏锐", "独立坚韧", "关键时不掉链子"],
        weaknesses=["不善表达", "拒绝帮助", "自我封闭"],
        growth_direction="从封闭走向有限度的信任与接纳他人",
        example_reference=["独行侠", "冷面杀手"],
        applicable_genres=["玄幻", "仙侠", "都市", "悬疑", "传统"],
    ),
    PersonalityEntry(
        id="pers_rexue_chongdong",
        name="热血冲动型",
        category="外向行动派",
        tags=["热血", "冲动", "直率", "行动力"],
        description="情绪外放、敢作敢当，遇事先冲再做，常靠直觉行事。",
        behavior_patterns=["一言不合就动手", "为朋友两肋插刀", "冲动后追悔"],
        dialogue_style="音量高、语速快，多用感叹与直接表达",
        strengths=["有感染力", "勇气十足", "行动力强"],
        weaknesses=["鲁莽", "缺乏耐心", "易被激怒"],
        growth_direction="从凭冲动行事到学会克制与谋略",
        example_reference=["少年侠客", "热血主角"],
        applicable_genres=["玄幻", "仙侠", "热血", "运动", "都市"],
    ),
    PersonalityEntry(
        id="pers_lengku_moulve",
        name="冷酷谋略型",
        category="理智型",
        tags=["冷酷", "算计", "理性", "谋略"],
        description="理性至上，习惯计算利弊，感情内敛，必要时可做出残酷决断。",
        behavior_patterns=["先权衡利弊再行动", "设局让人钻", "把情感当作可利用变量"],
        dialogue_style="简洁冷静，常反问，话里有话",
        strengths=["布局深远", "临危不乱", "执行力强"],
        weaknesses=["缺乏温情", "多疑", "难以信任他人"],
        growth_direction="从纯理性到学会珍视少数人与情感",
        example_reference=["军师", "枭雄", "腹黑反派"],
        applicable_genres=["玄幻", "仙侠", "权谋", "都市", "传统"],
    ),
    PersonalityEntry(
        id="pers_youyu_minrui",
        name="忧郁敏感型",
        category="感性",
        tags=["忧郁", "敏感", "细腻", "共情"],
        description="心思细腻，感知力强，情绪起伏大，容易沉浸于回忆与伤痛。",
        behavior_patterns=["对微小信号高度敏感", "深夜emo", "用艺术或写作排解"],
        dialogue_style="温柔留白，多隐喻与内心独白",
        strengths=["洞察人心", "有创造力", "共情力强"],
        weaknesses=["脆弱", "内耗", "悲观"],
        growth_direction="从被情绪吞噬到学会与情绪共处并转化为力量",
        example_reference=["文艺主角", "天才病弱角色"],
        applicable_genres=["都市", "传统", "言情", "悬疑"],
    ),
    PersonalityEntry(
        id="pers_shishi_quanbian",
        name="市侩圆滑型",
        category="圆滑",
        tags=["市侩", "圆滑", "精明", "识时务"],
        description="见人说人话，见鬼说鬼话，精于钻营但内心可能保留底线或温情。",
        behavior_patterns=["先看人下菜碟", "遇强则服遇弱则欺", "关键时暴露真心"],
        dialogue_style="油嘴滑舌，多奉承与场面话，偶露真话",
        strengths=["生存能力强", "人脉广", "应变快"],
        weaknesses=["势利", "缺乏立场", "被看穿后信用破产"],
        growth_direction="从见风使舵到在利益面前守住一条底线",
        example_reference=["市井商人", "墙头草配角"],
        applicable_genres=["都市", "传统", "历史", "权谋"],
    ),
    PersonalityEntry(
        id="pers_xiaoxiong",
        name="枭雄型",
        category="权谋枭雄",
        tags=["枭雄", "野心", "果决", "用人"],
        description="胸怀大志、杀伐果断，深谙人性与权术；为成大事不拘小节，心中自有一杆秤。",
        behavior_patterns=["善于笼络人心，也善于弃子", "决策快、不犹豫", "恩威并施"],
        dialogue_style="沉稳有分量，恩威并用，话中有话",
        strengths=["格局大", "执行力强", "识人善任"],
        weaknesses=["多疑", "难以完全信任人", "为达目的可牺牲感情"],
        growth_direction="在成就霸业的同时学会真正信任与珍视少数人",
        example_reference=["乱世霸主", "枭雄主角", "枭雄反派"],
        applicable_genres=["玄幻", "仙侠", "权谋", "历史", "都市"],
    ),
    PersonalityEntry(
        id="pers_renyi",
        name="仁义型",
        category="仁义",
        tags=["仁义", "重情义", "大义", "宽厚"],
        description="以仁义立身，重情重义，宁可自己吃亏也不肯辜负他人；是团队的精神支柱。",
        behavior_patterns=["路见不平必出头", "善待弱小与旧人", "恩怨分明但不赶尽杀绝"],
        dialogue_style="语气诚恳，多替他人着想，重承诺",
        strengths=["得人心", "有号召力", "信守承诺"],
        weaknesses=["容易心软", "背负过多", "被利用仁义拿捏"],
        growth_direction="在坚守仁义的同时学会防人与雷霆手段",
        example_reference=["仁德君主", "侠义之士", "精神领袖"],
        applicable_genres=["玄幻", "仙侠", "武侠", "历史", "传统"],
    ),
    PersonalityEntry(
        id="pers_yinxian",
        name="阴险型",
        category="阴险",
        tags=["阴险", "伪装", "算计", "隐忍"],
        description="表面和善无害，暗藏机锋，擅长设局与借刀杀人，隐忍极深。",
        behavior_patterns=["示弱博同情", "暗中布局让人背锅", "关键时刻背后一刀"],
        dialogue_style="温和客套，滴水不漏，极少流露真实意图",
        strengths=["隐蔽性强", "布局深远", "情绪不外露"],
        weaknesses=["难获真信任", "树敌于无形", "一旦暴露信用全失"],
        growth_direction="从阴暗算计到直面欲望、放下伪装（或彻底黑化）",
        example_reference=["笑面虎", "幕后黑手", "伪善反派"],
        applicable_genres=["权谋", "都市", "悬疑", "传统"],
    ),
    PersonalityEntry(
        id="pers_xiayi",
        name="侠义型",
        category="侠义",
        tags=["侠义", "快意恩仇", "洒脱", "路见不平"],
        description="快意恩仇、仗剑走天涯，重然诺、轻生死，不慕名利。",
        behavior_patterns=["路见不平拔刀相助", "千金一诺", "不为富贵折腰"],
        dialogue_style="爽朗干脆，语带豪气，偶尔放荡不羁",
        strengths=["赤诚", "果敢", "广交天下友"],
        weaknesses=["冲动", "不懂周旋", "易被人以侠义相胁"],
        growth_direction="从独行侠到懂得携手与谋划",
        example_reference=["游侠", "浪子剑客"],
        applicable_genres=["武侠", "仙侠", "玄幻", "传统"],
    ),
]

TOOL_PRESETS: list[NovelToolEntry] = [
    NovelToolEntry(
        id="tool_foreshadow",
        name="伏笔",
        category="叙事技巧",
        description="在早期埋下看似寻常、后期兑现的信息或物件，制造恍然大悟的阅读体验。",
        usage_guidelines="埋点要轻、要自然，回收要准、要有冲击；埋与收之间隔得足够远才有效。",
        examples=["第一章角落的一把旧钥匙，终章打开密室的锁", "配角随口一句预言，后期应验"],
        chapter_placement="跨章",
        common_mistakes=["埋得太明显", "忘记回收", "回收时强解释"],
    ),
    NovelToolEntry(
        id="tool_xuannian",
        name="悬念",
        category="节奏控制",
        description="通过未解问题或危险逼近把读者的注意力钉住，驱动翻页。",
        usage_guidelines="章末留问题或危机；悬念要具体、可被期待，且不能永远不兑现。",
        examples=["门外是谁在敲门？", "主角发现的玉佩和失踪的妹妹有什么关联？"],
        chapter_placement="中段/结尾",
        common_mistakes=["悬念悬而不决令读者疲惫", "答案配不上铺垫"],
    ),
    NovelToolEntry(
        id="tool_gouzi",
        name="章节钩子",
        category="节奏控制",
        description="章节结尾的强引力句，让读者必须读下一章。",
        usage_guidelines="钩子=新信息/新危机/反转预告；短、有画面感、不剧透关键真相。",
        examples=["就在这时，他手中的令牌亮起了红光", "她认出了那柄剑——是十年前父亲背上的那把"],
        chapter_placement="结尾",
        common_mistakes=["每章都用同一种钩子", "钩子与正文脱节"],
    ),
    NovelToolEntry(
        id="tool_fanzhuan",
        name="反转",
        category="情节装置",
        description="情节走向的意外转向，颠覆读者既有认知，带来强烈情绪冲击。",
        usage_guidelines="反转前需留合理线索（避免机械降神）；一次反转配一次情感释放，不宜连续硬转。",
        examples=["救人者竟是幕后黑手", "看似反派的人保护了主角"],
        chapter_placement="中段/结尾",
        common_mistakes=["无铺垫的强行反转", "为反转而反转导致逻辑崩塌"],
    ),
    NovelToolEntry(
        id="tool_chongtu",
        name="冲突设计",
        category="情节装置",
        description="角色目标与障碍的对抗，推动情节和人物成长的核心引擎。",
        usage_guidelines="外部冲突（对手/环境）与内部冲突（自我挣扎）交替；每个场景尽量有一个具体目标冲突。",
        examples=["利益争夺", "理念对立", "身份暴露"],
        chapter_placement="全程",
        common_mistakes=["冲突单一重复", "冲突靠误会硬凑"],
    ),
    NovelToolEntry(
        id="tool_qingxu_jiezou",
        name="情绪节拍",
        category="情绪营造",
        description="场景内情绪的起承转合编排，让读者与角色同频共振。",
        usage_guidelines="一个场景聚焦一种主导情绪；张弛交替，高潮前有铺垫、高潮后有喘息。",
        examples=["先平缓日常 → 突发危机 → 紧张追逐 → 短暂平安 → 新威胁"],
        chapter_placement="全程",
        common_mistakes=["全程高能导致疲劳", "情绪转折生硬"],
    ),
    NovelToolEntry(
        id="tool_shijiao",
        name="叙事视角",
        category="视角",
        description="以何种人物视角呈现信息，决定读者知道多少、共情谁。",
        usage_guidelines="选信息最有张力的一方做视角；限制视角可制造信息差与悬念。",
        examples=["主角第一人称", "第三人称贴主角肩", "反派视角透露阴谋"],
        chapter_placement="全程",
        common_mistakes=["视角随意跳转造成混乱", "视角人物知道太多泄底"],
    ),
]

CHARACTER_TEMPLATE_PRESETS: list[CharacterTemplate] = [
    CharacterTemplate(
        id="ct_gu_gao_jian_ke",
        name="孤高剑客",
        role="supporting",
        description="身负旧怨、寡言冷峻的用剑高手，表面拒人千里，内心有放不下的执念。",
        motivation="为旧日恩仇或诺言而活，最终学会放下",
        flaw="固执、不肯求助",
        arc=[{"stage": "start", "change": "独来独往"}, {"stage": "mid", "change": "被迫与人同行"}, {"stage": "end", "change": "承认伙伴的价值"}],
        behavior="少语、行动先于言语、对承诺极其认真",
        dialogue_style="句子短促，省略主语，多用行动描写代替表态",
        tags=["冷峻", "剑客", "寡言"],
        applicable_genres=["玄幻", "仙侠", "武侠", "传统"],
    ),
    CharacterTemplate(
        id="ct_tian_zhen_shao_nv",
        name="天真少女",
        role="supporting",
        description="出身单纯、心怀善意，以温柔化解身边人的戾气，但需在经历中成长。",
        motivation="守护重要的人，保留本心",
        flaw="过度信任、不够果决",
        arc=[{"stage": "start", "change": "天真烂漫"}, {"stage": "mid", "change": "遭遇背叛"}, {"stage": "end", "change": "温柔而坚定"}],
        behavior="先相信再怀疑，乐于助人，情绪外露",
        dialogue_style="语气软、多感叹词，会认真询问对方感受",
        tags=["温柔", "成长型", "治愈"],
        applicable_genres=["玄幻", "仙侠", "都市", "言情", "传统"],
    ),
]

# 写作手法库：知识型（guidance 注入对应环节）+ 机制型（暗线：蓝图协议）
# 条目内容源自主流叙事理论（三幕结构/英雄之旅/契诃夫之枪/双线结构）
# 与网文社区公认技法（黄金三章/爽点密度），并保留各家"勿机械套用"的告诫。
TECHNIQUE_PRESETS: list[TechniqueEntry] = [
    TechniqueEntry(
        id="tech_dark_line",
        name="暗线设计（明暗双线）",
        category="结构",
        mode="mechanism",
        apply_stage="all",
        description=(
            "明线是读者可见的表层事件，暗线是隐含在字里行间、贯穿始终的隐藏线索"
            "（隐藏身份/秘密动机/逐步揭开的真相/主题暗流）。暗线让二刷有价值、"
            "让揭示时刻产生'原来如此'的冲击。挂载后系统会维护叙事蓝图"
            "（真相/表象/揭示计划）并在每章下达'暗示任务与揭示纪律'，检查正文是否提前点破。"
        ),
        guidance=(
            "为暗线埋点时：用看似无意义的细节、口误、反常举动或反复出现的小物件暗示真相；"
            "埋点要轻（1-2 处/章），不解释、不强调；不同章的暗示须与真相一致；"
            "接近揭示计划时逐步加强暗示密度；揭示时回收此前埋点，制造'原来如此'。"
        ),
        checklist=[
            "本章是否提前点破了任何暗线真相（违反揭示纪律）",
            "暗线暗示是否与真相一致（不能埋自相矛盾的线索）",
            "接近揭示计划的章节，暗示密度是否逐步加强",
        ],
        examples=[
            "好：'周远摩挲手环的动作在雨夜里停了一下，他没接话。'（暗示，不解释）",
            "坏：'其实这手环是他哥哥的遗物。'（人物直接说破真相）",
        ],
        tags=["结构", "双线", "悬念"],
        structure_schema=(
            "narrative_blueprint = {theme: 主题句, motifs: [象征意象], dark_threads: [{id, name, "
            "truth: 隐藏真相, surface: 读者可见表象, reveal_plan: 揭示计划, related: [关联人物]}]}"
        ),
    ),
    TechniqueEntry(
        id="tech_three_act",
        name="三幕结构",
        category="结构",
        mode="knowledge",
        apply_stage="planning",
        description=(
            "经典叙事骨架：第一幕建置（约25%，介绍人物与世界，以'激发事件'打破平衡）、"
            "第二幕对抗（约50%，冲突升级、中间点逆转）、第三幕解决（约25%，高潮与收尾）。"
        ),
        guidance=(
            "规划章节时确认本章处于哪一幕：第一幕重点是建立共情与抛出激发事件；"
            "第二幕中点安排一次不可逆转折，避免中段疲软；第三幕高潮须兑现此前铺垫。"
        ),
        checklist=["本章位置与幕结构职责是否匹配", "第二幕中段是否有不可逆的转折"],
        examples=[
            "例：第 8 章中点，主角发现最信任的搭档一直在录音（不可逆转折，第二幕转第三幕）。",
        ],
        tags=["结构", "经典"],
    ),
    TechniqueEntry(
        id="tech_hero_journey",
        name="英雄之旅",
        category="结构",
        mode="knowledge",
        apply_stage="planning",
        description=(
            "坎贝尔式成长弧：平凡世界→冒险召唤→拒绝→导师→跨越门槛→试炼→ "
            "深渊（最黑暗时刻）→奖赏→归途→复活→携万灵药归来。适合成长型主角。"
        ),
        guidance=(
            "成长型主角的章节规划可对照旅程阶段：重点是'最黑暗时刻'要安排在高潮之前，"
            "且主角的蜕变必须由试炼中的选择驱动，而非外部赐予。"
        ),
        checklist=["主角的成长是否由自己的选择推动", "最黑暗时刻是否安排在高潮之前"],
        examples=[
            "例：主角拒绝冒险召唤后目睹家人受害，被迫主动跨过门槛（拒绝→被迫启程）。",
        ],
        tags=["结构", "成长弧"],
    ),
    TechniqueEntry(
        id="tech_golden_open",
        name="黄金三章法则",
        category="网文",
        mode="knowledge",
        apply_stage="planning",
        description=(
            "网文开篇铁律：第一章立主角与世界、抛危机；第二章小冲突展示能力与金手指；"
            "第三章给出第一个爽点并留强钩子。注意：它是参考不是枷锁——不能为它丢掉立意。"
        ),
        guidance=(
            "前三章规划：信息要克制（只给当下需要的设定）；每章至少一个小冲突或悬念；"
            "第三章内兑现第一个'承诺的爽点'；开篇即抓人，不做长篇设定铺陈。"
        ),
        checklist=["前三章是否每章都有冲突或悬念", "首个爽点是否在第三章内兑现"],
        examples=[
            "好：开篇第一句'他醒来时，手里攥着一张不属于他的录取通知书'。",
            "坏：先用两章介绍大陆历史与势力划分，第三章主角才出场。",
        ],
        tags=["网文", "开篇"],
    ),
    TechniqueEntry(
        id="tech_chekhov_gun",
        name="契诃夫之枪（伏笔回收律）",
        category="结构",
        mode="knowledge",
        apply_stage="planning",
        description=(
            "'第一幕出现的枪，第三幕必须响'：凡是着重描写过的关键物件/承诺/能力，"
            "后文必须兑现；反之，后文的关键转折必须预先有线索。"
        ),
        guidance=(
            "规划时检查：本章着重强调过的物件、承诺、能力，是否已有回收计划；"
            "若安排了重要转折，确认此前至少埋过一处线索。未打算回收的细节不要浓墨重彩。"
        ),
        checklist=["本章是否有'被强调但从未回收'的元素", "重大转折前是否有预埋线索"],
        examples=[
            "好：第 3 章特写过的旧钥匙，第 28 章打开密室。",
            "坏：第 5 章浓墨描写一把匕首，此后再未出现。",
        ],
        tags=["结构", "伏笔"],
    ),
    TechniqueEntry(
        id="tech_show_dont_tell",
        name="展示而非讲述",
        category="文笔",
        mode="knowledge",
        apply_stage="writing",
        description=(
            "不直接陈述情绪与评价（'她很生气'），而是通过动作、微表情、对话与环境"
            "让读者自己得出结论，代入感更强。讲述只用于快速过场。"
        ),
        guidance=(
            "写作时：情绪用身体反应与动作外化（攥紧的拳头、移开的目光）；"
            "能力与身份用事件展示；'讲述'仅用于时间跳跃的过场段，占比尽量低。"
        ),
        checklist=["关键情绪段是否用动作/对话展示而非直陈", "是否存在成段的'设定讲述'"],
        examples=[
            "好：'她把成绩单折了又折，折到再也折不动。'",
            "坏：'她内心非常痛苦和焦虑。'",
        ],
        tags=["文笔"],
    ),
    TechniqueEntry(
        id="tech_emotion_curve",
        name="情绪曲线（张弛管理）",
        category="节奏",
        mode="knowledge",
        apply_stage="planning",
        description=(
            "读者的情绪张力需要起伏：高压段后必须有喘息，连续高潮会导致疲劳钝化。"
            "整卷应呈'爬升-高潮-回落-再爬升'的波浪形。"
        ),
        guidance=(
            "规划章与场景时标注张力等级（1-5），避免连续两章 5 级；高潮章之后安排一章"
            "缓冲（日常/温情/余波），缓冲章内埋下一个新钩子再爬升。"
        ),
        checklist=["本章与前后章的张力等级是否形成张弛", "高潮后是否有缓冲章消化后果"],
        examples=[
            "例：追逐（张力5）→ 雨夜疗伤（张力2）→ 发现关键线索（张力4）→ 高潮对峙（张力5）。",
        ],
        tags=["节奏"],
    ),
    TechniqueEntry(
        id="tech_pacing_shuangdian",
        name="爽点密度（网文节奏）",
        category="网文",
        mode="knowledge",
        apply_stage="writing",
        description=(
            "网文读者的耐心以千字计：约每 3000 字需要一个小满足（装到/赢了/收获/进展），"
            "长压抑必须兑现，否则弃书。爽点=目标可见的推进。"
        ),
        guidance=(
            "写作时按场景检查：每 1-2 个场景应有一次小推进或小兑现（能力显现/被打脸/获得认可）；"
            "压抑段控制在 3000 字内并给出'快了'的信号；爽点要有铺垫落差，不硬灌。"
        ),
        checklist=["每 3000 字内是否有一个可感知的推进或兑现", "长压抑段是否超长且无兑现信号"],
        examples=[
            "例：当众被嘲讽（压）→ 800 字内主角当众解出压轴题（兑现），不隔章。",
        ],
        tags=["网文", "节奏"],
    ),
    TechniqueEntry(
        id="tech_question_tree",
        name="悬念问题树（开-续-收）",
        category="悬念",
        mode="knowledge",
        apply_stage="planning",
        description=(
            "悬念=抛给读者的未解问题。长篇要维护一棵问题树：大问题挂全书，"
            "中问题挂卷，小问题挂章；旧问题收束时必须开新问题，读者永远有'想知道的事'。"
        ),
        guidance=(
            "规划本章时盘点：开了哪些问题、本章回答哪个（回收要给足信息量）、"
            "开哪个新问题（大小错落）。章末至少保留一个未解问题。"
        ),
        checklist=["本章回收的问题答案是否有足够信息量", "旧问题收束时是否开了新问题", "章末是否留有未解之问"],
        examples=[
            "例：章末'门把手，转动了。'（开小问）；第 3 章回答'是谁报的信'（收），同章开'信里为何没有署名'（新问）。",
        ],
        tags=["悬念", "结构"],
    ),

    TechniqueEntry(
        id="tech_dialogue_subtext",
        name="对话潜台词",
        category="对话",
        mode="knowledge",
        apply_stage="writing",
        description="对话的真正信息在言外之意：人物说的与想的相反、答非所问、用琐事掩饰情绪。潜台词是对话写出高级感的核心。",
        guidance="关键对话要让'说的'与'要的'错位：以退为进、答非所问、借琐事传情绪；避免人物把内心想法直接说出口；潜台词靠动作与停顿补全。",
        checklist=["关键对话是否有言外之意", "是否存在人物直接说出内心想法的台词"],
        examples=[
            "好：'吃了吗？''嗯。'——两人都在等对方先提分手，聊的全是天气。",
            "坏：'我舍不得你，我们别分手好不好？'（把潜台词全部说破）",
        ],
        tags=["对话", "文笔"],
    ),
    TechniqueEntry(
        id="tech_villain_logic",
        name="反派塑造·逻辑自洽",
        category="人物",
        mode="knowledge",
        apply_stage="planning",
        description="反派在自己的逻辑里是'对的'：有目标、有原则、有能力，作恶有自洽理由。为坏而坏的反派会拖垮全书可信度。",
        guidance="设计反派时先写他的'正当理由'（他认为自己为什么没错）；给反派至少一次'有原则'的表现；反派的手段应由目标推导，而非剧情需要。",
        checklist=["反派的行为能否由其目标与价值观自洽推导", "反派是否有至少一处'讲原则/有人味'的表现"],
        examples=[
            "好：反派销毁证据不是为灭口，而是证据会牵连他一直在保护的弟弟。",
            "坏：反派坦言'我就是坏，看他们不顺眼'。",
        ],
        tags=["人物", "反派"],
    ),
    TechniqueEntry(
        id="tech_upgrade_consistency",
        name="升级体系一致性",
        category="网文",
        mode="knowledge",
        apply_stage="all",
        description="力量/等级体系一经确立即成法律：能力边界、升级条件、越级代价必须前后一致。体系崩坏是长篇网文最大的逻辑灾难。",
        guidance="写作时对照已确立的规则：不得使用前文排除的能力；越级挑战必须有代价（重伤/道具/盟友）与解释；每次升级需有铺垫的资源或契机，不凭空突破。",
        checklist=["本章是否使用了与前文规则矛盾的能力", "越级挑战是否有代价与解释", "升级是否有铺垫的契机"],
        examples=[
            "坏：前文明确'聚气期无法飞行'，第 20 章主角为赶路直接飞了。",
            "好：主角借'风灵翼'（第 12 章铺垫过的道具）完成一次性短距滑翔，并付出吐血的代价。",
        ],
        tags=["网文", "设定"],
    ),
    TechniqueEntry(
        id="tech_sensory_writing",
        name="感官描写（五感入景）",
        category="文笔",
        mode="knowledge",
        apply_stage="writing",
        description="关键场景调动至少两种感官（听觉/嗅觉/触觉/味觉/视觉）建立临场感；感官细节要服务情绪，而不是堆砌。",
        guidance="每个重要场景选 1-2 个主导感官贯穿（雨夜的潮气、考场的笔尖声）；用感官变化标记情绪转折；避免只写'看到'。",
        checklist=["关键场景是否有两种以上感官细节", "感官描写是否与情绪呼应而非堆砌"],
        examples=[
            "好：'走廊的灯管嗡嗡作响，他数着自己第三十次看表。'（听觉+动作写紧张）",
            "坏：'考场里非常安静，大家都很紧张。'",
        ],
        tags=["文笔", "描写"],
    ),
    TechniqueEntry(
        id="tech_opening_hook",
        name="开局钩子（黄金三行）",
        category="网文",
        mode="knowledge",
        apply_stage="review",
        description=(
            "知乎体/短篇平台的生死线：读者决定是否读下去，只看开头三行。"
            "开局必须自带冲突、悬念或反常，禁止铺垫式开头（天气/自我介绍/背景说明）。"
            "挂载后审稿环节会专项检查每章开头是否抓人、结尾是否留钩。"
        ),
        guidance=(
            "开头三行内必须出现以下至少一项：反常事件、直接冲突、强悬念；"
            "第一人称需立刻建立代入感（具体处境+情绪反应）；"
            "禁止以天气、环境描写、自我介绍开场；"
            "每章结尾必须留下推进性钩子（反转/威胁/悬念），让读者必须点开下一章。"
        ),
        checklist=[
            "本章开头前三行是否有强钩子（冲突/悬念/反常至少其一）",
            "是否存在铺垫式开场（天气/环境/自我介绍/背景说明）",
            "本章结尾是否留下推进性钩子（让读者必须点开下一章）",
        ],
        examples=[
            "好：'裁员协议推过来的那一刻，我先看到的是组长新换的苹果手表。'（反常+冲突+情绪，三行内齐了）",
            "坏：'我叫陈默，是一名在启明科技工作了三年的算法工程师，今天天气很好。'（自我介绍+天气，零钩子）",
        ],
        tags=["网文", "知乎体", "钩子", "短篇"],
    ),
]

PRESETS: dict[str, list[object]] = {
    "personality": PERSONALITY_PRESETS,
    "tool": TOOL_PRESETS,
    "character_template": CHARACTER_TEMPLATE_PRESETS,
    "technique": TECHNIQUE_PRESETS,
    "meme": MEME_PRESETS,
    "style": STYLE_PRESETS,
}
