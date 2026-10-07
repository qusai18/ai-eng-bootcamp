import os
import re
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

def _load_dotenv() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

GITHUB = "https://api.github.com"
TIMEOUT = httpx.Timeout(12.0)
CACHE_TTL = float(os.environ.get("CACHE_TTL", "60"))
SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
SORTS = {"best", "stars", "updated"}

app = FastAPI(title="GitBytes")
_cache: dict[str, tuple[float, dict]] = {}


class GithubError(Exception):
    def __init__(self, status: int, detail: dict):
        self.status = status
        self.detail = detail


def clear_cache() -> None:
    _cache.clear()


def _headers(accept: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": accept or "application/vnd.github+json",
        "User-Agent": "GitBytes",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _cache_get(key: str):
    hit = _cache.get(key)
    if not hit:
        return None
    expires, value = hit
    if time.time() > expires:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time() + CACHE_TTL, value)


def _detail(response: httpx.Response) -> dict:
    message = "GitHub request failed"
    try:
        body = response.json()
        message = body.get("message") or message
        errors = body.get("errors") or []
        extra = [item.get("message") for item in errors if isinstance(item, dict) and item.get("message")]
        if extra:
            message = message + ": " + "; ".join(extra)
    except Exception:
        text = response.text.strip()
        if text:
            message = text[:300]
    return message


def valid_segment(value: str) -> bool:
    return bool(SEGMENT.fullmatch(value)) and ".." not in value


async def fetch_github(path: str, params: dict | None = None, accept: str | None = None) -> httpx.Response:
    response = None
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(GITHUB + path, params=params, headers=_headers(accept))
        except httpx.TimeoutException as exc:
            raise GithubError(504, {"error": "timeout", "message": "GitHub timed out"}) from exc
        except httpx.HTTPError as exc:
            raise GithubError(502, {"error": "network", "message": "GitHub request failed"}) from exc
        if response.status_code >= 500 and attempt == 0:
            continue
        return response
    return response


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in (403, 429):
        reset = response.headers.get("x-ratelimit-reset")
        raise GithubError(
            response.status_code,
            {
                "error": "rate_limit",
                "message": _detail(response),
                "reset": int(reset) if reset and reset.isdigit() else None,
            },
        )
    if response.status_code == 422:
        raise GithubError(422, {"error": "invalid", "message": _detail(response)})
    if response.status_code >= 400:
        raise GithubError(response.status_code, {"error": "github", "message": _detail(response)})


def _rate(response: httpx.Response) -> dict:
    return {
        "remaining": response.headers.get("x-ratelimit-remaining"),
        "limit": response.headers.get("x-ratelimit-limit"),
        "reset": response.headers.get("x-ratelimit-reset"),
    }


@app.get("/health")
def health():
    return {"ok": True, "token": bool(os.environ.get("GITHUB_TOKEN", "").strip())}


@app.get("/api/rate-limit")
async def rate_limit():
    try:
        response = await fetch_github("/rate_limit")
        _raise_for_status(response)
    except GithubError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    data = response.json()
    return {"search": data["resources"]["search"], "core": data["resources"]["core"]}


@app.get("/api/search")
async def search(
    q: str = Query(min_length=1, max_length=256),
    sort: str = "best",
    per_page: int = Query(10, ge=1, le=30),
):
    if sort not in SORTS:
        raise HTTPException(status_code=400, detail={"error": "invalid", "message": "sort must be best, stars, or updated"})
    key = f"search\0{q}\0{sort}\0{per_page}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    params = {"q": q, "per_page": per_page}
    if sort != "best":
        params["sort"] = sort
    try:
        response = await fetch_github("/search/repositories", params=params)
        _raise_for_status(response)
    except GithubError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    body = response.json()
    payload = {
        "items": body.get("items") or [],
        "total": body.get("total_count") or 0,
        "rate": _rate(response),
        "cached": False,
    }
    stored = {**payload, "cached": True}
    _cache_set(key, stored)
    return payload


@app.get("/api/readme/{owner}/{repo}")
async def readme(owner: str, repo: str):
    if not valid_segment(owner) or not valid_segment(repo):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid", "message": "owner and repo must be a single path segment"},
        )
    key = f"readme\0{owner}\0{repo}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        response = await fetch_github(f"/repos/{owner}/{repo}/readme", accept="application/vnd.github.raw")
        _raise_for_status(response)
    except GithubError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
    payload = {"text": response.text, "rate": _rate(response), "cached": False}
    _cache_set(key, {**payload, "cached": True})
    return payload


_static = Path(__file__).resolve().parent.parent / "frontend"
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
