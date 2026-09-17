"""统一日志：各模块用 logging 替代 print，便于生产环境收集与过滤。"""
from __future__ import annotations

import logging

_LOGGER_NAME = "novel_agent"


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO) -> None:
    """服务入口调用一次；未配置 handlers 时输出到 stderr。"""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
