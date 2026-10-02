import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

from chunking import GUIDE, STRATEGIES, chunk_documents

ROOT = Path(__file__).resolve().parent
_default_ratings = "/tmp/rag-qa-ratings.json" if os.name != "nt" else str(ROOT / "ratings.json")
RATINGS_PATH = Path(os.getenv("RATINGS_PATH", _default_ratings))
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env")

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 3
ANSWER_PROMPT = (
    "Answer the question using ONLY the context below. "
    "If the context doesn't contain the answer, say so.\n\n"
    "Context:\n{context}\n\n"
    "Question: {question}"
)


class Index:
    def __init__(self, chunks: list[str], vectors: np.ndarray) -> None:
        self.chunks = chunks
        self.vectors = vectors


class Store:
    def __init__(self) -> None:
        self.mode = "single"
        self.documents: list[tuple[str, str]] = []
        self.indexes: dict[str, Index] = {}
        self.ratings: list[dict[str, str | int]] = _load_ratings()


def _load_ratings() -> list[dict[str, str | int]]:
    if not RATINGS_PATH.exists():
        return []
    try:
        data = json.loads(RATINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return data


store = Store()


def _save_ratings() -> None:
    RATINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATINGS_PATH.write_text(json.dumps(store.ratings), encoding="utf-8")


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def _embed(texts: list[str]) -> np.ndarray:
    response = _client().embeddings.create(model=EMBED_MODEL, input=texts)
    ordered = sorted(response.data, key=lambda item: item.index)
    vectors = np.array([item.embedding for item in ordered], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return vectors / norms


def _require_strategy(strategy: str) -> str:
    if strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")
    return strategy


def ensure_index(strategy: str) -> Index:
    _require_strategy(strategy)
    if not store.documents:
        raise HTTPException(status_code=400, detail="Add a document before asking")
    cached = store.indexes.get(strategy)
    if cached is not None:
        return cached

    def embed_sentences(sentences: list[str]) -> np.ndarray:
        return _embed(sentences)

    try:
        chunks = chunk_documents(
            store.documents,
            strategy,
            store.mode,
            embed_sentences if strategy == "semantic" else None,
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not chunks:
        raise HTTPException(status_code=400, detail="That document produced no chunks")
    try:
        vectors = _embed(chunks)
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    index = Index(chunks, vectors)
    store.indexes[strategy] = index
    return index


def retrieve(question: str, strategy: str) -> list[str]:
    index = ensure_index(strategy)
    try:
        query = _embed([question])[0]
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    scores = index.vectors @ query
    order = np.argsort(scores)[::-1][:TOP_K]
    return [index.chunks[int(i)] for i in order]


def answer_question(question: str, strategy: str) -> tuple[str, list[str]]:
    sources = retrieve(question, strategy)
    prompt = ANSWER_PROMPT.format(context="\n\n".join(sources), question=question)
    try:
        completion = _client().chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return completion.choices[0].message.content or "", sources


def scoreboard() -> list[dict[str, str | float | int]]:
    totals: dict[str, list[int]] = {key: [] for key in STRATEGIES}
    for rating in store.ratings:
        strategy = str(rating["strategy"])
        if strategy in totals:
            totals[strategy].append(int(rating["score"]))
    rows = []
    for key, scores in totals.items():
        rows.append(
            {
                "strategy": key,
                "name": STRATEGIES[key]["name"],
                "ratings": len(scores),
                "average": round(sum(scores) / len(scores), 2) if scores else 0,
            }
        )
    return rows


def recommendation() -> dict[str, str | float | int | None]:
    rows = [row for row in scoreboard() if int(row["ratings"]) > 0]
    guide = GUIDE[store.mode]
    suggested = "document" if store.mode == "multiple" else "recursive"
    if not rows:
        return {
            "strategy": None,
            "name": None,
            "average": None,
            "ratings": 0,
            "guide_strategy": suggested,
            "guide_name": STRATEGIES[suggested]["name"],
            "reason": guide,
        }
    best = max(rows, key=lambda row: (float(row["average"]), int(row["ratings"])))
    return {
        "strategy": best["strategy"],
        "name": best["name"],
        "average": best["average"],
        "ratings": best["ratings"],
        "guide_strategy": suggested,
        "guide_name": STRATEGIES[suggested]["name"],
        "reason": (
            f"{best['name']} has the highest score from your ratings "
            f"({best['average']} / 5 across {best['ratings']} rating"
            f"{'' if best['ratings'] == 1 else 's'}). {guide}"
        ),
    }


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


class DocumentIn(BaseModel):
    name: str = Field(default="document", max_length=120)
    text: str = Field(min_length=1, max_length=20000)


class IngestRequest(BaseModel):
    mode: Literal["single", "multiple"]
    documents: list[DocumentIn] = Field(min_length=1, max_length=8)
    strategy: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    strategy: str


class CompareRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class RateRequest(BaseModel):
    strategy: str
    question: str = Field(min_length=1, max_length=2000)
    score: int = Field(ge=0, le=5)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    model: str
    strategy: str
    chunk_count: int


@app.get("/health")
def health() -> dict[str, str | int]:
    ready = store.indexes.get("recursive")
    return {"status": "ok", "chunks": 0 if ready is None else len(ready.chunks)}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/sample")
def sample() -> dict[str, str]:
    text = (ROOT / "sample_rag_document.txt").read_text(encoding="utf-8")
    return {"name": "sample_rag_document.txt", "text": text}


@app.get("/strategies")
def strategies() -> dict:
    return {
        "strategies": [
            {"id": key, **value, "suggested": key == ("document" if store.mode == "multiple" else "recursive")}
            for key, value in STRATEGIES.items()
        ],
        "mode": store.mode,
        "documents": [name for name, _text in store.documents],
        "scores": scoreboard(),
        "recommendation": recommendation(),
    }


@app.post("/documents")
def ingest(body: IngestRequest) -> dict:
    strategy = _require_strategy(body.strategy)
    if body.mode == "single" and len(body.documents) != 1:
        raise HTTPException(status_code=400, detail="Single-document mode accepts one document")
    store.mode = body.mode
    store.documents = [(item.name.strip() or "document", item.text.strip()) for item in body.documents]
    store.indexes.clear()
    index = ensure_index(strategy)
    return {
        "mode": store.mode,
        "strategy": strategy,
        "documents": [name for name, _text in store.documents],
        "chunk_count": len(index.chunks),
        "chunks": [chunk[:280] for chunk in index.chunks[:8]],
        "recommendation": recommendation(),
    }


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    strategy = _require_strategy(body.strategy)
    question = body.question.strip()
    answer, sources = answer_question(question, strategy)
    index = store.indexes[strategy]
    return AskResponse(
        answer=answer,
        sources=sources,
        model=CHAT_MODEL,
        strategy=strategy,
        chunk_count=len(index.chunks),
    )


@app.post("/compare")
def compare(body: CompareRequest) -> dict:
    question = body.question.strip()
    results = []
    for strategy in STRATEGIES:
        answer, sources = answer_question(question, strategy)
        results.append(
            {
                "strategy": strategy,
                "name": STRATEGIES[strategy]["name"],
                "answer": answer,
                "sources": sources,
                "chunk_count": len(store.indexes[strategy].chunks),
            }
        )
    return {"question": question, "results": results, "recommendation": recommendation()}


@app.post("/rate")
def rate(body: RateRequest) -> dict:
    strategy = _require_strategy(body.strategy)
    store.ratings.append(
        {"strategy": strategy, "question": body.question.strip(), "score": body.score}
    )
    _save_ratings()
    return {"scores": scoreboard(), "recommendation": recommendation()}
