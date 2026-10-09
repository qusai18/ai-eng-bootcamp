"""Read answer and passage fields the same way RAGDoll2 does."""

from __future__ import annotations


def pick_answer(data) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    if not isinstance(data, dict):
        return ""
    for key in ("answer", "response", "output", "result", "text", "completion"):
        if isinstance(data.get(key), str):
            return data[key]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    content = data.get("content")
    if isinstance(content, list):
        for bit in content:
            if isinstance(bit, dict) and isinstance(bit.get("text"), str):
                return bit["text"]
    message = data.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    return ""


def pick_contexts(data) -> list[dict]:
    if not isinstance(data, dict):
        return []
    raw = None
    for key in ("contexts", "documents", "passages", "sources", "chunks", "results"):
        if key in data:
            raw = data[key]
            break
    if not isinstance(raw, list):
        return []
    contexts = []
    for item in raw:
        if isinstance(item, str):
            text = item[:1600]
            doc_id = ""
        elif isinstance(item, dict):
            text = str(
                item.get("text")
                or item.get("content")
                or item.get("page_content")
                or item.get("passage")
                or item.get("snippet")
                or ""
            )[:1600]
            doc_id = str(
                item.get("id")
                or item.get("docid")
                or item.get("doc_id")
                or item.get("source")
                or ""
            )
        else:
            continue
        if text:
            contexts.append({"id": doc_id, "text": text})
        if len(contexts) == 20:
            break
    return contexts


def chat_url(base: str) -> str:
    base = base.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if len(base) >= 3 and base[-3:-1] == "/v" and base[-1].isdigit():
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def claude_url(base: str) -> str:
    base = base.strip().rstrip("/")
    if base.endswith("/messages"):
        return base
    if len(base) >= 3 and base[-3:-1] == "/v" and base[-1].isdigit():
        return base + "/messages"
    return base + "/v1/messages"
