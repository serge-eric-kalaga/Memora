"""Real local analysis benchmark with explicit, manually adjudicated semantic facts.

Default lists the corpus. --run invokes local models; --score never invokes AI.
No word matching or model self-grade is accepted as semantic ground truth.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "backend/test/fixtures/memora/analysis/cases-v1.json"
CATEGORIES = ("summary", "topics", "decisions", "actions", "open_questions")
RUBRIC = (
    "supported",
    "modality_correct",
    "owner_correct",
    "deadline_correct",
    "category_correct",
    "citations_sufficient",
)


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review_template(results):
    reviews = []
    for row in results["results"]:
        reviews.append(
            {
                "case": row["case"],
                "forbidden_violations": None,
                "items": [
                    {
                        "id": item["id"],
                        "gold_facts": [],
                        **{key: None for key in RUBRIC},
                        "reason": "",
                    }
                    for item in row["items"]
                ],
                "answer": ({key: None for key in RUBRIC} | {"reason": ""})
                if row.get("answer") is not None
                else None,
            }
        )
    return {
        "results_sha256": None,
        "adjudicator": "",
        "instructions": "Read literal synthetic sources, expected propositions and all output claims. Null means ungraded, not false. Map only fully expressed expected propositions to gold fact IDs; a valid topical heading may map to no atomic fact and still be supported; mark each rubric field (true when genuinely not applicable). A factual claim with changed negation/modality/person/date fails even with valid source IDs. Record forbidden semantic violations, not mere quoted mentions. Do not grade by exact text or LLM self-evaluation.",
        "reviews": reviews,
    }


def score(results, reviews, corpus):
    if not reviews.get("adjudicator", "").strip():
        raise ValueError("Semantic adjudicator required")
    expected = {case["id"]: case for case in corpus["cases"]}
    graded = {row["case"]: row for row in reviews["reviews"]}
    result_ids = [row["case"] for row in results["results"]]
    if set(result_ids) != set(expected) or len(result_ids) != len(expected):
        raise ValueError("Complete corpus results required; partial runs cannot pass")
    if set(graded) != set(expected) or len(reviews["reviews"]) != len(expected):
        raise ValueError("Exactly one semantic review per case required")
    tp = fp = covered = gold_count = answer_correct = answer_total = violations = 0
    by_case = []
    for row in results["results"]:
        case = expected[row["case"]]
        review = graded[row["case"]]
        if not isinstance(review["forbidden_violations"], list):
            raise TypeError("Every case needs explicit forbidden-claim review")
        violations += len(review["forbidden_violations"])
        gold = {fact["id"] for fact in case["expected_facts"]}
        gold_count += len(gold)
        found = set()
        grades = {item["id"]: item for item in review["items"]}
        if set(grades) != {item["id"] for item in row["items"]}:
            raise ValueError("Every report item must be adjudicated exactly once")
        allowed = {item["id"] for item in case["segments"]}
        ctp = cfp = 0
        valid_ids = set()
        for item in row["items"]:
            grade = grades[item["id"]]
            if any(type(grade.get(key)) is not bool for key in RUBRIC):
                raise ValueError("Pending semantic rubric: no score published")
            mapped = set(grade["gold_facts"])
            if not mapped <= gold:
                raise ValueError("Unknown gold fact ID")
            sources = item["value"].get("sources", [])
            valid = (
                all(grade[key] for key in RUBRIC)
                and bool(sources)
                and set(sources) <= allowed
            )
            if valid:
                tp += 1
                ctp += 1
                found.update(mapped)
                valid_ids.add(item["id"])
            else:
                fp += 1
                cfp += 1
        if review.get("gold_fact_groups") is not None:
            # Some expected propositions require jointly supporting several items.
            # Count them only if every adjudicated evidence item is conformant.
            groups = review["gold_fact_groups"]
            if not set(groups) <= gold or any(
                not evidence or not set(evidence) <= set(grades)
                for evidence in groups.values()
            ):
                raise ValueError("Invalid joint fact evidence")
            found = {
                fact for fact, evidence in groups.items() if set(evidence) <= valid_ids
            }
        covered += len(found)
        if row.get("answer") is not None:
            answer_total += 1
            grade = review["answer"]
            if any(type(grade.get(key)) is not bool for key in RUBRIC):
                raise ValueError("Pending chat rubric: no score published")
            answer_correct += int(
                all(grade[key] for key in RUBRIC)
                and set(row["answer"].get("sources", [])) <= allowed
            )
        by_case.append(
            {
                "case": row["case"],
                "supported_items": ctp,
                "unsupported_or_wrong_items": cfp,
                "covered_gold_facts": len(found),
                "gold_facts": len(gold),
                "forbidden_violations": review["forbidden_violations"],
            }
        )
    precision = tp / (tp + fp) if tp + fp else 0
    recall = covered / gold_count if gold_count else 0
    return {
        "semantic_adjudicator": reviews["adjudicator"],
        "report_item_precision": precision,
        "gold_fact_recall": recall,
        "supported_items": tp,
        "unsupported_or_wrong_items": fp,
        "covered_gold_facts": covered,
        "gold_facts": gold_count,
        "chat_correct": answer_correct,
        "chat_total": answer_total,
        "forbidden_violations": violations,
        "target_90_met": precision >= 0.9
        and recall >= 0.9
        and violations == 0
        and answer_correct == answer_total,
        "by_case": by_case,
        "limit": "Synthetic corpus only. Human semantic mapping is required; IDs existing alone do not establish factual support. Precision unit is report item, recall unit is unique expected atomic fact; repeated facts do not inflate recall.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--corpus", type=Path, default=CASES)
    parser.add_argument(
        "--score", type=Path, help="Completed semantic review JSON; no inference"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / ".agents/logs/analysis-benchmark-v1.json"
    )
    args = parser.parse_args()
    corpus = load(args.corpus)
    if args.score:
        reviews = load(args.score)
        if reviews["results_sha256"] != digest(args.output):
            raise ValueError("Review does not reference exact result file hash")
        results = load(args.output)
        if results["corpus_sha256"] != digest(args.corpus):
            raise ValueError("Corpus changed since inference")
        print(json.dumps(score(results, reviews, corpus), ensure_ascii=False, indent=2))
        return
    if not args.run:
        print(
            json.dumps(
                {
                    "cases": [case["id"] for case in corpus["cases"]],
                    "count": len(corpus["cases"]),
                    "corpus_sha256": digest(args.corpus),
                    "inference": False,
                },
                indent=2,
            )
        )
        return
    if args.output.exists():
        raise ValueError("Output exists: choose a new --output to preserve evidence")
    os.environ.update(MEMORA_MODEL="gemma4:e4b", MEMORA_OLLAMA_KEEP_ALIVE="0")
    spec = importlib.util.spec_from_file_location(
        "analysis_benchmark_ai", ROOT / "backend/api/memora/ai.py"
    )
    ai = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ai)
    results = {
        "model": ai.MODEL,
        "ai_sha256": digest(ROOT / "backend/api/memora/ai.py"),
        "corpus_sha256": digest(args.corpus),
        "synthetic_only": True,
        "results": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in corpus["cases"]:
        start = time.monotonic()
        report = ai.report(case["segments"], "fr")
        row = {
            "case": case["id"],
            "expected_facts": case["expected_facts"],
            "forbidden_claims": case["forbidden_claims"],
            "synthetic_sources": case["segments"],
            "report_seconds": round(time.monotonic() - start, 3),
            "report": report,
            "items": [
                {"id": f"{category}:{i}", "category": category, "value": item}
                for category in CATEGORIES
                for i, item in enumerate(report[category])
            ],
            "answer": None,
        }
        if case.get("question"):
            start = time.monotonic()
            row.update(
                question=case["question"],
                expected_answer=case["expected_answer"],
                answer=ai.answer(case["segments"], case["question"], "fr"),
                answer_seconds=round(time.monotonic() - start, 3),
            )
        results["results"].append(row)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(case["id"], "inference complete; semantic grading pending", flush=True)
    template = review_template(results)
    template["results_sha256"] = digest(args.output)
    args.output.with_suffix(".review.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2)
    )
    print("No accuracy claim until completed semantic review and --score.")


if __name__ == "__main__":
    main()
