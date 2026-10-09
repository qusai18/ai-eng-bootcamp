"""BenchmarkQED AutoE pairwise win rates and reference scores.

Answers are written to a temporary directory and scored with the installed
`benchmark-qed` CLI. The directory, including any .env written for that run,
is deleted before this function returns.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import json

from scoring.offline import PAIRWISE, apply_offline

PAIRWISE_CRITERIA = PAIRWISE
REFERENCE_CRITERIA = ("correctness", "completeness")
_SLUG = re.compile(r"[^a-z0-9_]+")


def even_trials(trials: int) -> int:
    """BenchmarkQED rejects an odd trial count because it counterbalances order."""
    trials = max(1, int(trials))
    return trials if trials % 2 == 0 else trials + 1


def slug(name: str, used: set[str]) -> str:
    cleaned = _SLUG.sub("_", name.strip().lower()).strip("_") or "doll"
    candidate = cleaned
    suffix = 2
    while candidate in used:
        candidate = f"{cleaned}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def score_benchmark_qed(
    rows_by_doll: dict[str, list[dict]],
    doll_names: dict[str, str],
    references: dict[str, str],
    api_key: str,
    model: str,
    trials: int,
    *,
    pairwise: bool,
    reference: bool,
) -> list[str]:
    if not pairwise and not reference:
        return []
    if api_key == "offline-demo":
        apply_offline(
            rows_by_doll,
            references,
            ragas=False,
            deepeval=False,
            pairwise=pairwise,
            reference=reference,
        )
        return ["offline-demo key: BenchmarkQED columns are lexical stand-ins."]

    notes: list[str] = []
    usable = {
        doll_id: [row for row in rows if not row.get("error") and str(row.get("answer") or "").strip()]
        for doll_id, rows in rows_by_doll.items()
    }
    usable = {doll_id: rows for doll_id, rows in usable.items() if rows}
    if len(usable) < 1:
        return ["BenchmarkQED skipped: no successful answers."]

    used: set[str] = set()
    slugs = {doll_id: slug(doll_names.get(doll_id) or doll_id, used) for doll_id in usable}
    by_slug = {value: key for key, value in slugs.items()}
    trial_count = even_trials(trials)
    if trial_count != trials:
        notes.append(f"BenchmarkQED needs an even trial count; using {trial_count}.")

    root = Path(tempfile.mkdtemp(prefix="ragdoll3-qed-"))
    env = os.environ.copy()
    env["OPENAI_API_KEY"] = api_key
    try:
        input_dir = root / "input"
        for doll_id, rows in usable.items():
            _write_answers(input_dir / slugs[doll_id] / "live.json", rows)
        if pairwise and len(usable) >= 2:
            notes.extend(_pairwise(root, slugs, by_slug, rows_by_doll, model, trial_count, env))
        elif pairwise:
            notes.append("BenchmarkQED pairwise skipped: at least two dolls need a successful answer.")
        if reference:
            notes.extend(_reference(root, input_dir, slugs, by_slug, rows_by_doll, references, model, trial_count, env))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return notes


def _write_answers(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "question_id": row["qid"],
            "question_text": row["query"],
            "answer": row["answer"],
        }
        for row in rows
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _llm_config(model: str) -> dict:
    return {
        "auth_type": "api_key",
        "model": model or "gpt-4o-mini",
        "api_key": "${OPENAI_API_KEY}",
        "llm_provider": "openai.chat",
        "concurrent_requests": 4,
        "call_args": {"temperature": 0.0},
    }


def _run_cli(root: Path, command: str, env: dict) -> tuple[int, str]:
    settings = root / "settings.yaml"
    output = root / "output"
    output.mkdir(exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-m", "benchmark_qed", "autoe", command, str(settings), str(output)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60 * 30,
        check=False,
    )
    message = _scrub(f"{completed.stdout}\n{completed.stderr}".strip())
    return completed.returncode, message[-2000:]


def _scrub(text: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "[redacted]", text)


def _pairwise(root, slugs, by_slug, rows_by_doll, model, trials, env) -> list[str]:
    import yaml

    settings = {
        "others": [
            {"name": name, "answer_base_path": f"input/{name}"}
            for name in slugs.values()
        ],
        "question_sets": ["live"],
        "trials": trials,
        "llm_config": _llm_config(model),
    }
    (root / "settings.yaml").write_text(yaml.safe_dump(settings), encoding="utf-8")
    output = root / "output"
    if output.exists():
        shutil.rmtree(output)
    code, message = _run_cli(root, "pairwise-scores", env)
    parsed = _parse_pairwise(output, by_slug, rows_by_doll)
    if parsed:
        note = "BenchmarkQED pairwise scores read."
        if code != 0:
            note += " The significance step exited early; win rates still come from the pair files."
        return [note]
    detail = message or "no score files were written"
    return [f"BenchmarkQED pairwise failed: {detail}"]


def _reference(root, input_dir, slugs, by_slug, rows_by_doll, references, model, trials, env) -> list[str]:
    import yaml

    gold_rows = []
    seen = set()
    for rows in rows_by_doll.values():
        for row in rows:
            text = references.get(row["qid"])
            if text and row["qid"] not in seen:
                gold_rows.append({"qid": row["qid"], "query": row["query"], "answer": text})
                seen.add(row["qid"])
    if not gold_rows:
        return ["BenchmarkQED reference skipped: no reference answers match the topics."]
    _write_answers(input_dir / "gold" / "live.json", gold_rows)
    generated = []
    for doll_id, name in slugs.items():
        if any(references.get(row["qid"]) for row in rows_by_doll.get(doll_id, [])):
            generated.append({"name": name, "answer_base_path": f"input/{name}/live.json"})
    if not generated:
        return ["BenchmarkQED reference skipped: no doll answered a topic that has a reference."]
    settings = {
        "reference": {"name": "gold", "answer_base_path": "input/gold/live.json"},
        "generated": generated,
        "trials": trials,
        "score_min": 1,
        "score_max": 10,
        "llm_config": _llm_config(model),
    }
    (root / "settings.yaml").write_text(yaml.safe_dump(settings), encoding="utf-8")
    output = root / "output"
    if output.exists():
        shutil.rmtree(output)
    code, message = _run_cli(root, "reference-scores", env)
    parsed = _parse_reference(output, by_slug, rows_by_doll)
    if parsed:
        return ["BenchmarkQED reference scores read."]
    detail = message or "no score files were written"
    if code != 0:
        return [f"BenchmarkQED reference failed: {detail}"]
    return [f"BenchmarkQED reference failed: {detail}"]


def _parse_pairwise(output: Path, by_slug: dict[str, str], rows_by_doll: dict[str, list[dict]]) -> bool:
    """Average each doll's per-question win score across opponents and trials."""
    if not output.exists():
        return False
    buckets: dict[tuple[str, str, str], list[float]] = {}
    found = False
    for path in output.glob("*.csv"):
        if path.name in {"win_rates.csv", "winrates_sig_tests.csv"}:
            continue
        rows = _read_csv(path)
        if not rows or "criteria" not in rows[0]:
            continue
        for record in rows:
            criterion = record.get("criteria") or ""
            if criterion not in PAIRWISE_CRITERIA:
                continue
            question = record.get("question") or ""
            for name, doll_id in by_slug.items():
                raw = record.get(f"{name}_score")
                if raw in (None, ""):
                    continue
                try:
                    score = float(raw)
                except ValueError:
                    continue
                buckets.setdefault((doll_id, question, criterion), []).append(score)
                found = True
    if not found:
        return False
    for (doll_id, question, criterion), scores in buckets.items():
        mean = sum(scores) / len(scores)
        for row in rows_by_doll.get(doll_id, []):
            if row.get("query") == question and not row.get("error"):
                row.setdefault("qed", {})
                row["qed"][criterion] = mean
    return True


def _parse_reference(output: Path, by_slug: dict[str, str], rows_by_doll: dict[str, list[dict]]) -> bool:
    if not output.exists():
        return False
    found = False
    for path in output.glob("reference_scores-*.csv"):
        name = path.name[len("reference_scores-") : -len(".csv")]
        doll_id = by_slug.get(name)
        if not doll_id:
            continue
        grouped: dict[tuple[str, str], list[float]] = {}
        for record in _read_csv(path):
            criterion = record.get("criteria") or ""
            if criterion not in REFERENCE_CRITERIA:
                continue
            try:
                score = float(record.get("score") or "")
            except ValueError:
                continue
            grouped.setdefault((record.get("question") or "", criterion), []).append(score)
            found = True
        for (question, criterion), scores in grouped.items():
            mean = sum(scores) / len(scores)
            for row in rows_by_doll.get(doll_id, []):
                if row.get("query") == question and not row.get("error"):
                    row.setdefault("qed", {})
                    row["qed"][criterion] = mean
    return found


def _read_csv(path: Path) -> list[dict]:
    import csv

    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
