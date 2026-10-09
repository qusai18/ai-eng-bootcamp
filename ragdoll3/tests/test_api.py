"""Stream two stub dolls and check which columns the payload fills."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import app

TOPICS = [
    {"qid": "T01", "query": "how many players are on a soccer team on the field at one time"},
    {"qid": "T02", "query": "what causes the northern lights to occur"},
]
DOLLS = [
    {"id": "a", "name": "Grounded", "type": "rag", "url": "/stubs/grounded/query", "color": "#0785f2"},
    {"id": "b", "name": "Partial", "type": "rag", "url": "/stubs/partial/query", "color": "#ffc628"},
]


def _run(scorers):
    client = TestClient(app)
    response = client.post(
        "/api/evaluate",
        json={"dolls": DOLLS, "topics": TOPICS, "scorers": scorers, "k": 5},
    )
    assert response.status_code == 200, response.text
    events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    done = next(event for event in events if event["type"] == "done")
    rows = {}
    for event in events:
        if event["type"] == "row":
            rows.setdefault(event["doll_id"], {})[event["index"]] = event["row"]
    return done, rows, [event["text"] for event in events if event["type"] == "log"]


class ApiTests(unittest.TestCase):
    def test_missing_key_keeps_lexical_columns(self):
        done, rows, logs = _run(
            {"ragas": True, "deepeval": True, "pairwise": True, "reference": True, "judge_key": ""}
        )
        grounded = rows["a"][0]
        self.assertIsNone(grounded["error"])
        self.assertGreater(grounded["latency"], 0)
        self.assertIsNotNone(grounded["local"]["ground"])
        self.assertNotIn("ragas", grounded)
        self.assertTrue(any("judge key missing" in line for line in logs))
        self.assertEqual(done["run"]["errs"], 0)

    def test_offline_reference_is_limited_to_one_topic(self):
        done, rows, logs = _run(
            {
                "ragas": True,
                "deepeval": True,
                "pairwise": True,
                "reference": True,
                "trials": 1,
                "judge_key": "offline-demo",
                "judge_model": "gpt-4o-mini",
            }
            | {}
        )
        # references are a sibling field, not inside scorers
        client = TestClient(app)
        response = client.post(
            "/api/evaluate",
            json={
                "dolls": DOLLS,
                "topics": TOPICS,
                "references": [{"qid": "T01", "reference": "Eleven players are on the field at one time."}],
                "scorers": {
                    "ragas": True,
                    "deepeval": True,
                    "pairwise": True,
                    "reference": True,
                    "trials": 1,
                    "judge_key": "offline-demo",
                },
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        events = [json.loads(line) for line in response.text.splitlines() if line.strip()]
        latest = {}
        for event in events:
            if event["type"] == "row":
                latest[(event["doll_id"], event["index"])] = event["row"]
        first = latest[("a", 0)]
        second = latest[("a", 1)]
        self.assertIsNotNone(first["ragas"]["faithfulness"])
        self.assertIsNotNone(first["ragas"]["context_precision"])
        self.assertIsNotNone(first["qed"]["correctness"])
        self.assertIsNotNone(first["qed"]["relevance"])
        self.assertTrue(first["deepeval"]["faithfulness"]["reason"])
        self.assertIsNotNone(second["ragas"]["faithfulness"])
        self.assertIsNone(second["ragas"]["context_precision"])
        self.assertIsNone((second.get("qed") or {}).get("correctness"))
        self.assertIsNotNone(second["qed"]["relevance"])
        self.assertTrue(any("offline-demo" in line for line in (event["text"] for event in events if event["type"] == "log")))
        self.assertIn("run", done)


if __name__ == "__main__":
    unittest.main()
