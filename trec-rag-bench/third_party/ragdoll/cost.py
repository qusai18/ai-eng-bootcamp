"""`cost`: total token usage from a raw-events dir and (optionally) price it."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ragdoll.config import CostConfig, model_name
from ragdoll.runner import extract_usage

# USD per 1M tokens, keyed by bare model name. Empty by default on purpose:
# fill in verified prices or pass --input-price/--output-price at call time.
PRICES: dict[str, tuple[float, float]] = {}


def _read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def _prices(config: CostConfig) -> tuple[float | None, float | None]:
    table = PRICES.get(model_name(config.model), (None, None))
    input_price = config.input_price if config.input_price is not None else table[0]
    output_price = config.output_price if config.output_price is not None else table[1]
    return input_price, output_price


def cost(config: CostConfig) -> None:
    root = config.raw_events_dir
    if not root.exists():
        raise SystemExit(f"raw-events dir not found: {root}")

    rows: list[dict[str, Any]] = []
    files = with_usage = 0
    total_in = total_out = total = 0
    total_provider_cost = 0.0
    for path in sorted(root.rglob("*.jsonl")):
        files += 1
        usage = extract_usage(_read_events(path))
        if usage:
            with_usage += 1
        inp = int(usage.get("input_tokens", 0))
        out = int(usage.get("output_tokens", 0))
        tot = int(usage.get("total_tokens", inp + out))
        task_cost = float(usage.get("cost_usd", 0.0))
        total_in += inp
        total_out += out
        total += tot
        total_provider_cost += task_cost
        rows.append({
            "task": path.stem, "input_tokens": inp, "output_tokens": out,
            "total_tokens": tot, "cost_usd": round(task_cost, 6),
        })

    # Prefer the provider's own USD cost; fall back to a price-table estimate.
    input_price, output_price = _prices(config)
    estimated_cost = None
    if input_price is not None and output_price is not None:
        estimated_cost = total_in / 1e6 * input_price + total_out / 1e6 * output_price
    cost_usd = total_provider_cost if total_provider_cost > 0 else estimated_cost
    avg_cost = (cost_usd / with_usage) if (cost_usd is not None and with_usage) else None

    if config.output_file:
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        with config.output_file.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["task", "input_tokens", "output_tokens", "total_tokens", "cost_usd"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote per-task usage -> {config.output_file}")

    print(
        f"cost: files={files} with_usage={with_usage} "
        f"input_tokens={total_in} output_tokens={total_out} total_tokens={total}"
    )
    if total_provider_cost > 0:
        src = "provider-reported"
    elif cost_usd is not None:
        src = f"estimated (in=${input_price}/1M, out=${output_price}/1M)"
    else:
        src = None
    if cost_usd is not None:
        avg_str = f", avg/call=${avg_cost:.6f}" if avg_cost is not None else ""
        print(f"cost: total=${cost_usd:.4f}{avg_str} [{src}, model={config.model}]")
    elif with_usage:
        print("cost: unknown (no provider cost; pass --input-price and --output-price, USD per 1M tokens)")
    else:
        print("no usage found in events (provider may not emit token counts); raw events are still saved")
