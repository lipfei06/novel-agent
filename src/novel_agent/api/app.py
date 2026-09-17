"""F16 FastAPI 应用工厂。"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router
from .runtime import RuntimeStore

_ROOT_ENV = "NOVEL_AGENT_ROOT"


def create_app(root: str | Path | None = None, config_path: str | Path | None = None) -> FastAPI:
    """创建应用。root 缺省时读环境变量 NOVEL_AGENT_ROOT（便于 uvicorn factory 模式）。"""
    if root is None:
        root = os.environ.get(_ROOT_ENV, ".")
    app = FastAPI(title="novel-agent", version="0.1.0")
    # 只放行本机前端开发地址；如需其它来源，设置 NOVEL_AGENT_CORS_ORIGINS（逗号分隔）
    import os as _os

    origins = [o.strip() for o in _os.environ.get("NOVEL_AGENT_CORS_ORIGINS", "").split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    root = Path(root)
    app.state.root = root
    app.state.runtime = RuntimeStore(root, Path(config_path) if config_path else None)
    from .tasks import TaskManager

    app.state.tasks = TaskManager()
    app.include_router(router)
    return app
