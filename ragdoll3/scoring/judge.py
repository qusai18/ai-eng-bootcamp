"""The RAGDoll2 1–5 judge, called from the server."""

from __future__ import annotations

import json
import re

JUDGE_SYS = (
    "You are a strict, impartial RAG evaluator. You judge answers using ONLY the "
    "provided retrieved contexts as evidence. Respond with a single JSON object and nothing else."
)


def judge_prompt(question: str, contexts: list[dict], answer: str) -> str:
    if contexts:
        excerpts = "\n\n".join(
            f"[{index + 1}] {context.get('text', '')[:600]}"
            for index, context in enumerate(contexts[:6])
        )
    else:
        excerpts = (
            "NO CONTEXTS WERE RETRIEVED. If the answer asserts factual claims without "
            "evidence, score faithfulness and groundedness 1 — unless it explicitly says "
            "it lacks the information."
        )
    return f"""QUESTION: {question}

RETRIEVED CONTEXTS:
{excerpts}

ANSWER TO EVALUATE:
{answer}

Score each dimension from 1 to 5 (integers):
- faithfulness: 5 = every claim is supported by the contexts; 1 = claims contradict or go beyond the evidence.
- relevance: 5 = directly and fully answers the question; 1 = does not address it.
- groundedness: 5 = the specific facts are traceable to the contexts; 1 = no traceable facts.

Also list short quotes of any hallucinated claims (empty array if none).

Return exactly: {{"faithfulness": n, "relevance": n, "groundedness": n, "hallucinations": [], "note": "one sentence"}}"""


def parse_judge(text: str) -> dict | None:
    match = re.search(r"\{[\s\S]*\}", str(text))
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    def grade(value) -> int | None:
        try:
            number = round(float(value))
        except (TypeError, ValueError):
            return None
        return number if 1 <= number <= 5 else None

    hallucinations = payload.get("hallucinations")
    if not isinstance(hallucinations, list):
        hallucinations = []
    return {
        "faith": grade(payload.get("faithfulness")),
        "rel": grade(payload.get("relevance")),
        "gj": grade(payload.get("groundedness")),
        "hallucinations": [str(item) for item in hallucinations[:5]],
        "note": str(payload.get("note") or ""),
    }
