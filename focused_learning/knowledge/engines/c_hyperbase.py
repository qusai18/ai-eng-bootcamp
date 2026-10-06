import json
import os
import re
import sys
import types
from pathlib import Path

from knowledge.engines.common import graph_of, text_of

_PARSER = None
_TOKEN = re.compile(r"[a-z0-9]{3,}")
_STOP = {
    "what", "which", "when", "where", "why", "how", "does", "did", "this", "that",
    "these", "those", "document", "documents", "describe", "described", "about",
    "from", "with", "into", "your", "have", "been", "are", "was", "were", "the",
    "and", "for", "not", "can", "you", "please",
}


def _use_light_atomizer() -> None:
    """Keep AlphaBeta on spaCy rules without the PyTorch atom classifier.

    The published atomizer imports torch and a Hugging Face model. Loading that
    next to Node exceeds the 512 MB instance and the kernel stops the service.
    Verbs are still marked as predicates by the parser after this tagger runs.
    """
    name = "hyperbase_parser_ab.atomizer"
    if getattr(sys.modules.get(name), "_focused_light", False):
        return

    module = types.ModuleType(name)
    module._focused_light = True

    class Atomizer:
        def __init__(self, model_path: str | None = None) -> None:
            self.model_path = model_path or ""

        def atomize(self, sentence: str, tokens: list[str] | None = None) -> list[tuple[str, str]]:
            words = tokens if tokens is not None else sentence.split()
            return [(word, "C") for word in words]

    module.Atomizer = Atomizer
    sys.modules[name] = module


class Hyperbase:
    name = "Hyperbase"

    def probe(self) -> None:
        import spacy

        if not spacy.util.is_package("en_core_web_sm"):
            raise RuntimeError("spaCy model en_core_web_sm is not installed")

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
                "graph": {"nodes": [], "hyperedges": []},
            }
        from openai import OpenAI

        context = "\n\n".join(
            f"Document: {row['name']}\nSentence: {row['sentence']}\nSemantic hyperedge: {row['edge']}"
            for row in picked
        )
        graph = _graph(picked)
        grounding = [
            {
                "kind": "hyperedge",
                "label": row["edge"],
                "detail": row["sentence"],
                "source": row["name"],
            }
            for row in picked
        ]
        try:
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
        except Exception as exc:
            answer = "The language model could not complete an answer. The hypergraph is the evidence that was retrieved.\n\n" + str(exc)
        return {"answer": answer, "grounding": grounding, "graph": graph}

    def _parser(self):
        global _PARSER
        if _PARSER is None:
            _use_light_atomizer()
            from hyperbase import get_parser
            _PARSER = get_parser("alphabeta", lang="en")
        return _PARSER


_SKIP = {"the", "a", "an", "from", "to", "of", "and", "or", "in", "on", "for", "with"}


def _graph(rows: list[dict]) -> dict:
    hyperedges = []
    for row in rows:
        found = _hyperedges(row.get("edge") or "")
        if not found:
            members: list[str] = []
            tokens = _tokenize(row.get("edge") or "")
            if tokens:
                _concepts(_parse(tokens), members)
            unique = []
            for member in members:
                if member not in unique:
                    unique.append(member)
            sentence = " ".join((row.get("sentence") or "").split())
            if len(unique) >= 2:
                found = [{"label": sentence[:90] or unique[0], "members": unique}]
        hyperedges.extend(found)
    return graph_of(hyperedges)


def _tokenize(src: str) -> list[str]:
    tokens = []
    i = 0
    while i < len(src):
        if src[i].isspace():
            i += 1
            continue
        if src[i] in "()":
            tokens.append(src[i])
            i += 1
            continue
        j = i
        while j < len(src) and not src[j].isspace() and src[j] not in "()":
            j += 1
        tokens.append(src[i:j])
        i = j
    return tokens


def _parse(tokens: list[str]):
    def read(index: int):
        if index >= len(tokens):
            return "", index
        if tokens[index] != "(":
            return tokens[index], index + 1
        index += 1
        items = []
        while index < len(tokens) and tokens[index] != ")":
            node, index = read(index)
            items.append(node)
        return items, index + 1

    tree, _index = read(0)
    return tree


def _atom(token: str):
    if not isinstance(token, str) or "/" not in token:
        return None
    word, kind = token.split("/", 1)
    if not kind or kind[0] not in "CPMB#":
        return None
    word = word.replace("%2e", "").strip("?+.").strip()
    return word, kind


def _concept_word(token: str):
    atom = _atom(token) if isinstance(token, str) else None
    if not atom or not atom[0] or not atom[1].startswith("C") or atom[1].startswith("Cd") or atom[0].lower() in _SKIP:
        return None
    return atom[0]


def _concepts(tree, found: list[str]) -> None:
    word = _concept_word(tree) if isinstance(tree, str) else None
    if word:
        found.append(word)
        return
    if not isinstance(tree, list) or not tree:
        return
    head = _atom(tree[0]) if isinstance(tree[0], str) else None
    if head and head[1].startswith("B"):
        words = []
        grouped = True
        for child in tree[1:]:
            if isinstance(child, str):
                word = _concept_word(child)
                if word:
                    words.append(word)
                elif _atom(child) and _atom(child)[1].startswith("Cd"):
                    continue
                else:
                    grouped = False
                    break
            else:
                grouped = False
                break
        if grouped and len(words) >= 2:
            found.append(" ".join(words))
            return
    for child in tree:
        _concepts(child, found)


def _walk(tree, found: list[dict]) -> None:
    if not isinstance(tree, list) or not tree:
        return
    atom = _atom(tree[0]) if isinstance(tree[0], str) else None
    if atom and atom[1].startswith("P"):
        members: list[str] = []
        _concepts(tree[1:], members)
        unique = []
        for member in members:
            if member not in unique:
                unique.append(member)
        if len(unique) >= 2:
            found.append({"label": atom[0], "members": unique})
    for child in tree:
        _walk(child, found)


def _hyperedges(src: str) -> list[dict]:
    tokens = _tokenize(src)
    if not tokens:
        return []
    found: list[dict] = []
    _walk(_parse(tokens), found)
    return found


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
