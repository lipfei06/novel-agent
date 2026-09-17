"""revision：定点修改引擎（F10）。"""
from .context import build_edit_context
from .diff import render_diff
from .edit import edit_scene
from .selector import locate_paragraph, locate_scene

__all__ = ["build_edit_context", "render_diff", "edit_scene", "locate_paragraph", "locate_scene"]
