"""agents：各阶段 Agent（LLM 生成 + mock 模式）。"""
from __future__ import annotations

import os


def is_mock() -> bool:
    """mock 模式：NOVEL_ENGINE_MOCK=1 时返回确定性结果，无需 API key。"""
    return os.environ.get("NOVEL_ENGINE_MOCK") == "1"
