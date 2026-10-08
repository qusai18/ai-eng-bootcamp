"""Small local corpus so the bench can run without the ClimbMix collection.

Nuggets follow AutoNuggetizer labels used by RAGDoll: vital facts the answer
must cover, and okay facts that still count in the non-strict "all" score.
"""

from __future__ import annotations

TOPICS: list[dict] = [
    {
        "id": "trec-2026-tasks",
        "title": "TREC RAG 2026 tasks",
        "question": "What does the TREC RAG 2026 track ask systems to do, and which corpus do they search?",
        "narrative": "Describe the 2026 tasks and the corpus that replaced MS MARCO.",
        "passages": [
            {
                "doc_id": "trec26-tasks",
                "text": (
                    "The TREC RAG 2026 track has two tasks. Retrieval asks for a ranked list of "
                    "ClimbMix documents that are relevant to a narrative and useful as evidence. "
                    "Retrieval-Augmented Generation asks the system to retrieve evidence from "
                    "ClimbMix and return a summarized answer grounded in that evidence."
                ),
            },
            {
                "doc_id": "trec26-corpus",
                "text": (
                    "ClimbMix-400b replaces MS MARCO v2.1 as the 2026 corpus. The collection is "
                    "served through the Pyserini REST API."
                ),
            },
        ],
        "nuggets": [
            {"text": "The track has a retrieval task and a retrieval-augmented generation task.", "importance": "vital"},
            {"text": "Answers must be grounded in retrieved ClimbMix evidence.", "importance": "vital"},
            {"text": "ClimbMix-400b replaces MS MARCO v2.1 for 2026.", "importance": "vital"},
            {"text": "ClimbMix is served through the Pyserini REST API.", "importance": "okay"},
        ],
    },
    {
        "id": "citation-support",
        "title": "Citation support scoring",
        "question": "How does RAGDoll score whether a citation supports an answer sentence?",
        "narrative": "Explain the support labels and the precision and recall metrics.",
        "passages": [
            {
                "doc_id": "support-labels",
                "text": (
                    "The support judge labels each statement against its cited passage as Full Support, "
                    "Partial Support, or No Support. RAGDoll stores those labels as 2, 1, and 0. "
                    "A missing or unparseable judgment is stored as -1 and is dropped from the denominator."
                ),
            },
            {
                "doc_id": "support-metrics",
                "text": (
                    "Weighted precision is the mean support of sentences that have citations. "
                    "Weighted recall divides the same support mass by every sentence, so an uncited "
                    "sentence scores zero and lowers recall. Full support counts as 1.0 and partial "
                    "support counts as 0.5. Hard precision and hard recall count only full support."
                ),
            },
        ],
        "nuggets": [
            {"text": "Labels are full support, partial support, and no support, stored as 2, 1, and 0.", "importance": "vital"},
            {"text": "Weighted precision averages support over sentences that cite something.", "importance": "vital"},
            {"text": "Weighted recall treats uncited sentences as unsupported.", "importance": "vital"},
            {"text": "Partial support counts as 0.5 in the weighted metrics.", "importance": "okay"},
        ],
    },
    {
        "id": "nuggets",
        "title": "Nugget coverage",
        "question": "What is a nugget, and how does RAGDoll turn nugget assignments into a coverage score?",
        "narrative": "Define nuggets and the strict versus non-strict coverage metrics.",
        "passages": [
            {
                "doc_id": "nugget-def",
                "text": (
                    "A nugget is an atomic fact the answer should cover. Each nugget is marked vital "
                    "or okay. Assignment labels are support, partial_support, and not_support."
                ),
            },
            {
                "doc_id": "nugget-score",
                "text": (
                    "Support counts as 1.0. Partial support counts as 0.5 only in the non-strict "
                    "metrics. Strict vital and strict all ignore partial support. Vital metrics use "
                    "only vital nuggets. The all metrics use every nugget."
                ),
            },
        ],
        "nuggets": [
            {"text": "A nugget is an atomic fact marked vital or okay.", "importance": "vital"},
            {"text": "Assignment labels are support, partial support, and not support.", "importance": "vital"},
            {"text": "Strict metrics ignore partial support.", "importance": "vital"},
            {"text": "Vital metrics use only vital nuggets.", "importance": "okay"},
        ],
    },
]


def topic_by_id(topic_id: str) -> dict | None:
    for topic in TOPICS:
        if topic["id"] == topic_id:
            return topic
    return None


def passage_text(topic: dict, doc_id: str) -> str | None:
    for passage in topic["passages"]:
        if passage["doc_id"] == doc_id:
            return passage["text"]
    return None
