import inspect


def call_with(fn, /, *args, **wanted):
    """Pass only keyword arguments the callable actually accepts."""
    params = inspect.signature(fn).parameters
    accepts_var = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if accepts_var:
        return fn(*args, **wanted)
    kwargs = {key: value for key, value in wanted.items() if key in params and value is not None}
    return fn(*args, **kwargs)


def as_data(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict") and callable(value.dict):
        try:
            return value.dict()
        except Exception:
            pass
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            key: as_data(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    if isinstance(value, dict):
        return {key: as_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_data(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def text_of(doc: dict, limit: int = 60000) -> tuple[str, bool]:
    raw = (doc.get("text") or "").strip()
    clipped = raw[:limit]
    return clipped, len(raw) > limit


def source_header(doc: dict) -> str:
    return f"Source document id: {doc['id']}\nSource document name: {doc['name']}\n\n"


def graph_of(hyperedges: list[dict], limit_edges: int = 8, limit_nodes: int = 18) -> dict:
    """Normalize hyperedges into the shape the Ask view draws."""
    nodes = []
    seen: dict[str, str] = {}
    edges = []
    for edge in hyperedges:
        members = []
        for name in edge.get("members") or []:
            label = " ".join(str(name).split()).strip(" \"'")
            if len(label) < 2:
                continue
            key = label.lower()
            if key not in seen:
                if len(seen) >= limit_nodes:
                    continue
                seen[key] = f"n{len(seen)}"
                nodes.append({"id": seen[key], "label": label[:48]})
            if seen[key] not in members:
                members.append(seen[key])
        if len(members) < 2:
            continue
        edges.append({
            "id": f"e{len(edges)}",
            "label": " ".join(str(edge.get("label") or "relation").split())[:90],
            "members": members,
        })
        if len(edges) >= limit_edges:
            break
    used = {member for edge in edges for member in edge["members"]}
    return {"nodes": [node for node in nodes if node["id"] in used], "hyperedges": edges}
