from __future__ import annotations

import asyncio
from typing import Any

from ragdoll.config import SupportJudgeConfig
from ragdoll.jsonl import append_jsonl, completed_task_ids, read_jsonl
from ragdoll.runner import run_prompt
from ragdoll.support.prompts import parse_support_label
from ragdoll.support.stages import iter_support_tasks


async def judge(config: SupportJudgeConfig) -> None:
    if config.overwrite and config.output_file.exists():
        config.output_file.unlink()
    tasks = iter_support_tasks(list(read_jsonl(config.input_file)))
    if config.resume and not config.overwrite:
        done = completed_task_ids(config.output_file)
        before = len(tasks)
        tasks = [task for task in tasks if str(task["task_id"]) not in done]
        if before != len(tasks):
            print(f"resume: skipped {before - len(tasks)} completed task(s)", flush=True)
    if config.limit is not None:
        tasks = tasks[: config.limit]
    agent_config = config.local_agent_config()
    raw_events_dir = config.raw_events_dir or config.output_file.parent / "raw-events" / config.output_file.stem
    semaphore = asyncio.Semaphore(max(1, config.max_concurrency))

    async def one(task: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            result = await run_prompt(
                task_id=task["task_id"],
                evaluator="support",
                instruction=task["instruction"],
                raw_events_dir=raw_events_dir,
                config=agent_config,
                metadata=task["metadata"],
            )
            label = parse_support_label(result["output_text"]) if result["status"] == "completed" else None
            row = {
                "task_id": task["task_id"],
                "statement": task["metadata"]["statement"],
                "citation": task["metadata"]["citation"],
                "support_label": label,
                "raw_output": result["output_text"],
                "status": result["status"] if label is not None else "failed",
                "error": result["error"] if label is not None else result["error"] or "could not parse support label",
                "metadata": task["metadata"]["source"],
            }
            if config.include_prompt:
                row["prompt"] = task["instruction"]
            return row

    for future in asyncio.as_completed([asyncio.create_task(one(task)) for task in tasks]):
        append_jsonl(config.output_file, await future)
    print(f"processed={len(tasks)} output={config.output_file} raw_events_dir={raw_events_dir}")
