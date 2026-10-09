"""Lexical and qrel metrics, matched to the RAGDoll2 page."""

from __future__ import annotations

import math
import re

STOP = set(
    "a an the is are was were be been being to of in on at for with and or but if "
    "then than that this these those it its as by from can could would should do "
    "does did have has had not no nor you your we they he she i what which who whom "
    "when where why how also into over under about".split()
)
_TOKEN = re.compile(r"[a-z0-9][a-z0-9'-]*")
_CITE = re.compile(r"\[([^\[\]]{1,48})\]")
_SENT = re.compile(r"(?<=[.!?])\s+|\n+")
_NID = re.compile(r"%0a|\s+", re.IGNORECASE)


def tokens(text: str) -> list[str]:
    return [
        token
        for token in _TOKEN.findall(str(text).lower())
        if len(token) > 2 and token not in STOP
    ]


def nid(value: str) -> str:
    return _NID.sub("", str(value).strip().lower())


def ground_lex(answer: str, contexts: list[dict]) -> dict | None:
    if not answer or not contexts:
        return None
    sentences = [part.strip() for part in _SENT.split(answer) if part.strip()]
    sentences = [sentence for sentence in sentences if len(sentence) >= 12]
    if not sentences:
        return None
    context_tokens = [set(tokens(context.get("text") or "")) for context in contexts]
    supported = 0
    unsupported: list[str] = []
    for sentence in sentences:
        sentence_tokens = tokens(sentence)
        if not sentence_tokens:
            supported += 1
            continue
        best = 0.0
        for context in context_tokens:
            hits = sum(1 for token in sentence_tokens if token in context)
            best = max(best, hits / len(sentence_tokens))
        if best >= 0.45:
            supported += 1
        else:
            unsupported.append(sentence)
    return {"score": supported / len(sentences), "unsup": unsupported}


def citation_cov(answer: str, contexts: list[dict]) -> float | None:
    if not answer or not contexts:
        return None
    found = _CITE.findall(answer)
    if not found:
        return None
    ids = {nid(context.get("id") or "") for context in contexts}
    ids.discard("")
    cited: set[str] = set()
    for mark in found:
        trimmed = mark.strip()
        if trimmed.isdigit():
            index = int(trimmed) - 1
            if 0 <= index < len(contexts):
                cited.add(nid(contexts[index].get("id") or "") or f"#{index}")
        elif nid(mark) in ids:
            cited.add(nid(mark))
    return len(cited) / len(contexts)


def ctx_overlap(query: str, contexts: list[dict]) -> float | None:
    if not contexts:
        return None
    query_tokens = set(tokens(query))
    if not query_tokens:
        return None
    total = 0.0
    for context in contexts:
        context_tokens = set(tokens(context.get("text") or ""))
        total += sum(1 for token in query_tokens if token in context_tokens) / len(query_tokens)
    return total / len(contexts)


def rank_metrics(contexts: list[dict], qrel: dict | None) -> dict:
    empty = {"recall": None, "mrr": None, "ndcg": None}
    if not qrel or not contexts:
        return empty
    normalized = {nid(docid): rel for docid, rel in qrel.items()}
    rels = [normalized.get(nid(context.get("id") or ""), 0) or 0 for context in contexts]
    relevant = sum(1 for rel in qrel.values() if rel > 0)
    k = min(10, len(rels)) or 1
    found = sum(1 for rel in rels if rel > 0)
    recall = found / relevant if relevant else None
    first = next((index for index, rel in enumerate(rels) if rel > 0), -1)
    mrr = 1 / (first + 1) if first >= 0 else 0
    dcg = sum(1 / math.log2(index + 2) for index, rel in enumerate(rels[:k]) if rel > 0)
    ideal = min(relevant, k)
    idcg = sum(1 / math.log2(index + 2) for index in range(ideal)) if ideal else 0
    return {"recall": recall, "mrr": mrr, "ndcg": dcg / idcg if idcg else None}


def score_row(answer: str, contexts: list[dict], query: str, qrel: dict | None) -> dict:
    grounded = ground_lex(answer, contexts)
    ranks = rank_metrics(contexts, qrel)
    return {
        "ground": None if grounded is None else grounded["score"],
        "unsup": [] if grounded is None else grounded["unsup"],
        "cite": citation_cov(answer, contexts),
        "ctxOvl": ctx_overlap(query, contexts),
        **ranks,
    }
