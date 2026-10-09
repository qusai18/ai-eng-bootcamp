"""Lexical stand-ins used when the judge key is the local smoke value.

These numbers are not Ragas, DeepEval, or BenchmarkQED scores. They exist so the
verdict columns can be checked without an OpenAI key. A real key calls the libraries.
"""

from __future__ import annotations

from scoring.lexical import tokens

DEEPEVAL_THRESHOLDS = {
    "faithfulness": 0.90,
    "answer_relevancy": 0.80,
    "context_precision": 0.75,
    "context_recall": 0.90,
}
PAIRWISE = ("relevance", "comprehensiveness", "diversity", "empowerment")


def _overlap(left: str, right: str) -> float:
    left_tokens = set(tokens(left))
    right_tokens = set(tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def apply_offline(
    rows_by_doll: dict[str, list[dict]],
    references: dict[str, str],
    *,
    ragas: bool,
    deepeval: bool,
    pairwise: bool,
    reference: bool,
) -> None:
    quality: dict[str, dict[str, float]] = {}
    for doll_id, rows in rows_by_doll.items():
        quality[doll_id] = {}
        for row in rows:
            if row.get("error") or not row.get("answer"):
                continue
            local = row.get("local") or {}
            ground = local.get("ground")
            overlap = local.get("ctxOvl")
            faith = _clip(0.2 + 0.8 * (ground if ground is not None else 0.0))
            relevancy = _clip(0.15 + 0.85 * (overlap if overlap is not None else 0.0))
            quality[doll_id][row["qid"]] = (faith + relevancy) / 2
            reference_text = references.get(row["qid"])
            context_text = " ".join(context.get("text") or "" for context in row.get("contexts") or [])
            precision = _overlap(context_text, reference_text) if reference_text else None
            recall = _overlap(reference_text, context_text) if reference_text else None
            if ragas:
                row["ragas"] = {
                    "faithfulness": faith,
                    "answer_relevancy": relevancy,
                    "context_precision": precision,
                    "context_recall": recall,
                }
            if deepeval:
                scores = {
                    "faithfulness": faith,
                    "answer_relevancy": relevancy,
                }
                if reference_text:
                    scores["context_precision"] = precision or 0.0
                    scores["context_recall"] = recall or 0.0
                row["deepeval"] = {
                    name: {
                        "score": score,
                        "threshold": DEEPEVAL_THRESHOLDS[name],
                        "reason": (
                            "offline-demo stand-in from lexical overlap, not a DeepEval judge."
                        ),
                        "ok": score >= DEEPEVAL_THRESHOLDS[name],
                    }
                    for name, score in scores.items()
                }
            if reference and reference_text:
                row.setdefault("qed", {})
                row["qed"]["correctness"] = round(1 + 9 * _overlap(row["answer"], reference_text), 2)
                row["qed"]["completeness"] = round(1 + 9 * _overlap(reference_text, row["answer"]), 2)

    if not pairwise:
        return
    doll_ids = [doll_id for doll_id, rows in rows_by_doll.items() if any(not row.get("error") and row.get("answer") for row in rows)]
    if len(doll_ids) < 2:
        return
    for doll_id, rows in rows_by_doll.items():
        for row in rows:
            if row.get("error") or not row.get("answer"):
                continue
            mine = quality.get(doll_id, {}).get(row["qid"])
            if mine is None:
                continue
            others = [
                quality[other].get(row["qid"])
                for other in doll_ids
                if other != doll_id and row["qid"] in quality.get(other, {})
            ]
            others = [score for score in others if score is not None]
            if not others:
                continue
            wins = sum(1 if mine > other else 0.5 if mine == other else 0 for other in others) / len(others)
            row.setdefault("qed", {})
            for criterion in PAIRWISE:
                row["qed"][criterion] = wins
