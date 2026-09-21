"""F01 配置：加载 config.yaml 与题材 Profile，合并为单一运行时配置。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


class ConfigError(Exception):
    """配置缺失或非法，fail-fast。"""


@dataclass(frozen=True)
class ModelTier:
    """分级模型档位：OpenAI 兼容接口，key 走环境变量。"""

    tier: str
    model: str
    base_url: str = ""
    api_key_env: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096

    @property
    def api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env) or os.environ.get("OPENAI_API_KEY")


@dataclass(frozen=True)
class GenreProfile:
    """题材 Profile：决定篇幅、世界观必含项与红线。"""

    id: str
    name: str
    target_word_count: int = 100000
    default_volumes: int = 1
    chapters_per_volume: int = 20
    words_per_chapter: int = 2000
    world_requirements: list[str] = field(default_factory=list)
    red_lines: list[str] = field(default_factory=list)
    style_preset: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Config:
    genre: GenreProfile
    tiers: dict[str, ModelTier] = field(default_factory=dict)
    memory: dict = field(default_factory=dict)
    rag: dict = field(default_factory=dict)
    token_budget: dict[str, int] = field(default_factory=dict)
    library: dict = field(default_factory=dict)
    export: dict = field(default_factory=dict)
    projects: dict = field(default_factory=dict)
    consistency: dict = field(default_factory=dict)
    cost: dict = field(default_factory=dict)
    writer: dict = field(default_factory=dict)
    model_overrides: dict = field(default_factory=dict)  # 任务级模型覆写：{任务名: 档位名}

    def tier(self, name: str) -> ModelTier:
        if name not in self.tiers:
            raise ConfigError(f"未配置 LLM 档位: {name}")
        return self.tiers[name]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件格式错误（应为映射）: {path}")
    return data


def load_genre_profile(genre: str, profiles_dir: Path = PROFILES_DIR) -> GenreProfile:
    raw = _load_yaml(profiles_dir / f"{genre}.yaml")
    try:
        return GenreProfile(
            id=str(raw.get("id", genre)),
            name=str(raw.get("name", genre)),
            target_word_count=int(raw.get("target_word_count", 100000)),
            default_volumes=int(raw.get("default_volumes", 1)),
            chapters_per_volume=int(raw.get("chapters_per_volume", 20)),
            words_per_chapter=int(raw.get("words_per_chapter", 2000)),
            world_requirements=list(raw.get("world_requirements", [])),
            red_lines=list(raw.get("red_lines", [])),
            style_preset=dict(raw.get("style_preset", {})),
        )
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"题材 Profile 字段非法: {genre}") from exc


def load_config(path: str | Path = "config.yaml", genre: str | None = None) -> Config:
    """加载全局 config.yaml（可选覆盖题材）+ 题材 Profile。

    若项目根目录存在 .env，则自动加载其中的环境变量（如 DEEPSEEK_API_KEY）。
    """
    from dotenv import load_dotenv

    load_dotenv()

    cfg_path = Path(path)
    raw = _load_yaml(cfg_path)

    genre_id = genre or str(raw.get("genre", "webnovel"))
    profile = load_genre_profile(genre_id)

    tiers: dict[str, ModelTier] = {}
    for name, t in (raw.get("llm") or {}).items():
        if not isinstance(t, dict):
            raise ConfigError(f"llm.{name} 应为映射")
        tiers[name] = ModelTier(
            tier=name,
            model=str(t.get("model", "")),
            base_url=str(t.get("base_url", "")),
            api_key_env=str(t.get("api_key_env", "")),
            temperature=float(t.get("temperature", 0.7)),
            max_tokens=int(t.get("max_tokens", 4096)),
        )
        if not tiers[name].model:
            raise ConfigError(f"llm.{name} 缺少 model 字段")

    token_budget = {k: int(v) for k, v in (raw.get("token_budget") or {}).items()}

    return Config(
        genre=profile,
        tiers=tiers,
        memory=dict(raw.get("memory", {})),
        rag=dict(raw.get("rag", {})),
        token_budget=token_budget,
        library=dict(raw.get("library", {})),
        export=dict(raw.get("export", {})),
        projects=dict(raw.get("projects", {})),
        consistency=dict(raw.get("consistency", {})),
        cost=dict(raw.get("cost", {})),
        writer=dict(raw.get("writer", {})),
        model_overrides=dict(raw.get("model_overrides", {})),
    )


def list_profiles(profiles_dir: Path = PROFILES_DIR) -> list[str]:
    return sorted(p.stem for p in profiles_dir.glob("*.yaml"))
