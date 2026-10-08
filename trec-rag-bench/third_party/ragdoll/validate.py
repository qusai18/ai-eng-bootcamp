"""`validate`: schema-check an input JSONL with actionable per-line errors.

Catches the common shape mistakes (missing ``candidates``, nuggets without
``assignment``, answers without text) before a long, billed run.
"""

from __future__ import annotations

import json
from typing import Any

from ragdoll.config import ValidateConfig

KINDS = ("create", "nuggets", "answers", "assign", "assignment")
_MAX_ERRORS = 50


def _has_query(row: dict[str, Any]) -> bool:
    query = row.get("query")
    return isinstance(query, str) or (isinstance(query, dict) and isinstance(query.get("text"), str))


def detect_kind(row: dict[str, Any]) -> str:
    if "candidates" in row:
        return "create"
    if "answer_record" in row or "answer_records" in row:
        return "assign"
    if "context" in row and "nuggets" in row:
        return "assign"
    nuggets = row.get("nuggets")
    if isinstance(nuggets, list):
        if any(isinstance(n, dict) and "assignment" in n for n in nuggets):
            return "assignment"
        return "nuggets"
    if "answer_text" in row or "answer" in row:
        return "answers"
    return "unknown"


def _check_nuggets(nuggets: Any, *, require_assignment: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(nuggets, list):
        return ["`nuggets` must be a list"]
    for index, nugget in enumerate(nuggets):
        if isinstance(nugget, str):
            if require_assignment:
                errors.append(f"nugget[{index}] is a string but an `assignment` label is required")
            continue
        if not isinstance(nugget, dict) or not nugget.get("text"):
            errors.append(f"nugget[{index}] must be a string or an object with non-empty `text`")
        elif require_assignment and not nugget.get("assignment"):
            errors.append(f"nugget[{index}] is missing an `assignment` label")
    return errors


def check_row(kind: str, row: dict[str, Any]) -> list[str]:
    if kind == "create":
        errors = [] if _has_query(row) else ["`query` must be a string or object with `text`"]
        candidates = row.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            errors.append("`candidates` must be a non-empty list")
        return errors
    if kind == "nuggets":
        errors = [] if _has_query(row) else ["`query` must be a string or object with `text`"]
        return errors + _check_nuggets(row.get("nuggets"), require_assignment=False)
    if kind == "answers":
        errors = [] if (row.get("qid") or row.get("topic_id")) else ["missing `qid`/`topic_id`"]
        if not (row.get("answer_text") or row.get("answer")):
            errors.append("missing `answer_text` or `answer`")
        return errors
    if kind == "assign":
        if {"query", "context", "nuggets"} <= row.keys():
            return _check_nuggets(row.get("nuggets"), require_assignment=False)
        if "answer_record" in row and "nugget_record" in row:
            return []
        if "answer_records" in row and "nugget_record" in row:
            return []
        return ["assign rows need query+context+nuggets or answer_record(s)+nugget_record"]
    if kind == "assignment":
        return _check_nuggets(row.get("nuggets"), require_assignment=True)
    return [f"unknown kind: {kind}"]


def validate(config: ValidateConfig) -> None:
    if config.kind != "auto" and config.kind not in KINDS:
        raise SystemExit(f"--kind must be one of auto,{','.join(KINDS)}")
    detected = config.kind
    errors: list[str] = []
    n = 0
    with config.input_file.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            n += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_number}: invalid JSON: {exc}")
                if len(errors) >= _MAX_ERRORS:
                    break
                continue
            if not isinstance(row, dict):
                errors.append(f"line {line_number}: expected a JSON object")
                continue
            if detected == "auto":
                detected = detect_kind(row)
                if detected == "unknown":
                    errors.append(f"line {line_number}: could not detect record kind (pass --kind)")
                    break
            for message in check_row(detected, row):
                errors.append(f"line {line_number}: {message}")
            if len(errors) >= _MAX_ERRORS:
                break

    print(f"validate: file={config.input_file} kind={detected} rows={n} errors={len(errors)}")
    for message in errors[:_MAX_ERRORS]:
        print(f"  {message}")
    if errors:
        raise SystemExit(f"validation failed: {len(errors)} error(s)")
    print(f"[ok] {config.input_file} is valid as kind={detected}")
