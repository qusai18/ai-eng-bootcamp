import json
import os
import re
from pathlib import Path

from knowledge.engines.common import text_of

_PARSER = None
_TOKEN = re.compile(r"[a-z0-9]{3,}")
_STOP = {
    "what", "which", "when", "where", "why", "how", "does", "did", "this", "that",
    "these", "those", "document", "documents", "describe", "described", "about",
    "from", "with", "into", "your", "have", "been", "are", "was", "were", "the",
    "and", "for", "not", "can", "you", "please",
}


class Hyperbase:
    name = "Hyperbase"

    def probe(self) -> None:
        self._parser()

    def index(self, folder: Path, docs: list[dict]) -> dict:
        parser = self._parser()
        rows = []
        truncated = 0
        for doc in docs:
            body, cut = text_of(doc, limit=30000)
            if not body:
                continue
            if cut:
                truncated += 1
            for result in parser.parse(body):
                sentence = (getattr(result, "text", None) or "").strip()
                edge = str(getattr(result, "edge", "") or "").strip()
                if not sentence or not edge:
                    continue
                rows.append({"docId": doc["id"], "name": doc["name"], "sentence": sentence, "edge": edge})
        if not rows:
            raise RuntimeError("Hyperbase did not produce any semantic hyperedges")
        (folder / "edges.json").write_text(json.dumps(rows), encoding="utf-8")
        return {"docs": len(docs), "edges": len(rows), "truncated": truncated}

    def ask(self, folder: Path, question: str, doc_id: str | None) -> dict:
        path = folder / "edges.json"
        if not path.exists():
            raise RuntimeError("Hyperbase index is missing")
        rows = json.loads(path.read_text(encoding="utf-8"))
        if doc_id:
            rows = [row for row in rows if row.get("docId") == doc_id]
        picked = _rank(rows, question)
        if not picked:
            return {
                "answer": "The indexed semantic hyperedges do not mention that.",
                "grounding": [],
            }
        from openai import OpenAI

        context = "\n\n".join(
            f"Document: {row['name']}\nSentence: {row['sentence']}\nSemantic hyperedge: {row['edge']}"
            for row in picked
        )
        reply = OpenAI().chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer only from the supplied sentences and semantic hyperedges. "
                        "If they do not contain the answer, say so."
                    ),
                },
                {"role": "user", "content": f"{context}\n\nQuestion: {question}"},
            ],
        )
        answer = reply.choices[0].message.content or ""
        grounding = [
            {
                "kind": "hyperedge",
                "label": row["edge"],
                "detail": row["sentence"],
                "source": row["name"],
            }
            for row in picked
        ]
        return {"answer": answer, "grounding": grounding}

    def _parser(self):
        global _PARSER
        if _PARSER is None:
            from hyperbase import get_parser
            _PARSER = get_parser("alphabeta", lang="en")
        return _PARSER


def _rank(rows: list[dict], question: str, limit: int = 8) -> list[dict]:
    wanted = set(_TOKEN.findall(question.lower())) - _STOP
    if not wanted:
        return rows[:limit]
    scored = []
    for row in rows:
        hay = f"{row.get('sentence', '')} {row.get('edge', '')}".lower()
        overlap = len(wanted & set(_TOKEN.findall(hay)))
        if overlap:
            scored.append((overlap, row))
    if not scored:
        return rows[:limit]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in scored[:limit]]
