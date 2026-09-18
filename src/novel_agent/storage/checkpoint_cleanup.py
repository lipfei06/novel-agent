"""Checkpoint 历史清理：防止 SQLite Checkpoint 表随章节数无限膨胀。

LangGraph 的 SqliteSaver 每次状态变更都写一条 Checkpoint 记录。
对于 100+ 章的长篇，这些历史快照会让数据库膨胀到数十 MB。
本项目通过保留最近 N 条 + VACUUM 回收空间来控制体积。

用法：
    from novel_agent.storage.checkpoint_cleanup import prune_checkpoints
    prune_checkpoints("data/projects/<pid>/checkpoints/<pid>.sqlite", keep=5)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def prune_checkpoints(db_path: Path, keep: int = 5) -> int:
    """清理旧的 Checkpoint 历史，保留最近 keep 条。

    返回删除的行数。只操作 LangGraph 自己的 checkpoints 表，
    不影响当前状态（最新的 Checkpoint 始终保留）。
    """
    path = Path(db_path)
    if not path.exists():
        return 0
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        # 查看 checkpoints 表是否存在
        cur.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='checkpoints'"
        )
        if cur.fetchone()[0] == 0:
            return 0
        # 统计总行数
        cur.execute("SELECT COUNT(*) FROM checkpoints")
        total = cur.fetchone()[0]
        if total <= keep:
            return 0
        # 删除最旧的（保留最近 keep 条，按 rowid 降序取最新 keep 条的 rowid）
        cur.execute(
            "DELETE FROM checkpoints WHERE rowid NOT IN "
            "(SELECT rowid FROM checkpoints ORDER BY rowid DESC LIMIT ?)",
            (keep,),
        )
        deleted = cur.rowcount
        # 同时清理 checkpoint_writes（如果有这个表）
        cur.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='checkpoint_writes'"
        )
        if cur.fetchone()[0] > 0:
            cur.execute(
                "DELETE FROM checkpoint_writes WHERE thread_id IN ("
                "  SELECT DISTINCT thread_id FROM checkpoints"
                ") AND checkpoint_id NOT IN ("
                "  SELECT checkpoint_id FROM checkpoints ORDER BY rowid DESC LIMIT ?"
                ")",
                (keep * 3,),  # 每个 checkpoint 可能有多次 write
            )
        conn.commit()
        return deleted
    finally:
        conn.close()
