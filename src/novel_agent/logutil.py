"""统一日志：各模块用 logging 替代 print，便于生产环境收集与过滤。"""
from __future__ import annotations

import logging

_LOGGER_NAME = "novel_agent"


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO, log_file: str | None = None) -> None:
    """服务入口调用一次；stderr 之外可选落盘（logs/novel-agent.log，轮转 5MB×3），
    使 LLM 瞬时故障等错误的真实根因可回溯（独立控制台窗口关掉后日志仍在）。"""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        if log_file:
            from logging.handlers import RotatingFileHandler
            from pathlib import Path

            f = Path(log_file)
            f.parent.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(f, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
    logger.setLevel(level)
