import os
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from knowledge.billing import begin, finish
from knowledge.engines import ENGINES
from knowledge.store import (
    ENGINES as ENGINE_IDS,
    engine_dir,
    read_manifest,
    read_status,
    write_engine_status,
    write_manifest,
)

app = FastAPI()
_jobs: set[tuple[str, str]] = set()
_jobs_lock = threading.Lock()


class DocIn(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    text: str = ""


class IndexIn(BaseModel):
    engine: str
    clientId: str
    docs: list[DocIn] = Field(min_length=1, max_length=40)


class AskIn(BaseModel):
    engine: str
    clientId: str
    question: str = Field(min_length=1, max_length=2000)
    docId: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _engine(name: str):
    if name not in ENGINES:
        raise HTTPException(status_code=400, detail="engine must be a, b, or c")
    return ENGINES[name]


@app.get("/health")
def health():
    return {"ok": True, "openai": bool(os.environ.get("OPENAI_API_KEY"))}


@app.get("/api/knowledge/status")
def status(clientId: str):
    try:
        saved = read_status(clientId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    engines = {name: {**saved[name], "available": True} for name in ENGINE_IDS}
    return {"openai": bool(os.environ.get("OPENAI_API_KEY")), "engines": engines}


@app.post("/api/knowledge/index")
def index(body: IndexIn):
    _engine(body.engine)
    try:
        folder = engine_dir(body.clientId, body.engine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    docs = [doc.model_dump() for doc in body.docs if doc.text.strip()]
    if not docs:
        raise HTTPException(status_code=400, detail="No document text to index")
    key = (body.clientId, body.engine)
    with _jobs_lock:
        if key in _jobs:
            raise HTTPException(status_code=409, detail="This engine is already indexing")
        _jobs.add(key)
    write_manifest(folder, docs)
    write_engine_status(body.clientId, body.engine, state="indexing", error=None, updatedAt=_now(), docs=len(docs))
    threading.Thread(target=_run_index, args=(body.clientId, body.engine, folder, docs), daemon=True).start()
    return {"state": "indexing", "docs": len(docs)}


def _run_index(client_id: str, engine: str, folder, docs: list[dict]):
    try:
        result = ENGINES[engine].index(folder, docs)
        write_engine_status(
            client_id,
            engine,
            state="ready",
            error=None,
            updatedAt=_now(),
            docs=result.get("docs", len(docs)),
            truncated=result.get("truncated", 0),
            edges=result.get("edges"),
        )
    except Exception as exc:
        write_engine_status(client_id, engine, state="failed", error=str(exc), updatedAt=_now())
    finally:
        with _jobs_lock:
            _jobs.discard((client_id, engine))


@app.post("/api/knowledge/ask")
def ask(body: AskIn):
    _engine(body.engine)
    try:
        folder = engine_dir(body.clientId, body.engine)
        saved = read_status(body.clientId)[body.engine]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if saved["state"] == "indexing":
        raise HTTPException(status_code=409, detail="This engine is still indexing")
    if saved["state"] != "ready":
        raise HTTPException(status_code=409, detail="Index this engine before asking")
    sources = read_manifest(folder)
    if body.docId:
        sources = [item for item in sources if item["id"] == body.docId]
    begin()
    try:
        result = ENGINES[body.engine].ask(folder, body.question.strip(), body.docId)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"detail": str(exc), "usage": finish()})
    return {**result, "sources": sources, "usage": finish()}
