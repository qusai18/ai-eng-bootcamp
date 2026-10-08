"""Score endpoint answers with RAGDoll's published metric functions.

The official support judge and arena judge run through a Pi model. This bench
assigns the same labels RAGDoll expects (support 2/1/0, nugget support /
partial_support / not_support, arena Tie / preferred run) with a lexical judge
so a comparison can run locally. The numbers then come from RAGDoll itself:
``support_metric``, ``cell_metric``, ``pairwise_rows``, and ``system_counts``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAGDOLL_SRC = Path(__file__).resolve().parents[1] / "third_party"
if str(RAGDOLL_SRC) not in sys.path:
    sys.path.insert(0, str(RAGDOLL_SRC))

from ragdoll.arena.metrics import pairwise_rows, system_counts  # noqa: E402
from ragdoll.nuggetizer.metrics import cell_metric  # noqa: E402
from ragdoll.support.metrics import support_metric  # noqa: E402

_TOKEN = re.compile(r"[a-z0-9]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall(text.lower()) if len(token) > 2}


def coverage(needle: str, haystack: str) -> float:
    """Share of needle tokens that also appear in haystack."""
    left = tokens(needle)
    if not left:
        return 0.0
    right = tokens(haystack)
    return len(left & right) / len(left)


def split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE.split(text.strip()) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def support_label(statement: str, citation: str) -> int:
    """Map lexical overlap onto RAGDoll's 2 / 1 / 0 support scale."""
    score = coverage(statement, citation)
    if score >= 0.55:
        return 2
    if score >= 0.28:
        return 1
    return 0


def nugget_assignment(nugget: str, answer: str) -> str:
    score = coverage(nugget, answer)
    if score >= 0.55:
        return "support"
    if score >= 0.28:
        return "partial_support"
    return "not_support"


def normalize_answer(payload: object, topic: dict) -> dict:
    """Accept TREC rows or a simple {answer, citations} payload."""
    if isinstance(payload, str):
        payload = {"answer": payload}
    if not isinstance(payload, dict):
        raise ValueError("endpoint response must be a JSON object or string")

    if isinstance(payload.get("answer"), list):
        sentences = []
        references = [str(ref) for ref in payload.get("references") or []]
        for item in payload["answer"]:
            if isinstance(item, str):
                sentences.append({"text": item, "citations": []})
                continue
            if not isinstance(item, dict):
                continue
            citations = []
            for cite in item.get("citations") or []:
                if isinstance(cite, int) and 0 <= cite < len(references):
                    doc_id = references[cite]
                    text = _lookup(topic, doc_id)
                    citations.append({"doc_id": doc_id, "text": text or ""})
                elif isinstance(cite, dict):
                    citations.append(_citation_record(cite, topic))
            sentences.append({"text": str(item.get("text") or ""), "citations": citations})
        return {"sentences": [row for row in sentences if row["text"]], "raw": payload}

    text = str(payload.get("answer") or payload.get("text") or payload.get("output") or "")
    citations = []
    for cite in payload.get("citations") or payload.get("contexts") or []:
        if isinstance(cite, str):
            citations.append({"doc_id": "", "text": cite})
        elif isinstance(cite, dict):
            citations.append(_citation_record(cite, topic))
    sentences = []
    for index, sentence in enumerate(split_sentences(text)):
        attached = [
            cite
            for cite in citations
            if cite.get("sentence_index") in (None, index)
        ]
        # A single shared context list applies to every sentence.
        if citations and all(cite.get("sentence_index") is None for cite in citations):
            attached = citations
        sentences.append({"text": sentence, "citations": attached})
    return {"sentences": sentences, "raw": payload}


def _citation_record(cite: dict, topic: dict) -> dict:
    doc_id = str(cite.get("doc_id") or cite.get("docid") or cite.get("id") or "")
    text = str(cite.get("text") or cite.get("segment") or cite.get("passage") or "")
    if not text and doc_id:
        text = _lookup(topic, doc_id) or ""
    record = {"doc_id": doc_id, "text": text}
    if "sentence_index" in cite:
        record["sentence_index"] = cite["sentence_index"]
    return record


def _lookup(topic: dict, doc_id: str) -> str | None:
    for passage in topic["passages"]:
        if passage["doc_id"] == doc_id:
            return passage["text"]
    return None


def score_system(run_id: str, topic: dict, normalized: dict) -> dict:
    sentences = []
    for index, sentence in enumerate(normalized["sentences"]):
        citations = []
        for cite_index, cite in enumerate(sentence["citations"]):
            if not cite.get("text"):
                continue
            citations.append(
                {
                    "citationID": cite_index,
                    "reference": cite.get("doc_id") or f"cite-{cite_index}",
                    "support": str(support_label(sentence["text"], cite["text"])),
                }
            )
        sentences.append({"sentenceID": index, "text": sentence["text"], "citations": citations})

    support = support_metric(
        {"topic_id": topic["id"], "run_id": run_id, "sentences": sentences}
    )
    nuggets = []
    answer_text = " ".join(sentence["text"] for sentence in normalized["sentences"])
    for nugget in topic["nuggets"]:
        nuggets.append(
            {
                "text": nugget["text"],
                "importance": nugget["importance"],
                "assignment": nugget_assignment(nugget["text"], answer_text),
            }
        )
    cell = cell_metric(
        {
            "qid": topic["id"],
            "run_id": run_id,
            "nuggets": nuggets,
            "answer_text": answer_text,
        }
    )
    return {
        "run_id": run_id,
        "topic_id": topic["id"],
        "answer_text": answer_text,
        "sentences": sentences,
        "nuggets": nuggets,
        "support": {
            "weighted_precision": support.weighted_precision_first_citation,
            "weighted_recall": support.weighted_recall_first_citation,
            "hard_precision": support.hard_precision,
            "hard_recall": support.hard_recall,
            "sentences": support.sentences,
        },
        "nugget": {
            "strict_vital": cell.strict_vital_score,
            "vital": cell.vital_score,
            "strict_all": cell.strict_all_score,
            "all": cell.all_score,
        },
    }


def composite(row: dict) -> float:
    return 0.5 * row["nugget"]["vital"] + 0.5 * row["support"]["weighted_recall"]


def compare(results: list[dict]) -> dict:
    """Build a leaderboard and RAGDoll pairwise rows from per-topic scores."""
    by_run: dict[str, list[dict]] = {}
    by_topic: dict[str, list[dict]] = {}
    for row in results:
        by_run.setdefault(row["run_id"], []).append(row)
        by_topic.setdefault(row["topic_id"], []).append(row)

    leaderboard = []
    for run_id, rows in by_run.items():
        def avg(key_path: tuple[str, str]) -> float:
            return sum(row[key_path[0]][key_path[1]] for row in rows) / len(rows)

        leaderboard.append(
            {
                "run_id": run_id,
                "topics": len(rows),
                "vital": avg(("nugget", "vital")),
                "strict_vital": avg(("nugget", "strict_vital")),
                "all": avg(("nugget", "all")),
                "citation_precision": avg(("support", "weighted_precision")),
                "citation_recall": avg(("support", "weighted_recall")),
                "composite": sum(composite(row) for row in rows) / len(rows),
            }
        )

    judgments = []
    coverage = []
    run_ids = list(by_run)
    for left_index, run_a in enumerate(run_ids):
        for run_b in run_ids[left_index + 1 :]:
            pair_topics = []
            for topic_id, rows in by_topic.items():
                found = {row["run_id"]: row for row in rows}
                if run_a in found and run_b in found:
                    pair_topics.append((topic_id, found[run_a], found[run_b]))
            coverage.append({"run_a": run_a, "run_b": run_b, "shared_topics": len(pair_topics)})
            for topic_id, left, right in pair_topics:
                gap = composite(left) - composite(right)
                both_bad = composite(left) < 0.2 and composite(right) < 0.2
                if both_bad:
                    verdict = "Tie (Both Bad)"
                    preferred = None
                elif abs(gap) < 0.08:
                    verdict = "Tie"
                    preferred = None
                elif gap > 0:
                    verdict = "A"
                    preferred = run_a
                else:
                    verdict = "B"
                    preferred = run_b
                judgments.append(
                    {
                        "status": "completed",
                        "pair": [run_a, run_b],
                        "qid": topic_id,
                        "judge_verdict": verdict,
                        "preferred_run_id": preferred,
                        "score_gap": round(gap, 4),
                    }
                )

    counts = system_counts(judgments)
    pairs = pairwise_rows(judgments, coverage) if coverage else []
    for row in leaderboard:
        stats = counts.get(row["run_id"], {"wins": 0, "losses": 0, "ties": 0, "n_judgments": 0})
        row["wins"] = stats["wins"]
        row["losses"] = stats["losses"]
        row["ties"] = stats["ties"]
        row["battles"] = stats["n_judgments"]

    leaderboard.sort(key=lambda row: (row["composite"], row["wins"]), reverse=True)
    for rank, row in enumerate(leaderboard, start=1):
        row["rank"] = rank

    return {"leaderboard": leaderboard, "pairwise": pairs, "judgments": judgments}
