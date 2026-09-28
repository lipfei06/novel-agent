"""写作基础库：性格库 + 小说工具库 + 人物模板库 + 写作手法库 + 梗库（F17）。"""
from .index import LibraryIndex
from .memes import MemeEntry, MEME_PRESETS, populate_memes
from .personality import PersonalityEntry
from .presets import PERSONALITY_PRESETS, PRESETS, TECHNIQUE_PRESETS, TOOL_PRESETS
from .searcher import (
    default_store,
    meme_candidates_text,
    memes_for_chapter,
    pick_for_chapter,
    pick_for_character,
    search_personality,
    search_tool,
)
from .store import Kind, LibraryStore
from .techniques import TechniqueEntry
from .tools import NovelToolEntry
from novel_agent.types.character_template import CharacterTemplate

__all__ = [
    "Kind",
    "LibraryStore",
    "LibraryIndex",
    "PersonalityEntry",
    "NovelToolEntry",
    "TechniqueEntry",
    "MemeEntry",
    "CharacterTemplate",
    "PERSONALITY_PRESETS",
    "TOOL_PRESETS",
    "TECHNIQUE_PRESETS",
    "MEME_PRESETS",
    "PRESETS",
    "default_store",
    "pick_for_character",
    "pick_for_chapter",
    "search_personality",
    "search_tool",
    "memes_for_chapter",
    "meme_candidates_text",
    "populate_memes",
]
