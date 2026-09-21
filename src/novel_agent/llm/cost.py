"""真实成本统计：采集每次 LLM 调用的 usage，按项目累积到 cost.json。"""
from __future__ import annotations

import json
import threading
from pathlib import Path

_tls = threading.local()

# 缺省估价（USD / 1M tokens）；可在 config.yaml cost 段按模型覆盖
_DEFAULT_PRICE = (0.14, 0.28)


def set_project(project_id: str, root: str | Path | None = None) -> None:
    """在请求线程内标记当前项目（API 调用生成前设置）。"""
    _tls.project_id = project_id
    if root is not None:
        _tls.root = Path(root)


def _cost_path(root: Path, project_id: str) -> Path:
    from novel_agent.storage import ProjectPaths

    return ProjectPaths(root, project_id).data_dir / "cost.json"


def _price_for(cfg_cost: dict | None, model: str | None) -> tuple[float, float]:
    """查模型单价 (输入, 输出)；未命中模型名用 default_price。"""
    cost_cfg = cfg_cost or {}
    prices = cost_cfg.get("prices") or {}
    if model and model in prices and len(prices[model]) >= 2:
        p = prices[model]
        return (float(p[0]), float(p[1]))
    dp = cost_cfg.get("default_price") or _DEFAULT_PRICE
    try:
        return (float(dp[0]), float(dp[1]))
    except (TypeError, ValueError):
        return _DEFAULT_PRICE


def extract_usage(response) -> dict | None:
    """从 LangChain AI 响应中提取 usage（兼容多种键位）。

    ChatOpenAI 的 response_metadata 键是 token_usage；部分后端是 usage；
    新标准在 AIMessage.usage_metadata（input_tokens 等键名）。取不到返回 None。
    """
    meta = getattr(response, "response_metadata", {}) or {}
    u = meta.get("usage") or meta.get("token_usage")
    if u:
        return u
    um = getattr(response, "usage_metadata", None)
    if um:
        return {
            "prompt_tokens": um.get("input_tokens"),
            "completion_tokens": um.get("output_tokens"),
            "total_tokens": um.get("total_tokens"),
        }
    return None


def record_usage(usage: dict | None, model: str | None = None) -> None:
    """记录一次 LLM 调用的 token usage 到当前项目的 cost.json（按模型分桶）。"""
    if not usage:
        return
    project_id = getattr(_tls, "project_id", None)
    root = getattr(_tls, "root", None)
    if not project_id or root is None:
        return
    path = _cost_path(root, project_id)
    from novel_agent.storage import write_json_atomic

    data = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    data["prompt_tokens"] = int(data.get("prompt_tokens", 0)) + int(usage.get("prompt_tokens") or 0)
    data["completion_tokens"] = int(data.get("completion_tokens", 0)) + int(usage.get("completion_tokens") or 0)
    data["total_tokens"] = int(data.get("total_tokens", 0)) + int(usage.get("total_tokens") or 0)
    data["calls"] = int(data.get("calls", 0)) + 1
    if model:
        models = dict(data.get("models") or {})
        bucket = dict(models.get(model) or {})
        bucket["prompt_tokens"] = int(bucket.get("prompt_tokens", 0)) + int(usage.get("prompt_tokens") or 0)
        bucket["completion_tokens"] = int(bucket.get("completion_tokens", 0)) + int(usage.get("completion_tokens") or 0)
        bucket["calls"] = int(bucket.get("calls", 0)) + 1
        models[model] = bucket
        data["models"] = models
    write_json_atomic(path, data)


def get_cost(root: Path, project_id: str, cfg_cost: dict | None = None) -> dict:
    path = _cost_path(root, project_id)
    data = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    prompt = int(data.get("prompt_tokens", 0))
    completion = int(data.get("completion_tokens", 0))
    # 有按模型分桶时逐模型计价；否则整体用缺省价
    est = 0.0
    models = data.get("models") or {}
    if models:
        for name, bucket in models.items():
            p_in, p_out = _price_for(cfg_cost, name)
            est += (int(bucket.get("prompt_tokens", 0)) / 1_000_000) * p_in
            est += (int(bucket.get("completion_tokens", 0)) / 1_000_000) * p_out
    else:
        p_in, p_out = _price_for(cfg_cost, None)
        est = (prompt / 1_000_000) * p_in + (completion / 1_000_000) * p_out
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": int(data.get("total_tokens", 0)),
        "calls": int(data.get("calls", 0)),
        "est_cost_usd": round(est, 4),
    }
