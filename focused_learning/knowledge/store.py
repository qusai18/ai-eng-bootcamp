import json
import re
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data"
ENGINES = ("a", "b", "c")
_LOCK = threading.Lock()
_CLIENT = re.compile(r"^[A-Za-z0-9-]{8,80}$")

EMPTY = {"state": "not_indexed", "docs": 0, "error": None, "updatedAt": None}


def check_client(client_id: str) -> str:
    if not client_id or not _CLIENT.match(client_id):
        raise ValueError("clientId must be 8-80 letters, numbers, or hyphens")
    return client_id


def client_dir(client_id: str) -> Path:
    path = ROOT / check_client(client_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def engine_dir(client_id: str, engine: str) -> Path:
    if engine not in ENGINES:
        raise ValueError("engine must be a, b, or c")
    path = client_dir(client_id) / engine
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_path(client_id: str) -> Path:
    return client_dir(client_id) / "status.json"


def read_status(client_id: str) -> dict:
    path = _status_path(client_id)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    return {engine: {**EMPTY, **(data.get(engine) or {})} for engine in ENGINES}


def write_engine_status(client_id: str, engine: str, **fields) -> dict:
    with _LOCK:
        current = read_status(client_id)
        current[engine] = {**current[engine], **fields}
        _status_path(client_id).write_text(json.dumps(current), encoding="utf-8")
        return current[engine]


def write_manifest(folder: Path, docs: list[dict]) -> None:
    manifest = [{"id": d["id"], "name": d["name"]} for d in docs]
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def read_manifest(folder: Path) -> list[dict]:
    path = folder / "manifest.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
