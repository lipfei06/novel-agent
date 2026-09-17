"""JSON 原子写：先写临时文件再 os.replace，避免并发写或进程崩溃产生半截 JSON。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, data: Any, indent: int = 2) -> None:
    """原子化写入 JSON 文件（Windows/POSIX 均安全）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path, default: Any = None) -> Any:
    """读取 JSON；文件不存在或损坏时返回 default（损坏时打印告警到 stderr）。"""
    import sys

    path = Path(path)
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[jsonio] 读取损坏的 JSON 文件 {path}: {exc}", file=sys.stderr, flush=True)
        return default
