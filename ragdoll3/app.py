"""RAGDoll3 — compare live RAG endpoints and add Autonoma and BenchmarkQED columns.

    python -m uvicorn app:app --host 0.0.0.0 --port 8773
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from scoring.answers import chat_url, claude_url, pick_answer, pick_contexts
from scoring.autonoma import score_autonoma
from scoring.benchmark_qed import score_benchmark_qed
from scoring.judge import JUDGE_SYS, judge_prompt, parse_judge
from scoring.lexical import score_row

PORT = int(os.environ.get("PORT", "8773"))
STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="RAGDoll3")

SPECIAL = {
    "how many players are on a soccer team on the field at one time": {
        "grounded": {
            "answer": "Eleven players are on the field at one time.",
            "contexts": [
                {"id": "kilt-123", "text": "A soccer team fields eleven players at one time."},
                {"id": "kilt-124", "text": "Substitutes wait off the field and do not count among the eleven."},
            ],
        },
        "partial": {
            "answer": "A team uses several athletes, and the exact count depends on the league.",
            "contexts": [
                {"id": "kilt-900", "text": "Spectator rules vary by stadium and have nothing to do with the lineup."}
            ],
        },
    },
    "what causes the northern lights to occur": {
        "grounded": {
            "answer": "Charged particles from the sun collide with gases in Earth's atmosphere.",
            "contexts": [
                {
                    "id": "kilt-201",
                    "text": "The northern lights occur when charged particles from the sun strike gases in the atmosphere.",
                }
            ],
        },
        "partial": {
            "answer": "The lights are a weather phenomenon near the poles.",
            "contexts": [{"id": "kilt-901", "text": "Polar climates are cold for much of the year."}],
        },
    },
}


class Doll(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    type: str = "rag"
    url: str = Field(min_length=1, max_length=500)
    key: str = ""
    model: str = ""
    color: str = "#0785f2"


class Topic(BaseModel):
    qid: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=1, max_length=2000)


class Qrel(BaseModel):
    qid: str
    docid: str
    rel: int = 1


class Reference(BaseModel):
    qid: str
    reference: str = ""


class Scorers(BaseModel):
    judge_id: str | None = None
    ragas: bool = False
    deepeval: bool = False
    pairwise: bool = False
    reference: bool = False
    trials: int = 2
    judge_key: str = ""
    judge_model: str = "gpt-4o-mini"


class EvaluateRequest(BaseModel):
    dolls: list[Doll] = Field(min_length=1, max_length=10)
    topics: list[Topic] = Field(min_length=1, max_length=300)
    qrels: list[Qrel] = []
    references: list[Reference] = []
    k: int = 5
    max_tokens: int = 400
    timeout_ms: int = 60000
    conc: int = 3
    scorers: Scorers = Field(default_factory=Scorers)


class PingRequest(BaseModel):
    doll: Doll
    k: int = 5
    max_tokens: int = 400
    timeout_ms: int = 60000


def _qrel_map(qrels: list[Qrel]) -> dict[str, dict[str, int]]:
    mapped: dict[str, dict[str, int]] = {}
    for item in qrels:
        mapped.setdefault(item.qid, {})[item.docid] = item.rel
        mapped.setdefault(item.qid.lower(), {})[item.docid] = item.rel
    return mapped


def _reference_map(references: list[Reference]) -> dict[str, str]:
    mapped = {}
    for item in references:
        text = item.reference.strip()
        if text:
            mapped[item.qid] = text
    return mapped


def stub_payload(name: str, query: str) -> dict:
    special = SPECIAL.get(query.strip().lower(), {}).get(name)
    if special:
        return special
    if name == "grounded":
        return {
            "answer": f"The retrieved note answers this directly: {query.rstrip('?')}.",
            "contexts": [
                {"id": "doc-grounded", "text": f"{query} This passage states the fact directly."}
            ],
        }
    return {
        "answer": "This system answers fluently without using the retrieved evidence.",
        "contexts": [
            {"id": "doc-unrelated", "text": "Unrelated passage about ocean tides and shipping lanes."}
        ],
    }


def _stub_name(url: str) -> str | None:
    path = urlparse(url).path or url
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "stubs" and parts[-1] == "query":
        return parts[1]
    return None


async def call_doll(client: httpx.AsyncClient, doll: Doll, query: str, k: int, max_tokens: int, timeout_ms: int):
    started = time.perf_counter()
    stub = _stub_name(doll.url)
    if stub:
        if stub not in {"grounded", "partial"}:
            raise RuntimeError(f"unknown stub {stub}")
        payload = stub_payload(stub, query)
        return {
            "answer": pick_answer(payload).strip(),
            "contexts": pick_contexts(payload) if doll.type in {"rag", "custom"} else [],
            "tokens": 0,
            "latency": (time.perf_counter() - started) * 1000,
        }

    headers = {"Content-Type": "application/json"}
    if doll.type == "claude":
        url = claude_url(doll.url)
        if doll.key:
            headers["x-api-key"] = doll.key
        headers["anthropic-version"] = "2023-06-01"
        body = {
            "model": doll.model or "claude-sonnet-4-5",
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": query}],
        }
    elif doll.type == "openai":
        url = chat_url(doll.url)
        if doll.key:
            headers["Authorization"] = "Bearer " + doll.key
        body = {
            "model": doll.model or "gpt-4o-mini",
            "messages": [{"role": "user", "content": query}],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
    else:
        url = doll.url
        if doll.key:
            headers["Authorization"] = "Bearer " + doll.key
        body = {"query": query, "top_k": k}
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("doll URL must be http(s) or a /stubs path")
    try:
        response = await client.post(url, headers=headers, json=body, timeout=timeout_ms / 1000)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"timeout after {timeout_ms}ms") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(str(exc)[:180]) from exc
    answer = pick_answer(data).strip()
    contexts = pick_contexts(data) if doll.type in {"rag", "custom"} else []
    usage = data.get("usage") if isinstance(data, dict) else {}
    usage = usage or {}
    tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0) + int(
        usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    )
    return {
        "answer": answer,
        "contexts": contexts,
        "tokens": tokens,
        "latency": (time.perf_counter() - started) * 1000,
    }


async def judge_doll(client: httpx.AsyncClient, doll: Doll, question: str, contexts: list[dict], answer: str):
    prompt = judge_prompt(question, contexts, answer)
    if doll.type not in {"openai", "claude"}:
        result = await call_doll(client, doll, JUDGE_SYS + "\n\n" + prompt, 5, 300, 45000)
        parsed = parse_judge(result["answer"])
        if not parsed:
            raise RuntimeError("judge returned unparseable output")
        return parsed
    headers = {"Content-Type": "application/json"}
    if doll.type == "claude":
        url = claude_url(doll.url)
        if doll.key:
            headers["x-api-key"] = doll.key
        headers["anthropic-version"] = "2023-06-01"
        body = {
            "model": doll.model or "claude-sonnet-4-5",
            "max_tokens": 300,
            "temperature": 0,
            "system": JUDGE_SYS,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        url = chat_url(doll.url)
        if doll.key:
            headers["Authorization"] = "Bearer " + doll.key
        body = {
            "model": doll.model or "gpt-4o-mini",
            "temperature": 0,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": JUDGE_SYS},
                {"role": "user", "content": prompt},
            ],
        }
    response = await client.post(url, headers=headers, json=body, timeout=45)
    response.raise_for_status()
    parsed = parse_judge(pick_answer(response.json()))
    if not parsed:
        raise RuntimeError("judge returned unparseable output")
    return parsed


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/stubs/{name}/query")
def stub_query(name: str, body: dict) -> dict:
    if name not in {"grounded", "partial"}:
        raise HTTPException(status_code=404, detail="unknown stub")
    return stub_payload(name, str(body.get("query") or ""))


@app.post("/api/ping")
async def ping(body: PingRequest) -> dict:
    query = "ping" if body.doll.type in {"rag", "custom"} else "Reply with the single word: pong"
    async with httpx.AsyncClient() as client:
        try:
            result = await call_doll(client, body.doll, query, body.k, body.max_tokens, body.timeout_ms)
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:180]}
    if not result["answer"] and not result["tokens"]:
        return {"ok": False, "error": "empty response"}
    return {"ok": True, "latency_ms": result["latency"]}


@app.post("/api/evaluate")
async def evaluate(body: EvaluateRequest) -> StreamingResponse:
    names = [doll.name.strip() for doll in body.dolls]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="doll names must be unique")
    qrels = _qrel_map(body.qrels)
    references = _reference_map(body.references)

    async def events():
        logs: list[str] = []

        def emit(kind: str, **payload):
            if kind == "log":
                logs.append(payload["text"])
            return json.dumps({"type": kind, **payload}) + "\n"

        rows: dict[str, list[dict | None]] = {doll.id: [None] * len(body.topics) for doll in body.dolls}
        judge = next((doll for doll in body.dolls if doll.id == body.scorers.judge_id), None)
        total = len(body.dolls) * len(body.topics)
        yield emit(
            "log",
            text=(
                f"run started · {len(body.dolls)} dolls × {len(body.topics)} topics = {total} tasks"
                f" · K={body.k}"
                + (f" · judge: {judge.name}" if judge else " · no 1–5 judge")
            ),
        )
        semaphore = asyncio.Semaphore(max(1, min(body.conc, 6)))
        done = 0
        errors = 0

        async with httpx.AsyncClient() as client:

            async def one(doll: Doll, index: int, topic: Topic):
                nonlocal done, errors
                row = {
                    "qid": topic.qid,
                    "query": topic.query,
                    "answer": "",
                    "contexts": [],
                    "latency": 0,
                    "tokens": 0,
                    "error": None,
                    "judge": None,
                    "judgeErr": None,
                    "local": {},
                }
                async with semaphore:
                    try:
                        result = await call_doll(
                            client, doll, topic.query, body.k, body.max_tokens, body.timeout_ms
                        )
                        row.update(result)
                    except Exception as exc:
                        row["error"] = str(exc)[:180]
                if not row["error"]:
                    qrel = qrels.get(topic.qid) or qrels.get(topic.qid.lower())
                    row["local"] = score_row(row["answer"], row["contexts"], topic.query, qrel)
                    if row["answer"] and judge:
                        try:
                            row["judge"] = await judge_doll(
                                client, judge, topic.query, row["contexts"], row["answer"]
                            )
                        except Exception as exc:
                            row["judgeErr"] = str(exc)[:180]
                rows[doll.id][index] = row
                done += 1
                if row["error"]:
                    errors += 1
                tag = row["error"] or f"{round(row['latency'])}ms"
                yield_text = f"{doll.name} · {topic.qid} · {tag}"
                return index, doll.id, row, yield_text

            tasks = [
                asyncio.create_task(one(doll, index, topic))
                for doll in body.dolls
                for index, topic in enumerate(body.topics)
            ]
            for finished in asyncio.as_completed(tasks):
                index, doll_id, row, text = await finished
                yield emit("log", text=text)
                yield emit("row", doll_id=doll_id, index=index, row=row, done=done, total=total, errs=errors)

        library = body.scorers.ragas or body.scorers.deepeval or body.scorers.pairwise or body.scorers.reference
        judge_key = body.scorers.judge_key.strip() or os.environ.get("OPENAI_API_KEY", "").strip()
        if library and not judge_key:
            yield emit(
                "log",
                text="OpenAI judge key missing. Ragas, DeepEval, and BenchmarkQED columns were left blank.",
            )
        elif library:
            material = {doll_id: [row for row in doll_rows if row] for doll_id, doll_rows in rows.items()}
            names_by_id = {doll.id: doll.name for doll in body.dolls}
            scorers = body.scorers.model_copy(update={"judge_key": judge_key})
            source = "the key in this request" if body.scorers.judge_key.strip() else "the server OpenAI key"
            yield emit("log", text=f"scoring Ragas, DeepEval, and BenchmarkQED with {source}")
            notes = await asyncio.to_thread(
                _score_libraries,
                material,
                names_by_id,
                references,
                scorers,
            )
            for note in notes:
                yield emit("log", text=note)
            for doll_id, doll_rows in material.items():
                for index, row in enumerate(doll_rows):
                    yield emit("row", doll_id=doll_id, index=index, row=row, done=done, total=total, errs=errors)

        yield emit(
            "done",
            run={
                "ts": int(time.time() * 1000),
                "k": body.k,
                "judge": {"id": judge.id, "name": judge.name, "color": judge.color} if judge else None,
                "scorers": {
                    "ragas": body.scorers.ragas,
                    "deepeval": body.scorers.deepeval,
                    "pairwise": body.scorers.pairwise,
                    "reference": body.scorers.reference,
                    "trials": body.scorers.trials,
                },
                "eps": [{"id": doll.id, "name": doll.name, "color": doll.color} for doll in body.dolls],
                "topics": [{"qid": topic.qid, "query": topic.query} for topic in body.topics],
                "rows": rows,
                "done": done,
                "total": total,
                "errs": errors,
                "aborted": False,
                "logs": logs,
            },
        )

    return StreamingResponse(events(), media_type="application/x-ndjson")


def _score_libraries(rows, names, references, scorers: Scorers) -> list[str]:
    notes = score_autonoma(
        rows,
        references,
        scorers.judge_key.strip(),
        scorers.judge_model.strip() or "gpt-4o-mini",
        ragas=scorers.ragas,
        deepeval=scorers.deepeval,
    )
    notes.extend(
        score_benchmark_qed(
            rows,
            names,
            references,
            scorers.judge_key.strip(),
            scorers.judge_model.strip() or "gpt-4o-mini",
            scorers.trials,
            pairwise=scorers.pairwise,
            reference=scorers.reference,
        )
    )
    return notes
