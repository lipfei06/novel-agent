"""F04 NovelState：LangGraph 图状态。值为 JSON 可序列化（checkpoint 兼容）。"""
from __future__ import annotations

from typing import TypedDict


class NovelState(TypedDict, total=False):
    # 项目
    project_id: str
    project_root: str  # 磁盘根目录（解析记忆/落盘路径）
    genre: str
    title: str
    user_idea: str  # 用户初始立意
    current_stage: str  # stage0 ... done

    # 各环节产物（dict，节点内转 Pydantic 模型处理）
    concept: dict | None
    world_bible: dict | None
    characters: list[dict] | None
    outline: dict | None  # 含 version
    volume_plans: list[dict] | None
    writer_packets: dict | None  # {vol_ch: dict}
    chapters: dict | None  # {vol_ch: dict}

    # 章节游标
    current_volume: int
    current_chapter: int

    # 质量链路
    consistency_report: dict | None  # 最近一章的一致性报告
    auto_fix_attempts: int
    memory_notes: list[str]  # 记忆更新日志

    # 收尾链路
    editorial_report: dict | None  # 审校意见书
    final_paths: list[str]  # 导出产物路径

    # 卷/章管理
    pending_chapter: dict | None  # 待确认的生成章节（预览）
    character_state: dict | None  # 主要人物当前状态卡
    writer_proposals: dict | None  # 写手智能体的记忆更新提案（stage7 消费后清除）

    # 写作手法（自写作手法库挂载的条目快照）与叙事蓝图（机制型手法"暗线"的结构化数据）
    techniques: list[dict] | None  # [{id, name, mode, apply_stage, guidance, checklist, ...}]
    narrative_blueprint: dict | None  # {theme, motifs, dark_threads: [{id,name,truth,surface,reveal_plan,related}]}

    # 运行信息
    messages: list[str]
