"""定点修改引擎：diff 展示。"""
from __future__ import annotations

import difflib


def render_diff(old: str, new: str) -> str:
    """统一 diff 展示（unified format）。"""
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="修改前",
            tofile="修改后",
        )
    )
