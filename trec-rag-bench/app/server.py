"""Local bench that calls several RAG APIs and scores them with RAGDoll."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from corpus import TOPICS, topic_by_id
from scoring import compare, normalize_answer, score_system

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="TREC RAGDoll comparison bench")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Endpoint(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1)


class CompareRequest(BaseModel):
    endpoints: list[Endpoint] = Field(min_length=1, max_length=8)
    topic_ids: list[str] = Field(min_length=1)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/topics")
def list_topics() -> dict:
    return {
        "topics": [
            {
                "id": topic["id"],
                "title": topic["title"],
                "question": topic["question"],
                "nuggets": topic["nuggets"],
            }
            for topic in TOPICS
        ],
        "defaults": [
            {"name": "Grounded", "url": "/apps/grounded/query"},
            {"name": "Partial", "url": "/apps/partial/query"},
            {"name": "Fluent", "url": "/apps/fluent/query"},
        ],
        "judge": (
            "RAGDoll support_metric, cell_metric, pairwise_rows, and system_counts. "
            "Labels come from a local lexical judge that uses RAGDoll's 2/1/0 and "
            "support/partial_support/not_support scales. The official Pi model judge "
            "is not called."
        ),
    }


@app.post("/api/compare")
async def run_compare(body: CompareRequest, request: Request) -> dict:
    topics = []
    for topic_id in body.topic_ids:
        topic = topic_by_id(topic_id)
        if topic is None:
            raise HTTPException(status_code=400, detail=f"unknown topic {topic_id}")
        topics.append(topic)

    names = [endpoint.name.strip() for endpoint in body.endpoints]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="endpoint names must be unique")

    async with httpx.AsyncClient(timeout=20.0) as client:
        base = str(request.base_url).rstrip("/")
        calls = [
            _call_endpoint(client, endpoint, topic, base)
            for endpoint in body.endpoints
            for topic in topics
        ]
        calls_done = await asyncio.gather(*calls)

    results = []
    errors = []
    for endpoint, topic, payload, error in calls_done:
        if error:
            errors.append({"run_id": endpoint.name, "topic_id": topic["id"], "error": error})
            normalized = {"sentences": [], "raw": None}
        else:
            try:
                normalized = normalize_answer(payload, topic)
            except ValueError as exc:
                errors.append({"run_id": endpoint.name, "topic_id": topic["id"], "error": str(exc)})
                normalized = {"sentences": [], "raw": payload}
        scored = score_system(endpoint.name, topic, normalized)
        scored["error"] = error
        results.append(scored)

    report = compare(results)
    report["results"] = results
    report["errors"] = errors
    report["judge"] = "ragdoll-metrics + local lexical labels"
    return report


def _bundled_system(url: str) -> str | None:
    path = url.split("?", 1)[0]
    if path.startswith(("http://", "https://")):
        return None
    parts = path.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "apps" and parts[2] == "query":
        return parts[1]
    return None


async def _call_endpoint(client: httpx.AsyncClient, endpoint: Endpoint, topic: dict, base: str):
    body = {
        "topic_id": topic["id"],
        "question": topic["question"],
        "narrative": topic["narrative"],
    }
    bundled = _bundled_system(endpoint.url)
    if bundled:
        if bundled not in {"grounded", "partial", "fluent"}:
            return endpoint, topic, None, f"unknown bundled application {bundled}"
        return endpoint, topic, _mock_answer(bundled, topic), None
    url = endpoint.url if endpoint.url.startswith(("http://", "https://")) else f"{base}{endpoint.url}"
    try:
        response = await client.post(url, json=body)
        response.raise_for_status()
        return endpoint, topic, response.json(), None
    except httpx.HTTPError as exc:
        return endpoint, topic, None, str(exc)


@app.post("/apps/{system}/query")
def mock_app(system: str, body: dict) -> dict:
    """Three local applications with deliberately different answer quality."""
    topic = topic_by_id(str(body.get("topic_id") or ""))
    if topic is None:
        raise HTTPException(status_code=404, detail="mock apps only answer the bundled topics")
    if system not in {"grounded", "partial", "fluent"}:
        raise HTTPException(status_code=404, detail="unknown mock application")
    return _mock_answer(system, topic)


def _mock_answer(system: str, topic: dict) -> dict:
    passages = topic["passages"]
    if system == "grounded":
        return {
            "answer": [
                {"text": passages[0]["text"], "citations": [0]},
                {"text": passages[1]["text"], "citations": [1]},
            ],
            "references": [passage["doc_id"] for passage in passages],
        }
    if system == "partial":
        return {
            "answer": passages[0]["text"].split(". ")[0] + ".",
            "citations": [{"doc_id": passages[0]["doc_id"], "text": passages[0]["text"]}],
        }
    return {
        "answer": (
            "This system produces a fluent answer that does not use the retrieved evidence. "
            "MS MARCO v2.1 is still the only corpus, and answers are scored with BLEU against a single reference string."
        ),
        "citations": [],
    }
