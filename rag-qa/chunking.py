"""Chunking strategies from the Weaviate RAG chunking guide.

https://weaviate.io/blog/chunking-strategies-for-rag
"""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

STRATEGIES: dict[str, dict[str, str]] = {
    "fixed": {
        "name": "Fixed-size",
        "complexity": "Low",
        "best_for": "Short notes, emails, and a quick baseline",
        "summary": "Splits on a fixed word count with about 20% overlap. Fast, and it can cut a sentence in half.",
    },
    "recursive": {
        "name": "Recursive",
        "complexity": "Medium",
        "best_for": "Articles and reports where paragraphs should stay intact",
        "summary": "Splits on paragraphs, then lines, then sentences, until each piece fits. A solid default for one document.",
    },
    "document": {
        "name": "Document-based",
        "complexity": "Low",
        "best_for": "Several short, standalone documents",
        "summary": "Keeps each document, or each Markdown section, as its own chunk instead of cutting by length.",
    },
    "semantic": {
        "name": "Semantic",
        "complexity": "Medium-High",
        "best_for": "Dense text whose topics change without clear headings",
        "summary": "Embeds each sentence and starts a new chunk where the meaning shifts.",
    },
    "hierarchical": {
        "name": "Hierarchical",
        "complexity": "Medium",
        "best_for": "Long structured documents with sections and details",
        "summary": "Stores a short section overview and smaller detail chunks underneath it.",
    },
    "adaptive": {
        "name": "Adaptive",
        "complexity": "High",
        "best_for": "Mixed pages that alternate dense lists and plain prose",
        "summary": "Uses smaller chunks for dense or list-heavy passages and larger chunks for plain prose.",
    },
}

GUIDE = {
    "single": "For one document, recursive chunking is the usual starting point. Semantic and hierarchical chunking help when the text is dense or clearly sectioned.",
    "multiple": "For several documents, document-based chunking keeps each file intact. Use it when every document is already a complete piece.",
}


def chunk_documents(
    documents: list[tuple[str, str]],
    strategy: str,
    mode: str,
    embed_sentences: Callable[[list[str]], np.ndarray] | None = None,
) -> list[str]:
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy}")

    chunks: list[str] = []
    for name, text in documents:
        pieces = _chunk_one(text, strategy, mode, embed_sentences)
        for piece in pieces:
            label = f"Source: {name}\n{piece.strip()}"
            if label.strip():
                chunks.append(label)
    return [chunk for chunk in chunks if chunk.strip()]


def _chunk_one(
    text: str,
    strategy: str,
    mode: str,
    embed_sentences: Callable[[list[str]], np.ndarray] | None,
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if strategy == "fixed":
        return _fixed(text)
    if strategy == "recursive":
        return _recursive(text, 500, 100)
    if strategy == "document":
        return _document(text, mode)
    if strategy == "semantic":
        if embed_sentences is None:
            raise ValueError("Semantic chunking needs an embedding function")
        return _semantic(text, embed_sentences)
    if strategy == "hierarchical":
        return _hierarchical(text)
    if strategy == "adaptive":
        return _adaptive(text)
    raise ValueError(strategy)


def _words(text: str) -> list[str]:
    return re.sub(r"\s+", " ", text).strip().split(" ")


def _fixed(text: str, chunk_words: int = 80, overlap_fraction: float = 0.2) -> list[str]:
    words = _words(text)
    if len(words) <= chunk_words:
        return [text.strip()]
    overlap = int(chunk_words * overlap_fraction)
    chunks: list[str] = []
    for start in range(0, len(words), chunk_words):
        window = words[max(start - overlap, 0) : start + chunk_words]
        if window:
            chunks.append(" ".join(window))
    return chunks


def _recursive(text: str, chunk_size: int, overlap: int) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [piece.strip() for piece in splitter.split_text(text) if piece.strip()]


def _markdown_sections(text: str) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^#{1,3}\s+\S", line) and any(part.strip() for part in current):
            sections.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if any(part.strip() for part in current):
        sections.append("\n".join(current).strip())
    return [section for section in sections if section]


def _document(text: str, mode: str) -> list[str]:
    sections = _markdown_sections(text)
    has_headers = len(sections) > 1 or bool(re.search(r"^#{1,3}\s+\S", text, re.M))
    if mode == "multiple" and len(text) <= 2000 and not has_headers:
        return [text]
    if has_headers and sections:
        chunks: list[str] = []
        for section in sections:
            if len(section) > 1200:
                chunks.extend(_recursive(section, 800, 80))
            else:
                chunks.append(section)
        return chunks
    if len(text) <= 2000:
        return [text]
    return _recursive(text, 800, 80)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    return [part.strip() for part in parts if part.strip()]


def _semantic(text: str, embed_sentences: Callable[[list[str]], np.ndarray]) -> list[str]:
    sentences = _sentences(text)
    if len(sentences) <= 2:
        return [text]
    vectors = embed_sentences(sentences)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vectors = vectors / norms
    sims = [float(vectors[i] @ vectors[i + 1]) for i in range(len(vectors) - 1)]
    threshold = float(np.percentile(sims, 30)) if sims else 0.5
    threshold = min(max(threshold, 0.35), 0.85)

    chunks: list[str] = []
    current = [sentences[0]]
    for index, sentence in enumerate(sentences[1:]):
        joined = " ".join(current)
        if sims[index] < threshold or len(joined) > 700:
            chunks.append(joined)
            current = [sentence]
        else:
            current.append(sentence)
    if current:
        chunks.append(" ".join(current))
    return chunks


def _hierarchical(text: str) -> list[str]:
    sections = _markdown_sections(text) or [text]
    chunks: list[str] = []
    for section in sections:
        title = section.splitlines()[0][:120]
        overview = section[:450].strip()
        chunks.append(f"[overview] {overview}")
        for detail in _recursive(section, 320, 40):
            if detail.strip() == overview:
                continue
            chunks.append(f"[detail] {title}\n{detail}")
    return chunks


def _density(paragraph: str) -> int:
    digits = sum(character.isdigit() for character in paragraph)
    markers = len(re.findall(r"(?m)^(\s*[-*]|\s*\d+\.)\s+", paragraph))
    return digits + markers * 6 + paragraph.count(",")


def _adaptive(text: str) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        return [text]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        dense = _density(paragraph) >= 8 or len(paragraph) > 500
        if dense:
            if buffer:
                chunks.append(buffer.strip())
                buffer = ""
            chunks.extend(_recursive(paragraph, 250, 40))
            continue
        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= 800:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer.strip())
            buffer = paragraph
    if buffer:
        chunks.append(buffer.strip())
    return chunks
