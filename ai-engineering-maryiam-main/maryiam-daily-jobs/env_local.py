"""Load the repo-root .env without overriding variables already set (Render injects those)."""

from __future__ import annotations

import os
from pathlib import Path

def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".env").is_file() or (parent / ".git").exists():
            return parent
    return here.parent


REPO_ROOT = _repo_root()
ENV_PATH = REPO_ROOT / ".env"


def load_env() -> None:
    if not ENV_PATH.is_file():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def google_credentials() -> tuple[str, str]:
    load_env()
    username = (os.environ.get("GOOGLE_USERNAME") or "").strip()
    password = os.environ.get("GOOGLE_PASSWORD") or ""
    return username, password
