"""Offline scoring checks; no language model called."""

import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "analysis_bench", Path(__file__).parents[1] / "memora-benchmark-analysis.py"
)
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class SemanticScoring(unittest.TestCase):
    def test_valid_ids_do_not_mask_wrong_modality(self):
        corpus = {
            "cases": [
                {
                    "id": "synthetic",
                    "segments": [{"id": "s1"}],
                    "expected_facts": [{"id": "f1"}],
                }
            ]
        }
        results = {
            "results": [
                {
                    "case": "synthetic",
                    "items": [{"id": "summary:0", "value": {"sources": ["s1"]}}],
                }
            ]
        }
        review = {
            "adjudicator": "Synthetic test",
            "reviews": [
                {
                    "case": "synthetic",
                    "forbidden_violations": [],
                    "items": [
                        {
                            "id": "summary:0",
                            "gold_facts": ["f1"],
                            **dict.fromkeys(bench.RUBRIC, True),
                        }
                    ],
                }
            ],
        }
        correct = bench.score(results, review, corpus)
        self.assertTrue(correct["target_90_met"])
        review["reviews"][0]["items"][0]["modality_correct"] = False
        wrong = bench.score(results, review, corpus)
        self.assertEqual(wrong["unsupported_or_wrong_items"], 1)
        self.assertEqual(wrong["gold_fact_recall"], 0)
        self.assertFalse(wrong["target_90_met"])
        review["reviews"][0]["items"][0]["modality_correct"] = None
        with self.assertRaisesRegex(ValueError, "Pending"):
            bench.score(results, review, corpus)

    def test_supported_heading_does_not_inflate_atomic_fact_recall(self):
        corpus = {
            "cases": [
                {
                    "id": "synthetic",
                    "segments": [{"id": "s1"}],
                    "expected_facts": [{"id": "f1"}],
                }
            ]
        }
        results = {
            "results": [
                {
                    "case": "synthetic",
                    "items": [{"id": "topics:0", "value": {"sources": ["s1"]}}],
                }
            ]
        }
        review = {
            "adjudicator": "Synthetic",
            "reviews": [
                {
                    "case": "synthetic",
                    "forbidden_violations": [],
                    "items": [
                        {
                            "id": "topics:0",
                            "gold_facts": [],
                            **dict.fromkeys(bench.RUBRIC, True),
                        }
                    ],
                }
            ],
        }
        result = bench.score(results, review, corpus)
        self.assertEqual(result["report_item_precision"], 1)
        self.assertEqual(result["gold_fact_recall"], 0)
        self.assertFalse(result["target_90_met"])

    def test_joint_fact_requires_all_supporting_items(self):
        corpus = {
            "cases": [
                {
                    "id": "synthetic",
                    "segments": [{"id": "s1"}],
                    "expected_facts": [{"id": "f1"}],
                }
            ]
        }
        results = {
            "results": [
                {
                    "case": "synthetic",
                    "items": [
                        {"id": name, "value": {"sources": ["s1"]}}
                        for name in ("summary:0", "summary:1")
                    ],
                }
            ]
        }
        review = {
            "adjudicator": "Synthetic",
            "reviews": [
                {
                    "case": "synthetic",
                    "forbidden_violations": [],
                    "gold_fact_groups": {"f1": ["summary:0", "summary:1"]},
                    "items": [
                        {
                            "id": name,
                            "gold_facts": [],
                            **dict.fromkeys(bench.RUBRIC, True),
                        }
                        for name in ("summary:0", "summary:1")
                    ],
                }
            ],
        }
        self.assertEqual(bench.score(results, review, corpus)["gold_fact_recall"], 1)
        review["reviews"][0]["items"][1]["supported"] = False
        self.assertEqual(bench.score(results, review, corpus)["gold_fact_recall"], 0)

    def test_partial_run_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "Complete corpus"):
            bench.score(
                {"results": []},
                {"adjudicator": "Synthetic", "reviews": []},
                {"cases": [{"id": "missing"}]},
            )


if __name__ == "__main__":
    unittest.main()
