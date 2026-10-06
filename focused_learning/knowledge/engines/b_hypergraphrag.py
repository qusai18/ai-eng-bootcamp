import csv
import io
import re
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from knowledge.engines.common import graph_of, source_header, text_of

VENDOR = Path(__file__).resolve().parents[1] / "vendor" / "HyperGraphRAG"
_RELATIONS = re.compile(r"-----Relationships-----\s*```csv\s*(.*?)```", re.S)


def _graph(detail: str) -> dict:
    match = _RELATIONS.search(detail or "")
    if not match:
        return {"nodes": [], "hyperedges": []}
    rows = csv.DictReader(io.StringIO(match.group(1).strip()))
    hyperedges = []
    for row in rows:
        members = []
        for part in (row.get("related_entities") or "").split("|"):
            name = part.strip().strip('"').replace("_", " ")
            if name:
                members.append(name)
        label = (row.get("hyperedge") or "relation").strip()
        if label and len(members) >= 2:
            hyperedges.append({"label": label, "members": members[:8]})
    return graph_of(hyperedges)


class HyperGraphRag:
    name = "HyperGraphRAG"

    def probe(self) -> None:
        if not VENDOR.exists():
            raise RuntimeError(f"HyperGraphRAG vendor is missing at {VENDOR}")

    def index(self, folder: Path, docs: list[dict]) -> dict:
        HyperGraphRAG, _QueryParam = self._import()
        work = folder / "work"
        if work.exists():
            shutil.rmtree(work)
        contexts = []
        truncated = 0
        for doc in docs:
            body, cut = text_of(doc)
            if not body:
                continue
            if cut:
                truncated += 1
            contexts.append(source_header(doc) + body)
        if not contexts:
            raise RuntimeError("No document text was available to index")
        rag = HyperGraphRAG(working_dir=str(work))
        rag.insert(contexts)
        return {"docs": len(contexts), "truncated": truncated}

    def ask(self, folder: Path, question: str, doc_id: str | None) -> dict:
        HyperGraphRAG, QueryParam = self._import()
        work = folder / "work"
        if not work.exists():
            raise RuntimeError("HyperGraphRAG index is missing")
        asked = question
        if doc_id:
            asked = f"Answer using only the document whose id is {doc_id}. {question}"
        rag = HyperGraphRAG(working_dir=str(work))
        answer = rag.query(asked, QueryParam(mode="hybrid", top_k=20))
        context = rag.query(asked, QueryParam(mode="hybrid", only_need_context=True, top_k=12))
        detail = context if isinstance(context, str) else str(context or "")
        grounding = []
        if detail.strip():
            grounding.append({
                "kind": "context",
                "label": "Retrieved hypergraph context",
                "detail": detail[:4000],
                "source": doc_id or "",
            })
        return {"answer": str(answer or ""), "grounding": grounding, "graph": _graph(detail)}

    def _import(self):
        root = str(VENDOR)
        if not VENDOR.exists():
            raise RuntimeError(f"HyperGraphRAG vendor is missing at {VENDOR}")
        if root not in sys.path:
            sys.path.insert(0, root)
        from hypergraphrag import HyperGraphRAG, QueryParam
        return HyperGraphRAG, QueryParam
