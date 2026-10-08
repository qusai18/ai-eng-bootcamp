from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any

from ragdoll.config import (
    LocalAgentConfig,
    NuggetAgenticCreateConfig,
    NuggetAssignConfig,
    NuggetCreateConfig,
    NuggetEvalConfig,
    NuggetMetricsConfig,
)
from ragdoll.jsonl import append_jsonl, completed_task_ids, read_jsonl, write_jsonl
from ragdoll.nuggetizer.metrics import compute_metrics
from ragdoll.nuggetizer.prompts import parse_label_list
from ragdoll.nuggetizer.stages import (
    _assign_windowed,
    _create_windowed,
    _load_assign_payloads,
    _score_windowed,
    iter_agentic_create_tasks,
    iter_create_inputs,
)
from ragdoll.runner import run_prompt, select_rows
from ragdoll.trec_io import iter_assign_payloads_from_files


def _select_tasks(items: list[dict[str, Any]], *, config: Any, output: Path) -> list[dict[str, Any]]:
    """Apply resume/overwrite/shuffle/limit and log a one-line selection summary."""
    total = len(items)
    done = completed_task_ids(output) if (config.resume and not config.overwrite) else set()
    selected = select_rows(
        items,
        output=output,
        resume=config.resume,
        overwrite=config.overwrite,
        shuffle=config.shuffle,
        seed=config.seed,
        limit=config.limit,
    )
    if done or len(selected) != total:
        print(f"selected {len(selected)}/{total} tasks (resume-skipped={len(done)})", flush=True)
    return selected


def _assign_output_row(
    item: dict[str, Any],
    assigned: list[tuple[dict[str, Any], str]],
    *,
    include_trace: bool,
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "task_id": item["task_id"],
        "status": "completed",
        "qid": item.get("qid", ""),
        "run_id": item.get("run_id", ""),
        "query": item["query"],
        "answer_text": item.get("answer_text", item["context"]),
        "response_length": item.get("response_length"),
        "context": item["context"],
        "nuggets": [{**nugget, "assignment": assignment} for nugget, assignment in assigned],
    }
    if include_trace:
        row["trace"] = traces
    return row


async def create(config: NuggetCreateConfig) -> None:
    if config.overwrite and config.output_file.exists():
        config.output_file.unlink()
    agent_config = config.local_agent_config()
    raw_events_dir = config.raw_events_dir or config.output_file.parent / "raw-events" / config.output_file.stem
    inputs = iter_create_inputs(list(read_jsonl(config.input_file)))
    inputs = _select_tasks(inputs, config=config, output=config.output_file)
    if config.dry_run:
        print(f"[dry-run] create would process {len(inputs)} topics -> {config.output_file}")
        return
    semaphore = asyncio.Semaphore(max(1, config.max_concurrency))

    async def one(item: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            nuggets, creator_traces = await _create_windowed(
                base_task_id=item["task_id"],
                qid=item["qid"],
                query=item["query"],
                candidates=item["candidates"],
                initial_nuggets=item["initial_nuggets"],
                agent_config=agent_config,
                raw_events_dir=raw_events_dir,
                window_size=config.window_size,
                max_trials=config.max_trials,
                max_nuggets=config.max_nuggets,
            )
            scored, scorer_traces = await _score_windowed(
                base_task_id=item["task_id"],
                qid=item["qid"],
                query=item["query"],
                nuggets=nuggets,
                agent_config=agent_config,
                raw_events_dir=raw_events_dir,
                window_size=config.window_size,
                max_trials=config.max_trials,
            )
            row: dict[str, Any] = {
                "task_id": item["task_id"],
                "status": "completed",
                "qid": item["qid"],
                "query": item["query"],
                "nuggets": [{"text": text, "importance": importance} for text, importance in scored],
            }
            if config.include_trace:
                row["creator_trace"] = creator_traces
                row["scorer_trace"] = scorer_traces
            return row

    pending = [asyncio.create_task(one(item)) for item in inputs]
    for future in asyncio.as_completed(pending):
        row = await future
        append_jsonl(config.output_file, row)
        print(f"completed task_id={row['task_id']}", flush=True)
    print(f"processed={len(inputs)} output={config.output_file} raw_events_dir={raw_events_dir}")


async def agentic_create(config: NuggetAgenticCreateConfig) -> None:
    if config.overwrite:
        if config.output_file.exists():
            config.output_file.unlink()
        if config.failed_output and config.failed_output.exists():
            config.failed_output.unlink()
    tasks = select_rows(
        iter_agentic_create_tasks(list(read_jsonl(config.input_file)), creator_max_nuggets=config.max_nuggets),
        output=config.output_file,
        resume=config.resume,
        overwrite=config.overwrite,
        shuffle=config.shuffle,
        seed=config.seed,
        limit=config.limit,
    )
    if config.dry_run:
        print(f"[dry-run] agentic-create would process {len(tasks)} topics -> {config.output_file}")
        return
    agent_config = config.local_agent_config()
    raw_events_dir = config.raw_events_dir or config.output_file.parent / "raw-events" / config.output_file.stem
    semaphore = asyncio.Semaphore(max(1, config.max_concurrency))

    async def one(task: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _run_agentic_create_task(
                task,
                agent_config=agent_config,
                raw_events_dir=raw_events_dir,
                max_nuggets=config.max_nuggets,
                window_size=config.window_size,
                max_trials=config.max_trials,
                include_trace=config.include_trace,
            )

    pending = [asyncio.create_task(one(task)) for task in tasks]
    for future in asyncio.as_completed(pending):
        row = await future
        if row["status"] == "completed":
            append_jsonl(config.output_file, row)
        elif config.failed_output:
            append_jsonl(config.failed_output, row)
        print(f"{row['status']} task_id={row['task_id']}", flush=True)
    print(f"processed={len(tasks)} output={config.output_file} raw_events_dir={raw_events_dir}")


async def _run_agentic_create_task(
    task: dict[str, Any],
    *,
    agent_config: LocalAgentConfig,
    raw_events_dir: Path,
    max_nuggets: int,
    window_size: int,
    max_trials: int,
    include_trace: bool,
) -> dict[str, Any]:
    metadata = task["metadata"]
    created = await run_prompt(
        task_id=f"{task['task_id']}:agentic-create",
        evaluator="nugget-agentic-create",
        instruction=task["instruction"],
        raw_events_dir=raw_events_dir,
        config=replace(agent_config, system_prompt=task["system_prompt"]),
        metadata=metadata,
    )
    if created["status"] != "completed":
        return _agentic_failed_row(
            task=task, error=created["error"] or "agentic creator failed", trace=created, include_trace=include_trace
        )
    nuggets = parse_label_list(created["output_text"])
    if nuggets is None:
        return _agentic_failed_row(
            task=task,
            error="could not parse agentic creator output as a Python list",
            trace=created,
            include_trace=include_trace,
        )
    nuggets = nuggets[:max_nuggets]
    scored, scorer_traces = await _score_windowed(
        base_task_id=task["task_id"],
        qid=metadata["qid"],
        query=metadata["query"],
        nuggets=nuggets,
        agent_config=agent_config,
        raw_events_dir=raw_events_dir,
        window_size=window_size,
        max_trials=max_trials,
    )
    row: dict[str, Any] = {
        "task_id": task["task_id"],
        "status": "completed",
        "qid": metadata["qid"],
        "query": metadata["query"],
        "initial_nuggets": metadata["initial_nuggets"],
        "nuggets": [{"text": text, "importance": importance} for text, importance in scored],
    }
    if include_trace:
        row["creator_trace"] = created
        row["scorer_trace"] = scorer_traces
    return row


def _agentic_failed_row(
    *, task: dict[str, Any], error: str, trace: dict[str, Any], include_trace: bool
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "task_id": task["task_id"],
        "status": "failed",
        "evaluator": "nugget-agentic-create",
        "error": error,
        "metadata": task["metadata"],
    }
    if include_trace:
        row["trace"] = trace
    return row


async def assign(config: NuggetAssignConfig) -> None:
    if config.overwrite and config.output_file.exists():
        config.output_file.unlink()
    agent_config = config.local_agent_config()
    raw_events_dir = config.raw_events_dir or config.output_file.parent / "raw-events" / config.output_file.stem
    items = _load_assign_payloads(config)
    items = _select_tasks(items, config=config, output=config.output_file)
    if config.dry_run:
        print(f"[dry-run] assign would process {len(items)} cells -> {config.output_file}")
        return
    semaphore = asyncio.Semaphore(max(1, config.max_concurrency))

    async def one(item: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            assigned, traces = await _assign_windowed(
                base_task_id=item["task_id"],
                query=item["query"],
                context=item["context"],
                nuggets=item["nuggets"],
                assign_mode=config.assign_mode,
                agent_config=agent_config,
                raw_events_dir=raw_events_dir,
                window_size=config.window_size,
                max_trials=config.max_trials,
            )
            return _assign_output_row(item, assigned, include_trace=config.include_trace, traces=traces)

    pending = [asyncio.create_task(one(item)) for item in items]
    for future in asyncio.as_completed(pending):
        row = await future
        append_jsonl(config.output_file, row)
        print(f"completed task_id={row['task_id']}", flush=True)
    print(f"processed={len(items)} output={config.output_file} raw_events_dir={raw_events_dir}")


_SHARED_FIELDS = (
    "agent_binary", "provider", "model", "thinking", "system_prompt", "temperature",
    "max_concurrency", "timeout_seconds", "agent_state_dir", "cache_dir",
    "resume", "overwrite", "dry_run", "limit", "shuffle", "seed",
    "window_size", "max_trials",
)


def _shared(config: NuggetEvalConfig) -> dict[str, Any]:
    return {name: getattr(config, name) for name in _SHARED_FIELDS}


async def eval_pipeline(config: NuggetEvalConfig) -> None:
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    shared = _shared(config)

    # 1) Nuggets: generate from candidates (E2E) or use the provided fixed list.
    if config.create_input is not None:
        nuggets_path = output_dir / "nuggets.jsonl"
        print(f"[eval] create nuggets: {config.create_input} -> {nuggets_path}")
        await create(
            NuggetCreateConfig(
                input_file=config.create_input,
                output_file=nuggets_path,
                max_nuggets=config.max_nuggets,
                **shared,
            )
        )
    else:
        nuggets_path = config.nuggets_file
        print(f"[eval] using fixed nuggets: {nuggets_path}")

    # 2) Join answers + nuggets into assign payloads, then assign.
    assign_inputs = output_dir / "assign_inputs.jsonl"
    written = write_jsonl(assign_inputs, iter_assign_payloads_from_files(config.answers_file, nuggets_path))
    print(f"[eval] joined {written} assign payloads -> {assign_inputs}")
    assignments = output_dir / "assignments.jsonl"
    await assign(
        NuggetAssignConfig(
            input_file=assign_inputs,
            output_file=assignments,
            assign_mode=config.assign_mode,
            **shared,
        )
    )

    if config.dry_run:
        print("[eval] dry-run: skipping metrics")
        return

    # 3) Score (and correlate against gold when provided).
    print(f"[eval] scoring {assignments} -> {output_dir / 'metrics'}")
    compute_metrics(
        NuggetMetricsConfig(
            input_file=assignments,
            output_dir=output_dir / "metrics",
            reference=config.gold,
        )
    )
    print(f"[eval] done -> {output_dir}")
