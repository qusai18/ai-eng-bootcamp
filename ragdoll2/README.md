# RAGDoll2 — instructor guide

Live bench: https://ragdoll2.onrender.com

Source: https://github.com/qusai18/ai-eng-bootcamp/tree/2026-10-01-d19q/ragdoll2

RAGDoll2 compares up to 10 retrieval-augmented endpoints on one shared question list and writes one verdict table. It is a single static page. API keys stay in the browser. Render does not store them.

## What instructors do

1. Open https://ragdoll2.onrender.com.
2. Add each system under test with **Add doll**. Repeat until every system is in the list (up to 10). The button label changes to **Add another doll**.
3. Leave the topics you want checked in **Evidence set**, or import your own topics and qrels.
4. In **Harness**, leave the judge on **none** for lexical scores only, or pick an OpenAI or Claude doll to score faithfulness, relevance, and groundedness from 1 to 5.
5. Click **Run evaluation**.
6. Read **Verdict**. One row per doll. Open a doll to see each answer, the passages it returned, and any judge notes.

Every registered doll is compared. The Harness dropdown does not select which dolls run. It only selects the judge.

## Add a RAG application

Provider: **RAG application**. The only required field is the endpoint URL.

The bench sends:

```http
POST {your URL}
Content-Type: application/json

{"query":"<topic text>","top_k":5}
```

`top_k` is the K slider in Evidence set (1–10, default 5).

The endpoint must return HTTP 200 and JSON. A usable body looks like this:

```json
{
  "answer": "Eleven players are on the field at one time.",
  "contexts": [
    { "id": "kilt-123", "text": "A soccer team fields eleven players." }
  ]
}
```

The answer may also be named `response`, `output`, `result`, `text`, or `completion`. Passages may also be named `documents`, `passages`, `sources`, `chunks`, or `results`. Each passage id may be `id`, `docid`, `doc_id`, or `source`. Passage text may be `text`, `content`, `page_content`, `passage`, or `snippet`.

The host must allow browser CORS from `https://ragdoll2.onrender.com` for `POST`. The bench does not proxy the call.

The knowledge base stays inside the RAG app. This bench never uploads documents. It only sees the passages that endpoint returns. At most 20 passages are kept, each cut to 1,600 characters.

## Add OpenAI or Claude

Choose provider **OpenAI** or **Claude**, then fill the base URL, API key, and model.

| Provider | Default base URL | Default model if the field is empty |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Claude | `https://api.anthropic.com/v1` | `claude-sonnet-4-5` |

These are chat calls. They do not retrieve passages. Use them as extra dolls, or pick one as the judge. A judge sees the question, up to 6 passages of 600 characters, and the answer, and returns JSON scores. If the RAG app returned no passages, the judge is told that and should score unsupported factual claims as 1.

OpenAI and Claude must also allow browser CORS, or the call fails in this page.

## Evidence set and qrels

The page starts with 14 bundled questions. Import replaces them (up to 300).

Topics (`topics.json`):

```json
[
  { "qid": "2024-1", "query": "how many players are on a soccer team on the field at one time" },
  { "qid": "2024-2", "query": "what causes the northern lights to occur" }
]
```

Qrels (`qrels.json`). `docid` must match the passage id the RAG app returns. `rel` above 0 counts as relevant.

```json
[
  { "qid": "2024-1", "docid": "kilt-123", "rel": 1 },
  { "qid": "2024-1", "docid": "kilt-456", "rel": 2 },
  { "qid": "2024-2", "docid": "kilt-789", "rel": 1 }
]
```

With qrels loaded, the verdict adds Recall@K, MRR, and nDCG@10. Without qrels, those columns stay hidden.

The note about a ~5.9M-document KILT Wikipedia corpus describes the official TREC RAG 2024 track. Those documents are not loaded in this app.

## Local copy

From this folder:

```bash
python -m http.server 8771
```

Open http://127.0.0.1:8771/. For a local page, the RAG host must allow CORS from `http://127.0.0.1:8771`.
