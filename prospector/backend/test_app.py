import httpx
import pytest
from fastapi.testclient import TestClient

import app as api


class Scripted:
    responses = []
    seen = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, headers=None):
        Scripted.seen.append({"url": url, "params": params, "headers": headers})
        return Scripted.responses.pop(0)


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    api.clear_cache()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    Scripted.responses = []
    Scripted.seen = []
    yield
    api.clear_cache()


def test_health_hides_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    body = TestClient(api.app).get("/health").json()
    assert body == {"ok": True, "token": True}
    assert "ghp_secret" not in str(body)


def test_readme_rejects_nested_segment():
    response = TestClient(api.app).get("/api/readme/a..b/repo")
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid"


def test_search_caches_and_sends_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    monkeypatch.setattr(api.httpx, "AsyncClient", Scripted)
    Scripted.responses = [
        httpx.Response(
            200,
            json={"items": [{"full_name": "a/b"}], "total_count": 1},
            headers={"x-ratelimit-remaining": "9", "x-ratelimit-limit": "10", "x-ratelimit-reset": "100"},
        )
    ]
    client = TestClient(api.app)
    first = client.get("/api/search", params={"q": "ripgrep", "per_page": 5})
    second = client.get("/api/search", params={"q": "ripgrep", "per_page": 5})
    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["items"][0]["full_name"] == "a/b"
    assert second.json()["cached"] is True
    assert len(Scripted.seen) == 1
    assert Scripted.seen[0]["headers"]["Authorization"] == "Bearer ghp_secret"
    assert "ghp_secret" not in first.text.replace("Bearer ghp_secret", "")


def test_rate_limit_includes_reset(monkeypatch):
    monkeypatch.setattr(api.httpx, "AsyncClient", Scripted)
    Scripted.responses = [
        httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"x-ratelimit-reset": "1700000000"},
        ),
        httpx.Response(
            403,
            json={"message": "API rate limit exceeded"},
            headers={"x-ratelimit-reset": "1700000000"},
        ),
    ]
    response = TestClient(api.app).get("/api/search", params={"q": "x"})
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "error": "rate_limit",
        "message": "API rate limit exceeded",
        "reset": 1700000000,
    }


def test_invalid_query_surfaces_github_message(monkeypatch):
    monkeypatch.setattr(api.httpx, "AsyncClient", Scripted)
    Scripted.responses = [
        httpx.Response(422, json={"message": "Validation Failed", "errors": [{"message": "The listed users and repositories cannot be searched either because the resources do not exist or you do not have permission to view them."}]}),
    ]
    response = TestClient(api.app).get("/api/search", params={"q": "org:missing"})
    assert response.status_code == 422
    assert "cannot be searched" in response.json()["detail"]["message"]


def test_server_error_is_retried_once(monkeypatch):
    monkeypatch.setattr(api.httpx, "AsyncClient", Scripted)
    Scripted.responses = [
        httpx.Response(502, text="bad gateway"),
        httpx.Response(
            200,
            json={"resources": {"search": {"remaining": 8, "limit": 10}, "core": {"remaining": 40, "limit": 60}}},
        ),
    ]
    response = TestClient(api.app).get("/api/rate-limit")
    assert response.status_code == 200
    assert response.json()["search"]["remaining"] == 8
    assert len(Scripted.seen) == 2
