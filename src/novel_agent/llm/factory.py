"""F02 LLM 工厂：按档位返回 LangChain chat model（OpenAI 兼容接口）。"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI

from novel_agent.config import Config, ModelTier

_PLACEHOLDER_KEY = "not-set"


def get_chat_model(tier: str, cfg: Config, task: str | None = None) -> ChatOpenAI:
    """按档位返回 ChatOpenAI。task 给定时，可被 cfg.model_overrides[task] 覆写档位
    （任务级模型路由：如 summary→local，切换只需改配置）。"""
    overrides = getattr(cfg, "model_overrides", None) or {}
    if task and task in overrides:
        overridden = str(overrides[task])
        if overridden in cfg.tiers:
            tier = overridden
    t: ModelTier = cfg.tier(tier)
    return ChatOpenAI(
        model=t.model,
        api_key=t.api_key or _PLACEHOLDER_KEY,
        base_url=t.base_url or None,
        temperature=t.temperature,
        max_tokens=t.max_tokens,
    )


def get_model_name(tier: str, cfg: Config) -> str:
    """返回档位对应的模型名（便于日志/成本面板展示）。"""
    return cfg.tier(tier).model


def get_embedder(cfg: Config):
    """按 memory.vector.embedding 配置返回 embed 函数（text -> list[float]）。

    OpenAI 兼容 /embeddings 接口；未配置 model 时返回 None（回退本地 bigram 检索）。
    """
    import httpx

    emb = ((cfg.memory.get("vector") or {}).get("embedding") or {}) if cfg.memory else {}
    model = str(emb.get("model", "") or "")
    if not model:
        return None
    base_url = str(emb.get("base_url", "") or "").rstrip("/")
    api_key = os.environ.get(str(emb.get("api_key_env", "") or ""), "") or os.environ.get("OPENAI_API_KEY", "")
    dim = emb.get("dim")

    def embed(text: str) -> list[float]:
        resp = httpx.post(
            f"{base_url}/embeddings",
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            json={"model": model, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        vec = resp.json()["data"][0]["embedding"]
        return [float(x) for x in vec[:dim]] if dim else [float(x) for x in vec]

    return embed


def _schema_instructions(schema) -> str:
    """把 Pydantic schema 转成显式 JSON Schema 说明，注入提示词，提升模型遵循度。"""
    try:
        import json

        return (
            "输出必须严格符合以下 JSON Schema（字段名与类型必须一致；可省略缺省字段）：\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=None)
        )
    except Exception:
        return ""


def _extract_json(text) -> object:
    """从模型输出文本中稳健提取 JSON（容忍代码围栏/前后杂质/裸 JSON 值）。"""
    import json
    import re

    if isinstance(text, (dict, list)):
        return text
    s = str(text or "").strip()
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S).strip()  # 推理类模型（deepseek-r1 等）先剥离思考段
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s).strip()
    # 整体就是合法 JSON（含裸字符串/数字/布尔/对象/数组）→ 直接解析
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 否则找到第一个 { 或 [ 作为 JSON 起点
    starts = [i for i, ch in enumerate(s) if ch in "{["]
    for start_idx in starts:
        start = s[start_idx]
        depth = 0
        for i in range(start_idx, len(s)):
            ch = s[i]
            if ch == start:
                depth += 1
            elif ch == ("}" if start == "{" else "]"):
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start_idx : i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("未能从模型输出中提取 JSON")


def _coerce_field(annotation, value, _missing=object()):
    """宽松修复常见结构偏差：list[dict]←list[str]、str←dict 等。"""
    import json
    from typing import get_args, get_origin

    if value is _missing or value is None:
        return value
    origin = get_origin(annotation)
    if origin is list:
        from pydantic import BaseModel

        item = get_args(annotation)[0] if get_args(annotation) else object
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            if value and all(not isinstance(v, dict) for v in value):
                if isinstance(item, type) and issubclass(item, BaseModel):
                    first = next(iter(item.model_fields))
                    return [{first: v} for v in value]
                if item is dict:
                    return [{"desc": v} for v in value]
            return value
        return [value]
    if annotation is str and isinstance(value, dict):
        for k in ("summary", "text", "content", "title"):
            if isinstance(value.get(k), str):
                return value[k]
        strs = [v for v in value.values() if isinstance(v, str)]
        return strs[0] if strs else json.dumps(value, ensure_ascii=False)
    return value


def _validate_or_coerce(schema, data):
    """先严格校验；失败则按字段类型宽松修复后再校验。"""
    from pydantic import BaseModel, ValidationError

    try:
        return schema.model_validate(data)
    except ValidationError:
        if not isinstance(data, dict) or not (isinstance(schema, type) and issubclass(schema, BaseModel)):
            return None
        coerced = {}
        for name, field in schema.model_fields.items():
            if name not in data:
                continue  # 缺省字段不强制注入，交给模型默认值
            coerced[name] = _coerce_field(field.annotation, data[name])
        try:
            return schema.model_validate(coerced)
        except ValidationError:
            return None


def _json_mode_unsupported(exc: Exception) -> bool:
    """识别"服务端不支持 response_format=json_object"类错误（常见于本地模型服务）。"""
    text = f"{exc}".lower()
    return (
        "response_format" in text
        or "json_object" in text
        or "json mode" in text
        or "not supported" in text
    )


_TRANSIENT_KEYWORDS = (
    "timeout", "timed out", "connection", "connect", "reset by peer", "eof",
    "rate limit", "429", "500", "502", "503", "504", "unavailable",
    "bad gateway", "overloaded", "internal server error", "remote end",
)


def _is_transient(exc: Exception) -> bool:
    """识别网络/服务端瞬时故障（值得更长退避后再试），与格式错误区分。"""
    name = type(exc).__name__.lower()
    if any(k in name for k in ("timeout", "connection", "connect", "network", "protocol")):
        return True
    text = f"{exc}".lower()
    return any(k in text for k in _TRANSIENT_KEYWORDS)


def invoke_structured(llm, messages: list[dict], schema=None, retries: int = 3):
    """安全调用结构化输出：注入 json 提示与 schema 说明；解析失败自动宽松修复并重试。

    DeepSeek 等 OpenAI 兼容服务：要求 prompt 含 "json" 字样；对嵌套结构遵循度一般，
    因此采用"提取 JSON → 严格校验 → 宽松修复 → 重试"的策略，尽量不中断创作。
    重试退避按错误类型区分：网络/服务端瞬时故障（超时/断连/5xx/限流）用长退避
    （2s/8s/20s，扛过几十秒的服务抖动），格式错误维持短退避（1s/2s/4s）快速换思路。
    不修改调用方传入的 messages（注入只发生在内部拷贝上）。
    """
    import time

    hint = _schema_instructions(schema) if schema is not None else ""
    msgs = [dict(m) for m in messages]
    for m in msgs:
        if m.get("role") == "system":
            if "json" not in m.get("content", "").lower():
                m["content"] = f"{m['content']}\n请以 JSON 格式输出结果。"
            if hint:
                m["content"] = f"{m['content']}\n\n{hint}"
            break
    else:
        system = f"请以 JSON 格式输出结果。{('\n\n' + hint) if hint else ''}"
        msgs.insert(0, {"role": "system", "content": system})

    bound = llm.bind(response_format={"type": "json_object"})
    json_mode = True  # 本地/兼容服务不支持 json_object 时自动降级为纯提示词约束（不消耗重试次数）
    last_err: Exception | None = None
    attempt = 0
    while attempt <= retries:
        if attempt:
            waits = (8, 20, 30) if _is_transient(last_err) else (1, 2, 4)
            time.sleep(waits[min(attempt, len(waits)) - 1])
        try:
            response = bound.invoke(msgs)
        except Exception as exc:  # noqa: BLE001
            if json_mode and _json_mode_unsupported(exc):
                json_mode = False
                bound = llm
                continue
            last_err = exc
            attempt += 1
            continue
        try:
            from .cost import extract_usage, record_usage

            model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "")
            record_usage(extract_usage(response), model=str(model_name) if model_name else None)
            data = _extract_json(response.content)
            parsed = _validate_or_coerce(schema, data)
            if parsed is not None:
                return parsed
            last_err = ValueError("模型输出的内容不是规定的结构（可能只给了一段文字）")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        attempt += 1
    raise LLMStructuredError(
        f"AI 偶发未按格式输出（已自动重试 {retries + 1} 次仍失败）。"
        f"这不是系统故障，重新点击「接受」即可继续。{last_err}"
    )


class LLMStructuredError(RuntimeError):
    """结构化输出失败。"""
