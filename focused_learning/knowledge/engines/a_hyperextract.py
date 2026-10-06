import os
import shutil
from pathlib import Path

from knowledge.engines.common import as_data, call_with, source_header, text_of

TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "architecture_hypergraph.yaml"


def _clients():
    from hyperextract import create_client

    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return create_client(llm="openai", embedder="openai:text-embedding-3-small", api_key=key)


class HyperExtract:
    name = "Hyper-Extract"

    def probe(self) -> None:
        import hyperextract  # noqa: F401

    def index(self, folder: Path, docs: list[dict]) -> dict:
        from hyperextract import Template

        store = folder / "store"
        if store.exists():
            shutil.rmtree(store)
        store.mkdir(parents=True)

        llm, embedder = _clients()
        ka = Template.create(str(TEMPLATE), "en", llm_client=llm, embedder=embedder)
        truncated = 0
        ingested = 0
        for doc in docs:
            body, cut = text_of(doc)
            if not body:
                continue
            if cut:
                truncated += 1
            text = source_header(doc) + body
            ka = ka.feed_text(text, source_id=doc["id"])
            ingested += 1
        if not ingested:
            raise RuntimeError("No document text was available to index")
        ka.build_index()
        ka.dump(str(store))
        return {"docs": ingested, "truncated": truncated}

    def ask(self, folder: Path, question: str, doc_id: str | None) -> dict:
        from hyperextract import Template

        store = folder / "store"
        if not store.exists():
            raise RuntimeError("Hyper-Extract index is missing")
        llm, embedder = _clients()
        ka = Template.create(str(TEMPLATE), "en", llm_client=llm, embedder=embedder)
        ka.load(str(store))
        scope = {"source_ids": [doc_id], "tags": [doc_id]} if doc_id else {}
        found = call_with(ka.search, question, top_k=6, **scope)
        nodes, edges = _split_search(found)
        reply = call_with(ka.chat, question, top_k=8, **scope)
        answer = getattr(reply, "content", None) or str(reply)
        grounding = [_node_card(item) for item in nodes] + [_edge_card(item) for item in edges]
        return {"answer": answer, "grounding": grounding}


def _split_search(found):
    if isinstance(found, tuple) and len(found) == 2:
        nodes, edges = found
        return list(nodes or []), list(edges or [])
    if isinstance(found, dict):
        return list(found.get("nodes") or found.get("entities") or []), list(
            found.get("edges") or found.get("relations") or []
        )
    if isinstance(found, list):
        return found, []
    return [], []


def _field(data: dict, *names: str) -> str:
    for name in names:
        value = data.get(name)
        if value:
            if isinstance(value, list):
                return ", ".join(str(item) for item in value)
            return str(value)
    return ""


def _node_card(item) -> dict:
    data = as_data(item)
    if not isinstance(data, dict):
        return {"kind": "node", "label": str(data), "detail": "", "source": ""}
    return {
        "kind": "node",
        "label": _field(data, "name", "entity_name") or "Concept",
        "detail": _field(data, "description", "type"),
        "source": _field(data, "source", "source_id"),
    }


def _edge_card(item) -> dict:
    data = as_data(item)
    if not isinstance(data, dict):
        return {"kind": "edge", "label": str(data), "detail": "", "source": ""}
    participants = _field(data, "participants", "members")
    detail = _field(data, "description")
    if participants:
        detail = (participants + (" — " + detail if detail else "")).strip(" —")
    return {
        "kind": "edge",
        "label": _field(data, "name", "type") or "Hyperedge",
        "detail": detail,
        "source": _field(data, "source", "source_id"),
    }
