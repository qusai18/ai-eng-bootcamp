from __future__ import annotations

from typing import Any

from ragdoll.config import MaterializeUmbrelaConfig
from ragdoll.jsonl import read_jsonl, write_jsonl
from ragdoll.umbrela.prompts import render_umbrela_prompt


def query_text(record: dict[str, Any]) -> tuple[str, str | None]:
    query = record.get("query")
    if isinstance(query, str):
        return query, None
    if isinstance(query, dict) and isinstance(query.get("text"), str):
        qid = str(query["qid"]) if query.get("qid") is not None else None
        return query["text"], qid
    raise ValueError("UMBRELA input requires `query` as a string or object with `text`")


def candidate_passage(candidate: Any) -> tuple[str, str | None]:
    if isinstance(candidate, str):
        return candidate, None
    if isinstance(candidate, dict):
        if isinstance(candidate.get("text"), str):
            return candidate["text"], str(candidate.get("docid")) if candidate.get("docid") is not None else None
        doc = candidate.get("doc")
        if isinstance(doc, dict) and isinstance(doc.get("segment"), str):
            docid = doc.get("docid", candidate.get("docid"))
            return doc["segment"], str(docid) if docid is not None else None
    raise ValueError("UMBRELA candidates must be strings or objects with `text` or `doc.segment`")


def iter_prompt_tasks(records: list[dict[str, Any]], *, prompt_type: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        query, qid = query_text(record)
        candidates = record.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("UMBRELA input requires `candidates` as a list")
        for candidate_index, candidate in enumerate(candidates):
            passage, docid = candidate_passage(candidate)
            task_id = str(
                record.get("task_id")
                or f"{qid or f'record{record_index:06d}'}:candidate{candidate_index:04d}"
            )
            if len(candidates) > 1 or "task_id" not in record:
                task_id = f"{task_id}:{candidate_index}"
            tasks.append(
                {
                    "task_id": task_id,
                    "evaluator": "umbrela",
                    "instruction": render_umbrela_prompt(query=query, passage=passage, prompt_type=prompt_type),
                    "metadata": {
                        "query": query,
                        "qid": qid,
                        "passage": passage,
                        "docid": docid,
                        "candidate_index": candidate_index,
                        "prompt_type": prompt_type,
                    },
                }
            )
    return tasks


def materialize(config: MaterializeUmbrelaConfig) -> None:
    tasks = iter_prompt_tasks(list(read_jsonl(config.input_file)), prompt_type=config.prompt_type)
    count = write_jsonl(config.output_file, tasks)
    print(f"wrote={count} output={config.output_file}")
