"""Token counts and charges for the OpenAI calls made while answering one question.

Each chat and embedding response already includes a usage object. This module
records those counts, then prices them from the platform costs API
(GET /v1/organization/costs). That endpoint needs a key with the
api.usage.read scope. A normal project key can still read the daily usage
roll-up at GET /v1/usage, so the charge falls back to OpenAI's published
per-token price when the costs API refuses the key.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextvars import ContextVar

# USD per token. Published list: https://developers.openai.com/api/docs/pricing
# Checked 2026-10-06. Used only when the costs API does not return a rate.
_PUBLISHED = {
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "cached": 0.075 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "cached": 1.25 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4.1-mini": {"input": 0.40 / 1_000_000, "cached": 0.10 / 1_000_000, "output": 1.60 / 1_000_000},
    "gpt-4.1": {"input": 2.00 / 1_000_000, "cached": 0.50 / 1_000_000, "output": 8.00 / 1_000_000},
    "text-embedding-3-small": {"input": 0.02 / 1_000_000, "cached": 0.02 / 1_000_000, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13 / 1_000_000, "cached": 0.13 / 1_000_000, "output": 0.0},
    "text-embedding-ada-002": {"input": 0.10 / 1_000_000, "cached": 0.10 / 1_000_000, "output": 0.0},
}

_sessions: dict[str, list] = {}
_lock = threading.Lock()
_current: ContextVar[str | None] = ContextVar("kb_openai_usage", default=None)
_installed = False
_rate_cache: dict = {"at": 0.0, "rates": {}, "status": "unchecked"}
_usage_cache: dict = {"at": 0.0, "date": "", "rows": [], "status": "unchecked"}


def install() -> None:
    """Wrap the OpenAI SDK so every chat and embedding call can be counted."""
    global _installed
    if _installed:
        return
    from openai.resources.chat.completions.completions import AsyncCompletions, Completions
    from openai.resources.embeddings import AsyncEmbeddings, Embeddings

    _wrap(Completions, "create", "chat", False)
    _wrap(Completions, "parse", "chat", False)
    _wrap(AsyncCompletions, "create", "chat", True)
    _wrap(AsyncCompletions, "parse", "chat", True)
    _wrap(Embeddings, "create", "embedding", False)
    _wrap(AsyncEmbeddings, "create", "embedding", True)
    _installed = True


def begin() -> None:
    install()
    session = uuid.uuid4().hex
    with _lock:
        _sessions[session] = []
    _current.set(session)


def finish() -> dict:
    session = _current.get()
    _current.set(None)
    with _lock:
        calls = _sessions.pop(session, None) if session else None
    return summarize(calls or [])


def summarize(calls: list[dict]) -> dict:
    if not calls:
        return {
            "calls": [],
            "inputTokens": 0,
            "cachedTokens": 0,
            "outputTokens": 0,
            "chargeUsd": 0,
            "currency": "usd",
            "source": "none",
            "note": "No OpenAI calls were made for this question.",
        }
    rates, costs_status = _platform_rates()
    priced = []
    sources = set()
    unknown = []
    for call in calls:
        charge, source = _charge(call, rates)
        if source == "unknown":
            unknown.append(call["model"])
        else:
            sources.add(source)
        priced.append({**call, "chargeUsd": charge, "rateSource": source})
    if costs_status == "ok" and sources == {"platform.costs"}:
        source = "platform.costs"
    elif "platform.costs" in sources:
        source = "mixed"
    elif sources:
        source = "published"
    else:
        source = "unknown"
    usage_date, usage_rows, usage_status = _platform_usage()
    return {
        "calls": priced,
        "inputTokens": sum(call["inputTokens"] for call in priced),
        "cachedTokens": sum(call["cachedTokens"] for call in priced),
        "outputTokens": sum(call["outputTokens"] for call in priced),
        "chargeUsd": round(sum(call["chargeUsd"] or 0 for call in priced), 10),
        "currency": "usd",
        "source": source,
        "platform": {
            "costs": costs_status,
            "usageDate": usage_date,
            "usage": usage_rows,
            "usageStatus": usage_status,
        },
        "note": _note(source, costs_status, unknown, usage_date, usage_rows, usage_status),
    }


def _wrap(cls, name: str, kind: str, is_async: bool) -> None:
    original = getattr(cls, name)

    if is_async:
        async def wrapped(self, *args, **kwargs):
            response = await original(self, *args, **kwargs)
            _record(kind, kwargs.get("model"), response)
            return response
    else:
        def wrapped(self, *args, **kwargs):
            response = original(self, *args, **kwargs)
            _record(kind, kwargs.get("model"), response)
            return response

    setattr(cls, name, wrapped)


def _record(kind: str, requested_model, response) -> None:
    session = _current.get()
    with _lock:
        if session in _sessions:
            bucket = _sessions[session]
        elif len(_sessions) == 1:
            bucket = next(iter(_sessions.values()))
        else:
            return
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")
    if not usage:
        return
    prompt = int(_field(usage, "prompt_tokens", 0) or _field(usage, "input_tokens", 0) or 0)
    completion = int(_field(usage, "completion_tokens", 0) or _field(usage, "output_tokens", 0) or 0)
    details = _field(usage, "prompt_tokens_details", None)
    cached = int(_field(details, "cached_tokens", 0) or 0) if details else 0
    model = str(getattr(response, "model", None) or requested_model or "unknown")
    bucket.append({
        "kind": kind,
        "model": model,
        "inputTokens": prompt,
        "cachedTokens": min(cached, prompt),
        "outputTokens": completion,
    })


def _field(obj, name: str, default=0):
    if obj is None:
        return default
    if isinstance(obj, dict):
        value = obj.get(name, default)
    else:
        value = getattr(obj, name, default)
    return default if value is None else value


def _charge(call: dict, rates: dict) -> tuple[float | None, str]:
    model = call["model"]
    fresh = max(0, call["inputTokens"] - call["cachedTokens"])
    cached = call["cachedTokens"]
    output = call["outputTokens"]
    platform = (
        _lookup(rates, model, "input"),
        _lookup(rates, model, "cached"),
        _lookup(rates, model, "output"),
    )
    published = _lookup_published(model)
    if any(rate is not None for rate in platform):
        input_rate = platform[0] if platform[0] is not None else (published or {}).get("input", 0)
        cached_rate = platform[1] if platform[1] is not None else (published or {}).get("cached", input_rate)
        output_rate = platform[2] if platform[2] is not None else (published or {}).get("output", 0)
        return round(fresh * input_rate + cached * cached_rate + output * output_rate, 10), "platform.costs"
    if published:
        return round(
            fresh * published["input"] + cached * published["cached"] + output * published["output"],
            10,
        ), "published"
    return None, "unknown"


def _lookup(table: dict, model: str, kind: str):
    name = (model or "").lower()
    best = None
    for (key, rate_kind), per in table.items():
        if rate_kind != kind:
            continue
        label = key.lower()
        if name == label or name.startswith(label + "-"):
            if best is None or len(label) > len(best[0]):
                best = (label, per)
    return None if best is None else best[1]


def _lookup_published(model: str):
    name = (model or "").lower()
    best = None
    for key, rate in _PUBLISHED.items():
        if name == key or name.startswith(key + "-"):
            if best is None or len(key) > len(best[0]):
                best = (key, rate)
    return None if best is None else best[1]


def _platform_rates() -> tuple[dict, str]:
    if time.time() - _rate_cache["at"] < 600:
        return _rate_cache["rates"], _rate_cache["status"]
    rates: dict = {}
    status = "unavailable"
    start = int(time.time()) - 7 * 86400
    query = urllib.parse.urlencode([
        ("start_time", start),
        ("bucket_width", "1d"),
        ("limit", "7"),
        ("group_by", "line_item"),
    ])
    try:
        body = _get_json("/v1/organization/costs?" + query)
        status = "ok"
        for bucket in body.get("data") or []:
            for row in bucket.get("results") or []:
                model, kind = _split_line(str(row.get("line_item") or ""))
                amount = (row.get("amount") or {}).get("value")
                per = _per_token(amount, row.get("quantity"), row.get("quantity_unit"))
                if model and kind and per is not None:
                    rates[(model, kind)] = per
        if not rates:
            status = "empty"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        status = "missing_scope" if exc.code == 403 and "api.usage.read" in detail else f"http_{exc.code}"
    except Exception:
        status = "unavailable"
    _rate_cache.update(at=time.time(), rates=rates, status=status)
    return rates, status


def _platform_usage() -> tuple[str, list, str]:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    if _usage_cache["date"] == day and time.time() - _usage_cache["at"] < 30:
        return day, _usage_cache["rows"], _usage_cache["status"]
    rows: list = []
    status = "unavailable"
    try:
        body = _get_json("/v1/usage?date=" + day)
        status = "ok"
        for row in body.get("data") or []:
            if not isinstance(row, dict):
                continue
            rows.append({
                "model": row.get("snapshot_id") or row.get("model") or "",
                "operation": row.get("operation") or "",
                "requests": int(row.get("n_requests") or 0),
                "inputTokens": int(row.get("n_context_tokens_total") or row.get("n_context_tokens") or 0),
                "outputTokens": int(row.get("n_generated_tokens_total") or row.get("n_generated_tokens") or 0),
            })
    except urllib.error.HTTPError as exc:
        status = f"http_{exc.code}"
    except Exception:
        status = "unavailable"
    _usage_cache.update(at=time.time(), date=day, rows=rows, status=status)
    return day, rows, status


def _get_json(path: str) -> dict:
    key = os.environ.get("OPENAI_ADMIN_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    request = urllib.request.Request(
        "https://api.openai.com" + path,
        headers={"Authorization": "Bearer " + key, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _split_line(line: str) -> tuple[str | None, str | None]:
    text = line.strip()
    if not text:
        return None, None
    model, _, rest = text.partition(",")
    rest = rest.lower()
    if "output" in rest or "completion" in rest:
        kind = "output"
    elif "cache" in rest:
        kind = "cached"
    else:
        kind = "input"
    return model.strip(), kind


def _per_token(amount, quantity, unit) -> float | None:
    if amount is None or not quantity:
        return None
    label = (unit or "tokens").lower().replace(" ", "")
    scale = {
        "token": 1,
        "tokens": 1,
        "1000_tokens": 1000,
        "1k_tokens": 1000,
        "1000000_tokens": 1_000_000,
        "1m_tokens": 1_000_000,
    }.get(label, 1)
    return float(amount) / (float(quantity) * scale)


def _note(source: str, costs_status: str, unknown: list[str], day: str, rows: list, usage_status: str) -> str:
    if source == "platform.costs":
        text = "Charge uses the token counts on each API response and the rate from the platform costs API."
    elif costs_status == "missing_scope":
        text = (
            "Charge uses the token counts on each API response and OpenAI's published price. "
            "The platform costs API needs a key with api.usage.read. Set OPENAI_ADMIN_KEY to use the billed rate."
        )
    elif costs_status == "empty":
        text = "The platform costs API has no line items for the last 7 days, so the charge uses OpenAI's published price."
    else:
        text = "Charge uses the token counts on each API response and OpenAI's published price."
    if unknown:
        names = ", ".join(sorted(set(unknown)))
        text += f" No price is available for {names}."
    if usage_status == "ok" and rows:
        parts = [
            f"{row['model'] or row['operation']}: {row['inputTokens']} in, {row['outputTokens']} out"
            for row in rows[:4]
        ]
        text += f" Platform usage for {day}: " + "; ".join(parts) + "."
    return text
