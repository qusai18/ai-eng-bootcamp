import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
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


index: Index | None = None


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return vectors / norms


def build_index() -> Index:
    document = (ROOT / "sample_rag_document.txt").read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(document)
    if not chunks:
        raise RuntimeError("Sample document produced no chunks")

    response = _client().embeddings.create(model=EMBED_MODEL, input=chunks)
    ordered = sorted(response.data, key=lambda item: item.index)
    vectors = _normalize(np.array([item.embedding for item in ordered], dtype=np.float32))
    return Index(chunks, vectors)


def retrieve(question: str) -> list[str]:
    if index is None:
        raise HTTPException(status_code=503, detail="Index is not ready")
    response = _client().embeddings.create(model=EMBED_MODEL, input=question)
    query = np.array(response.data[0].embedding, dtype=np.float32)
    norm = np.linalg.norm(query)
    if norm:
        query = query / norm
    scores = index.vectors @ query
    order = np.argsort(scores)[::-1][:TOP_K]
    return [index.chunks[int(i)] for i in order]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global index
    index = build_index()
    yield


app = FastAPI(lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    model: str


@app.get("/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "chunks": 0 if index is None else len(index.chunks)}


@app.get("/")
def home() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    try:
        sources = retrieve(body.question.strip())
        prompt = ANSWER_PROMPT.format(
            context="\n\n".join(sources),
            question=body.question.strip(),
        )
        completion = _client().chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except HTTPException:
        raise
    except OpenAIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    answer = completion.choices[0].message.content or ""
    return AskResponse(answer=answer, sources=sources, model=CHAT_MODEL)
