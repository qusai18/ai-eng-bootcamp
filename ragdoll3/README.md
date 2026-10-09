# RAGDoll3

Live bench: run from this folder, then open the printed local URL.

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8773
```

RAGDoll3 compares up to 10 retrieval-augmented endpoints on one shared question list. The server posts each question, so the RAG host does not need browser CORS. The verdict keeps the RAGDoll2 columns and adds:

- **Ragas:** faithfulness and answer relevancy on every successful answer. Context precision and context recall only for topics that have a reference answer.
- **DeepEval:** the same four metrics. The score and the judge's reason show on the open row, not as extra table columns.
- **BenchmarkQED pairwise:** win rate on relevance, comprehensiveness, diversity, and empowerment when at least two dolls return an answer.
- **BenchmarkQED reference:** correctness and completeness, on a 1–10 scale, only for topics with a reference answer.

The OpenAI key can be typed in the page for one run, or set as `OPENAI_API_KEY` on the server. A key typed in the page is not written into this repo. BenchmarkQED's temporary files are deleted when the scoring step finishes.

`offline-demo` in the key field fills the new columns from lexical overlap so the table can be checked without a model. Those numbers are not Ragas or BenchmarkQED scores.

## Add a doll

Provider **RAG application**. The endpoint receives:

```http
POST {your URL}
Content-Type: application/json

{"query":"<topic text>","top_k":5}
```

A usable body:

```json
{
  "answer": "Eleven players are on the field at one time.",
  "contexts": [
    { "id": "kilt-123", "text": "A soccer team fields eleven players." }
  ]
}
```

Answer and passage field names match RAGDoll2. Two stand-in endpoints are built in: `/stubs/grounded/query` and `/stubs/partial/query`.

OpenAI and Claude dolls are chat calls. They do not retrieve passages. One of them can still be the 1–5 judge.

## Reference answers

This file is separate from qrels. Qrels still drive Recall@K, MRR, and nDCG.

```json
[{ "qid": "T01", "reference": "Eleven players are on the field at one time." }]
```

Context precision, context recall, correctness, and completeness use only the topics listed here. A reference for one topic does not invent a score for the others.

## What this bench does not do

It does not upload a corpus. It does not generate questions, score assertions, or run BenchmarkQED retrieval-reference or significance tests. BenchmarkQED trial counts must be even; an odd number is raised by one.
