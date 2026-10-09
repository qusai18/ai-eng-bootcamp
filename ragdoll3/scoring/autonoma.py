"""Ragas batch scores and DeepEval reasons for the four Autonoma metrics."""

from __future__ import annotations

import os
from collections.abc import Iterable

from scoring.offline import DEEPEVAL_THRESHOLDS, apply_offline

RAGAS_FIELDS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
_RAGAS_ALIASES = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "response_relevancy": "answer_relevancy",
    "context_precision": "context_precision",
    "context_recall": "context_recall",
    "llm_context_precision_with_reference": "context_precision",
    "llm_context_recall": "context_recall",
}


def score_autonoma(
    rows_by_doll: dict[str, list[dict]],
    references: dict[str, str],
    api_key: str,
    model: str,
    *,
    ragas: bool,
    deepeval: bool,
) -> list[str]:
    if not ragas and not deepeval:
        return []
    if api_key == "offline-demo":
        apply_offline(
            rows_by_doll,
            references,
            ragas=ragas,
            deepeval=deepeval,
            pairwise=False,
            reference=False,
        )
        return ["offline-demo key: Ragas and DeepEval columns are lexical stand-ins."]
    notes: list[str] = []
    previous = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = api_key
    try:
        if ragas:
            notes.extend(_score_ragas(rows_by_doll, references, model))
        if deepeval:
            notes.extend(_score_deepeval(rows_by_doll, references, model))
    finally:
        if previous is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous
    return notes


def _ready_rows(rows_by_doll: dict[str, list[dict]]) -> list[tuple[str, dict]]:
    ready = []
    for doll_id, rows in rows_by_doll.items():
        for row in rows:
            if row.get("error") or not str(row.get("answer") or "").strip():
                continue
            ready.append((doll_id, row))
    return ready


def _contexts(row: dict) -> list[str]:
    texts = [str(context.get("text") or "").strip() for context in row.get("contexts") or []]
    texts = [text for text in texts if text]
    return texts or [" "]


def _score_ragas(rows_by_doll: dict[str, list[dict]], references: dict[str, str], model: str) -> list[str]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError as exc:
        return [f"Ragas is not installed ({exc})."]

    ready = _ready_rows(rows_by_doll)
    if not ready:
        return ["Ragas skipped: no successful answers."]
    notes = []
    generation = [faithfulness, answer_relevancy]
    notes.extend(_run_ragas(evaluate, Dataset, ready, generation, references, model, need_reference=False))
    referenced = [(doll_id, row) for doll_id, row in ready if references.get(row["qid"])]
    if referenced:
        notes.extend(
            _run_ragas(
                evaluate,
                Dataset,
                referenced,
                [context_precision, context_recall],
                references,
                model,
                need_reference=True,
            )
        )
    return notes


def _run_ragas(evaluate, dataset_cls, ready, metrics, references, model, *, need_reference: bool) -> list[str]:
    frame = {
        "user_input": [row["query"] for _, row in ready],
        "response": [row["answer"] for _, row in ready],
        "retrieved_contexts": [_contexts(row) for _, row in ready],
        "reference": [references.get(row["qid"]) or row["answer"] for _, row in ready],
    }
    try:
        kwargs = {"dataset": dataset_cls.from_dict(frame), "metrics": metrics}
        try:
            from langchain_openai import ChatOpenAI
            from ragas.llms import LangchainLLMWrapper

            kwargs["llm"] = LangchainLLMWrapper(ChatOpenAI(model=model, temperature=0))
        except ImportError:
            pass
        result = evaluate(**kwargs)
        table = result.to_pandas()
    except Exception as exc:
        label = "context metrics" if need_reference else "faithfulness and answer relevancy"
        return [f"Ragas {label} failed: {exc}"]

    for index, (_, row) in enumerate(ready):
        scored = row.setdefault("ragas", {})
        for column in table.columns:
            canonical = _RAGAS_ALIASES.get(str(column))
            if canonical not in RAGAS_FIELDS:
                continue
            value = table.iloc[index][column]
            try:
                scored[canonical] = float(value)
            except (TypeError, ValueError):
                continue
    return []


def _score_deepeval(rows_by_doll: dict[str, list[dict]], references: dict[str, str], model: str) -> list[str]:
    try:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            FaithfulnessMetric,
        )
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        return [f"DeepEval is not installed ({exc})."]

    ready = _ready_rows(rows_by_doll)
    if not ready:
        return ["DeepEval skipped: no successful answers."]
    failures = 0
    for _, row in ready:
        reference = references.get(row["qid"])
        case = LLMTestCase(
            input=row["query"],
            actual_output=row["answer"],
            retrieval_context=_contexts(row),
            expected_output=reference or row["answer"],
        )
        builders = [
            ("faithfulness", lambda: FaithfulnessMetric(threshold=DEEPEVAL_THRESHOLDS["faithfulness"], include_reason=True, model=model)),
            ("answer_relevancy", lambda: AnswerRelevancyMetric(threshold=DEEPEVAL_THRESHOLDS["answer_relevancy"], include_reason=True, model=model)),
        ]
        if reference:
            builders.extend(
                [
                    ("context_precision", lambda: ContextualPrecisionMetric(threshold=DEEPEVAL_THRESHOLDS["context_precision"], include_reason=True, model=model)),
                    ("context_recall", lambda: ContextualRecallMetric(threshold=DEEPEVAL_THRESHOLDS["context_recall"], include_reason=True, model=model)),
                ]
            )
        scored = {}
        for name, build in builders:
            try:
                metric = build()
                metric.measure(case)
                score = float(metric.score)
                scored[name] = {
                    "score": score,
                    "threshold": DEEPEVAL_THRESHOLDS[name],
                    "reason": str(getattr(metric, "reason", "") or ""),
                    "ok": bool(metric.is_successful()) if hasattr(metric, "is_successful") else score >= DEEPEVAL_THRESHOLDS[name],
                }
            except Exception as exc:
                failures += 1
                scored[name] = {
                    "score": None,
                    "threshold": DEEPEVAL_THRESHOLDS[name],
                    "reason": f"DeepEval failed: {exc}",
                    "ok": False,
                }
        row["deepeval"] = scored
    if failures:
        return [f"DeepEval could not score {failures} metric calls."]
    return []


def enabled_names(flags: Iterable[bool]) -> list[str]:
    return [name for name, flag in zip(("ragas", "deepeval"), flags, strict=True) if flag]
