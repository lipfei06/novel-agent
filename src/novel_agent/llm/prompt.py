"""F02 prompt 守卫：token 估算与环节预算强制校验（禁止把整本小说塞进 prompt）。"""
from __future__ import annotations


class TokenBudgetExceeded(Exception):
    """环节 prompt 估算 token 超限。"""

    def __init__(self, stage: str, total: int, limit: int) -> None:
        super().__init__(f"{stage} 预算超限: 估算 {total} > 上限 {limit}")
        self.stage = stage
        self.total = total
        self.limit = limit


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数。中文约 1 字≈1 token 偏保守，取字符数（去空白）。

    用途为预算保护而非精确计费；精确计费依赖 provider 返回 usage。
    """
    return max(1, len(str(text or "").replace(" ", "")))


def guard_tokens(stage: str, parts: dict[str, str], budget: dict[str, int]) -> int:
    """汇总 parts 的估算 token，超过 budget[stage] 抛 TokenBudgetExceeded。

    返回估算总数，供调用方记录。
    """
    total = sum(estimate_tokens(v) for v in parts.values())
    limit = budget.get(stage, 0)
    if limit and total > limit:
        raise TokenBudgetExceeded(stage, total, limit)
    return total


def build_messages(system: str, user: str, stage: str, budget: dict[str, int], style: str = "", skill: str = "") -> list[dict[str, str]]:
    """装配 system/user 消息并过预算守卫。

    system 之后的注入顺序（冲突时越靠后越具体、越优先）：skill 手艺指导 → 题材风格指令。
    skill 计入预算守卫（约 300-600 token），style 沿用旧行为不计。
    """
    guard_tokens(stage, {"system": f"{system}\n\n{skill}" if skill else system, "user": user}, budget)
    if skill:
        system = f"{system}\n\n{skill}"
    if style:
        system = f"{system}\n\n{style}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


_STYLE_LABELS = {
    "pace": "节奏",
    "dialogue_ratio": "对话占比（0-1）",
    "show_vs_tell": "展示与讲述比（0-1，越大越多展示）",
    "hook_frequency": "钩子频率",
    "tone": "基调",
    "pov": "叙事视角",
    "sensitivity": "尺度",
}


def style_directive(cfg) -> str:
    """把题材 Profile 的 style_preset 渲染为可注入写作类 prompt 的风格指令。

    使 webnovel / literary / short_story 三种题材真正产生差异化的写作要求。
    """
    preset = getattr(getattr(cfg, "genre", None), "style_preset", None) or {}
    if not preset:
        return ""
    parts = [f"{_STYLE_LABELS.get(k, k)}：{v}" for k, v in preset.items()]
    return "写作风格要求（来自题材设定，务必遵循）：" + "；".join(parts) + "。"
