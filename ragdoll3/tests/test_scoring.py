"""Column and lexical checks that do not call a model."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring.benchmark_qed import _parse_pairwise, _parse_reference, even_trials
from scoring.lexical import score_row
from scoring.offline import apply_offline


class LexicalTests(unittest.TestCase):
    def test_grounded_sentence_and_qrels(self):
        contexts = [
            {"id": "kilt-123", "text": "A soccer team fields eleven players at one time."},
            {"id": "kilt-900", "text": "Spectator rules vary by stadium."},
        ]
        scored = score_row(
            "Eleven players are on the field at one time.",
            contexts,
            "how many players are on a soccer team on the field at one time",
            {"kilt-123": 1},
        )
        self.assertGreater(scored["ground"], 0.5)
        self.assertEqual(scored["recall"], 1)
        self.assertEqual(scored["mrr"], 1)
        self.assertGreater(scored["ndcg"], 0)

    def test_missing_qrels_hide_rank_metrics(self):
        scored = score_row("Eleven players are on the field.", [{"id": "a", "text": "players"}], "players", None)
        self.assertIsNone(scored["recall"])


class OfflineColumnTests(unittest.TestCase):
    def test_reference_metrics_only_on_referenced_topic(self):
        rows = {
            "a": [
                {
                    "qid": "T01",
                    "query": "how many players",
                    "answer": "Eleven players are on the field at one time.",
                    "contexts": [{"id": "kilt-123", "text": "A soccer team fields eleven players."}],
                    "error": None,
                    "local": {},
                },
                {
                    "qid": "T02",
                    "query": "what causes the northern lights",
                    "answer": "Charged particles from the sun collide with gases.",
                    "contexts": [{"id": "kilt-201", "text": "charged particles from the sun strike gases"}],
                    "error": None,
                    "local": {},
                },
            ]
        }
        for row in rows["a"]:
            row["local"] = score_row(row["answer"], row["contexts"], row["query"], None)
        apply_offline(
            rows,
            {"T01": "Eleven players are on the field at one time."},
            ragas=True,
            deepeval=False,
            pairwise=False,
            reference=True,
        )
        self.assertIsNotNone(rows["a"][0]["ragas"]["context_precision"])
        self.assertIsNone(rows["a"][1]["ragas"]["context_precision"])
        self.assertIn("correctness", rows["a"][0]["qed"])
        self.assertNotIn("qed", rows["a"][1])
        self.assertIsNotNone(rows["a"][0]["ragas"]["faithfulness"])
        self.assertIsNotNone(rows["a"][1]["ragas"]["faithfulness"])


class BenchmarkParseTests(unittest.TestCase):
    def test_even_trials(self):
        self.assertEqual(even_trials(1), 2)
        self.assertEqual(even_trials(2), 2)

    def test_pairwise_csv_fills_win_rate(self):
        root = Path(__file__).resolve().parent / "_tmp_qed"
        root.mkdir(exist_ok=True)
        csv = root / "live_grounded--partial.csv"
        csv.write_text(
            "question,criteria,grounded_score,partial_score\n"
            "how many players,relevance,1.0,0.0\n"
            "how many players,comprehensiveness,0.5,0.5\n",
            encoding="utf-8",
        )
        rows = {
            "a": [{"qid": "T01", "query": "how many players", "error": None, "answer": "Eleven"}],
            "b": [{"qid": "T01", "query": "how many players", "error": None, "answer": "Several"}],
        }
        self.assertTrue(_parse_pairwise(root, {"grounded": "a", "partial": "b"}, rows))
        self.assertEqual(rows["a"][0]["qed"]["relevance"], 1.0)
        self.assertEqual(rows["b"][0]["qed"]["relevance"], 0.0)
        csv.unlink()
        root.rmdir()

    def test_reference_csv(self):
        root = Path(__file__).resolve().parent / "_tmp_ref"
        root.mkdir(exist_ok=True)
        path = root / "reference_scores-grounded.csv"
        path.write_text(
            "question,criteria,score\nhow many players,correctness,8\nhow many players,completeness,6\n",
            encoding="utf-8",
        )
        rows = {"a": [{"qid": "T01", "query": "how many players", "error": None, "answer": "Eleven"}]}
        self.assertTrue(_parse_reference(root, {"grounded": "a"}, rows))
        self.assertEqual(rows["a"][0]["qed"]["correctness"], 8)
        self.assertEqual(rows["a"][0]["qed"]["completeness"], 6)
        path.unlink()
        root.rmdir()


if __name__ == "__main__":
    unittest.main()
