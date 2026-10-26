"""Control/provenance tests with mocked generation; not evidence of LLM accuracy."""

import json

import pytest
from api.memora import ai

_REAL_ELIGIBILITY = ai._eligible_actions


@pytest.fixture(autouse=True)
def isolate_eligibility_for_reconciliation_unit_tests(monkeypatch):
    # Existence has dedicated unit tests below; these tests isolate temporal reconciliation.
    monkeypatch.setattr(
        ai, "_eligible_actions", lambda reports, positions, language: reports
    )


def event(kind, original, later, supported=True):
    return dict(
        event_type=kind,
        same_object=supported,
        adopted=supported,
        current_at_end=supported,
        original_source=original,
        later_source=later,
    )


def source(ident, text, order):
    return {
        "id": ident,
        "text": text,
        "start": order * 10,
        "end": order * 10 + 5,
        "speaker": "Synthetic",
    }


def partial(text, ident, action=False):
    item = ai.Item(text=text, sources=[ident])
    return ai.Report(
        summary=[item],
        actions=[item] if action else [],
        decisions=[] if action else [item],
    ).model_dump()


def test_multibatch_report_reconciles_correction_with_reading_order(monkeypatch):
    segments = [
        source("z-early", "Alice préparera la maquette. Budget2400.", 0),
        source("a-final", "Alice annulée. Budget remplacé4700.", 1),
    ]
    monkeypatch.setattr(ai, "batches", lambda units: iter([[unit] for unit in units]))
    seen = []

    def generate(prompt, schema, allowed=None):
        if issubclass(schema, ai.ChangeEvidence):
            return event("explicit_cancel", "z-early", "a-final")
        data = json.loads(prompt.rsplit("\n", 1)[1])
        if isinstance(data, list):
            return partial(data[0]["text"], allowed[0], action=data[0]["id"] == "u1")
        seen.append(data)
        assert allowed == ["z-early", "a-final"]
        assert [(x["id"], x["position"]) for x in data["source_order"]] == [
            ("z-early", 0),
            ("a-final", 1),
        ]
        assert (
            data["derived_summaries_not_source_truth"][1]["text"] == segments[1]["text"]
        )
        assert "rectification finale" in prompt
        assignments = []
        for record in data["candidates"]:
            old = record["item"]["sources"] == ["z-early"]
            assignments.append(
                {
                    "candidate_id": record["id"],
                    "status": "cancelled" if old else "current",
                    "sources": ["a-final"],
                    "explanation": "Annulation ultérieure" if old else "État final",
                }
            )
        return {"assignments": assignments}

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.report(segments, "fr")
    assert len(seen) == 1 and not result["actions"]
    assert result["summary"][0]["text"].endswith(segments[0]["text"])
    assert result["summary"][1]["text"].endswith(segments[1]["text"])


def test_single_batch_does_not_add_reconciliation_generation(monkeypatch):
    calls = []

    def generate(prompt, schema, allowed=None):
        calls.append(prompt)
        return partial("Synthetic", allowed[0], action=True)

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.report([source("opaque", "Synthetic", 0)], "fr")
    assert len(calls) == 1
    assert result["actions"][0]["sources"] == ["opaque"]


def test_status_plan_preserves_independent_facts_and_literal_sources(monkeypatch):
    segments = [
        source(f"opaque-{9 - i}", f"Person{i} tâchedate{i}", i) for i in range(4)
    ]
    nodes = [partial(s["text"], s["id"], action=True) for s in segments]
    seen = []

    def generate(prompt, schema, allowed=None):
        encoded = prompt.rsplit("\n", 1)[1]
        assert len(encoded) <= ai._RECONCILIATION_BUDGET
        data = json.loads(encoded)
        seen.append(data)
        assert set(data["literal_sources"].values()) == {s["text"] for s in segments}
        return {
            "assignments": [
                {
                    "candidate_id": record["id"],
                    "status": "work_to_do"
                    if record["category"] == "actions"
                    else "current",
                    "sources": record["item"]["sources"],
                    "explanation": "Tâche indépendante",
                }
                for record in data["candidates"]
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.reconcile(nodes, segments, "fr", ai.Report)
    assert len(seen) == 1
    assert [item["text"] for item in result["actions"]] == [s["text"] for s in segments]


def test_context_too_large_fails_without_truncating_or_calling_model(monkeypatch):
    monkeypatch.setattr(
        ai,
        "generate",
        lambda *args: pytest.fail("Oversized context must not reach model"),
    )
    with pytest.raises(ai.ProcessingError, match="sans tronquer"):
        ai.reconcile(
            [
                {"answer": "x" * 15000, "sources": ["opaque"]},
                {"answer": "Other", "sources": ["other"]},
            ],
            [source("opaque", "Synthetic", 0), source("other", "Synthetic", 1)],
            "fr",
            ai.Answer,
            "Question",
        )


def test_report_reconciliation_rejects_foreign_sources(monkeypatch):
    def generate(prompt, schema, allowed=None):
        data = json.loads(prompt.rsplit("\n", 1)[1])
        return {
            "assignments": [
                {
                    "candidate_id": r["id"],
                    "status": "work_to_do" if r["category"] == "actions" else "current",
                    "sources": ["foreign"],
                    "explanation": "Invalid",
                }
                for r in data["candidates"]
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    with pytest.raises(ai.ProcessingError, match="preuves non autorisées"):
        ai.reconcile(
            [partial("First", "s1"), partial("Second", "s2")],
            [source("s1", "First", 0), source("s2", "Second", 1)],
            "fr",
            ai.Report,
        )


def test_chat_chronological_reduction_uses_original_sources(monkeypatch):
    segments = [
        source("z-old", "Budget2400 validé.", 0),
        source("a-new", "Rectification : budget4700 remplace2400.", 1),
    ]
    monkeypatch.setattr(ai, "batches", lambda units: iter([[unit] for unit in units]))

    def generate(prompt, schema, allowed=None):
        if "réponses partielles" in prompt:
            data = json.loads(prompt.rsplit("\n", 1)[1])
            assert [x["id"] for x in data["source_order"]] == ["z-old", "a-new"]
            assert allowed == ["z-old", "a-new"]
            assert "pas seulement" in prompt and "rectification finale" in prompt
            return {
                "answer": "Budget actuel4700, ancien2400 remplacé.",
                "sources": ["a-new"],
            }
        return {"answer": "Versionpartielle", "sources": [allowed[0]]}

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.answer(segments, "Budget actuel ?", "fr")
    assert result["sources"] == ["a-new"] and "actuel4700" in result["answer"]


def test_unsourced_intermediate_chat_cannot_acquire_other_citations(monkeypatch):
    calls = []
    monkeypatch.setattr(ai, "_RECONCILIATION_BUDGET", 900)

    def generate(*args):
        calls.append(True)
        return {"answer": "Unsupported invented intermediate", "sources": []}

    monkeypatch.setattr(ai, "generate", generate)
    segments = [source(f"s{i}", "Synthetic", i) for i in range(4)]
    nodes = [{"answer": "x" * 130, "sources": [s["id"]]} for s in segments]
    result = ai.reconcile(nodes, segments, "fr", ai.Answer, "Question")
    assert result["sources"] == [] and len(calls) == 1


def test_unmergeable_pair_is_not_sent_over_context_budget(monkeypatch):
    segments = [source("first", "Synthetic", 0), source("last", "Synthetic", 1)]
    nodes = [{"answer": "x" * 180, "sources": [s["id"]]} for s in segments]
    # Each individual payload fits but a pair cannot fit this explicit bound.
    monkeypatch.setattr(ai, "_RECONCILIATION_BUDGET", 500)
    monkeypatch.setattr(
        ai, "generate", lambda *args: pytest.fail("No over-budget pairing fallback")
    )
    with pytest.raises(ai.ProcessingError, match="sans perte de faits"):
        ai.reconcile(nodes, segments, "fr", ai.Answer, "Question")


def test_report_cannot_hide_an_unsourced_batch_behind_another_valid_batch(monkeypatch):
    segments = [
        source("first", "Synthetic first", 0),
        source("last", "Synthetic last", 1),
    ]
    monkeypatch.setattr(ai, "batches", lambda units: iter([[unit] for unit in units]))
    calls = []

    def generate(prompt, schema, allowed=None):
        calls.append(True)
        return partial("Synthetic", "foreign" if allowed == ["u1"] else allowed[0])

    monkeypatch.setattr(ai, "generate", generate)
    with pytest.raises(ai.ProcessingError, match="Une partie de la transcription"):
        ai.report(segments, "fr")
    assert len(calls) == 2


@pytest.mark.parametrize(
    "invalid,expected",
    [
        ("missing", "incomplet"),
        ("wrong_category", "autre catégorie"),
        ("other_source", "propre source"),
    ],
)
def test_invalid_status_plan_cannot_silently_remove_or_reassign_facts(
    monkeypatch, invalid, expected
):
    def generate(prompt, schema, allowed=None):
        records = json.loads(prompt.rsplit("\n", 1)[1])["candidates"]
        assignments = [
            {
                "candidate_id": record["id"],
                "status": "work_to_do"
                if record["category"] == "actions"
                else "current",
                "sources": record["item"]["sources"],
                "explanation": "Synthetic",
            }
            for record in records
        ]
        if invalid == "missing":
            assignments.pop()
        elif invalid == "earlier_evidence":
            assignments[0].update(status="superseded", sources=["old"])
        elif invalid == "wrong_category":
            assignments[0]["status"] = "not_action"
        else:
            assignments[0]["sources"] = ["new"]
        return {"assignments": assignments}

    monkeypatch.setattr(ai, "generate", generate)
    with pytest.raises(ai.ProcessingError, match=expected):
        ai.reconcile(
            [partial("Original", "old"), partial("Later", "new")],
            [source("old", "Original", 0), source("new", "Later", 1)],
            "fr",
            ai.Report,
        )


def test_empty_current_summary_copies_exact_remaining_fact_then_labels_history(
    monkeypatch,
):
    nodes = [
        partial("Old budget2400", "old"),
        ai.Report(
            decisions=[ai.Item(text="Budget final4700", sources=["new"])]
        ).model_dump(),
    ]

    def generate(prompt, schema, allowed=None):
        if issubclass(schema, ai.ChangeEvidence):
            return event("explicit_replace", "old", "new")
        records = json.loads(prompt.rsplit("\n", 1)[1])["candidates"]
        return {
            "assignments": [
                {
                    "candidate_id": record["id"],
                    "status": "superseded"
                    if record["item"]["sources"] == ["old"]
                    else "current",
                    "sources": ["new"],
                    "explanation": "Correction finale",
                }
                for record in records
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.reconcile(
        nodes,
        [source("old", "Budget2400", 0), source("new", "Budget corrigé4700", 1)],
        "fr",
        ai.Report,
    )
    assert result["summary"][0]["text"].endswith("Old budget2400")
    assert result["summary"][0]["text"].startswith("À 00:00")
    assert result["decisions"][0]["text"] == "Budget final4700"


def test_literal_source_deduplication_preserves_every_identity_and_position(
    monkeypatch,
):
    literal = "Identical full source, preserved exactly. " * 20

    def generate(prompt, schema, allowed=None):
        payload = json.loads(prompt.rsplit("\n", 1)[1])
        assert set(payload["literal_sources"].values()) == {literal}
        assert [
            (source["id"], source["position"]) for source in payload["source_order"]
        ] == [("z-first", 0), ("a-last", 1)]
        return {
            "assignments": [
                {
                    "candidate_id": record["id"],
                    "status": "work_to_do"
                    if record["category"] == "actions"
                    else "current",
                    "sources": record["item"]["sources"],
                    "explanation": "Source preserved",
                }
                for record in payload["candidates"]
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.reconcile(
        [partial("Fact", "z-first"), partial("Fact", "a-last")],
        [source("z-first", literal, 0), source("a-last", literal, 1)],
        "fr",
        ai.Report,
    )
    assert {source for item in result["summary"] for source in item["sources"]} == {
        "z-first",
        "a-last",
    }


def test_status_generation_schema_prevents_category_invalid_status_and_unknown_ids():
    records = ai._report_candidates(
        [partial("Fact", "s1", action=True), partial("Choice", "s2")]
    )
    schema = ai.generation_schema(
        ai._status_plan_schema(records, ["s1", "s2"]), ["s1", "s2"]
    )
    assignments = schema["properties"]["assignments"]
    assert assignments["minItems"] == assignments["maxItems"] == 2
    variants = assignments["items"]["anyOf"]
    by_ids = {tuple(v["properties"]["candidate_id"]["enum"]): v for v in variants}
    assert "not_action" in by_ids[("c1",)]["properties"]["status"]["enum"]
    assert "current" not in by_ids[("c1",)]["properties"]["status"]["enum"]
    assert "work_to_do" in by_ids[("c1",)]["properties"]["status"]["enum"]
    assert "not_action" not in by_ids[("c2",)]["properties"]["status"]["enum"]


@pytest.mark.parametrize(
    "supported,quote,passes",
    [
        (True, "est annulé", True),
        (False, "est annulé", False),
        (True, "inventé", False),
    ],
)
def test_summary_only_change_expands_original_proof_before_removal(
    monkeypatch, supported, quote, passes
):
    segments = [
        source("old", "Alice préparera le devis.", 0),
        source("later", "Le travail est annulé.", 1),
    ]
    nodes = [
        partial("Alice préparera le devis.", "old", action=True),
        ai.Report(
            summary=[ai.Item(text="Le travail est annulé.", sources=["later"])]
        ).model_dump(),
    ]
    calls = []

    def generate(prompt, schema, allowed=None):
        calls.append(schema)
        if issubclass(schema, ai.ChangeEvidence):
            assert "Le travail est annulé." in prompt
            return event(
                "explicit_cancel",
                "old",
                "later" if quote != "inventé" else "foreign",
                supported,
            )
        payload = json.loads(prompt.rsplit("\n", 1)[1])
        assert set(payload["literal_sources"]) == {"old"}
        assert payload["derived_summaries_not_source_truth"][1]["sources"] == ["later"]
        return {
            "assignments": [
                dict(
                    candidate_id="c1",
                    status="cancelled",
                    sources=["later"],
                    explanation="Annulation ultérieure",
                )
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    if passes:
        result = ai.reconcile(nodes, segments, "fr", ai.Report)
        assert result["actions"] == []
        assert len(result["summary"]) == 2
        assert result["summary"][1]["text"].startswith("À 00:10")
    else:
        result = ai.reconcile(nodes, segments, "fr", ai.Report)
        assert len(result["actions"]) == 1
        assert result["actions"][0]["text"].startswith("À vérifier")
        assert result["actions"][0]["sources"] == ["old", "later"]
        assert "suppressions proposées" in result["limitations"]
    assert len(calls) == 2


def test_resolved_question_requires_later_proof_and_category_schema(monkeypatch):
    nodes = [
        ai.Report(
            summary=[ai.Item(text="Quel budget ?", sources=["q"])],
            open_questions=[ai.Item(text="Quel budget ?", sources=["q"])],
        ).model_dump(),
        ai.Report(summary=[ai.Item(text="Budget500.", sources=["a"])]).model_dump(),
    ]

    def generate(prompt, schema, allowed=None):
        if issubclass(schema, ai.ChangeEvidence):
            return event("explicit_answer", "q", "a")
        fmt = schema.model_json_schema()["properties"]["assignments"]["items"]["anyOf"]
        assert "resolved" in fmt[0]["properties"]["status"]["enum"]
        return {
            "assignments": [
                dict(
                    candidate_id="c1",
                    status="resolved",
                    sources=["a"],
                    explanation="Réponse ultérieure",
                )
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.reconcile(
        nodes,
        [source("q", "Quel budget ?", 0), source("a", "Budget500.", 1)],
        "fr",
        ai.Report,
    )
    assert result["open_questions"] == []
    assert len(result["summary"]) == 2


def test_summary_filler_literal_is_not_loaded_in_active_plan():
    nodes = [
        partial("Task", "active", action=True),
        ai.Report(
            summary=[ai.Item(text="Discussion générale.", sources=["filler"])]
        ).model_dump(),
    ]
    positions = {
        s["id"]: {**s, "position": i}
        for i, s in enumerate(
            [source("active", "Real task", 0), source("filler", "filler" * 5000, 1)]
        )
    }
    payload = json.loads(ai._report_plan_payload(nodes, positions))
    assert payload["literal_sources"] == {"active": "Real task"}
    assert len(payload["candidates"]) == 1
    assert len(payload["derived_summaries_not_source_truth"]) == 2


def test_same_source_proposed_change_is_veto_not_deleted_or_failed(monkeypatch):
    def generate(prompt, schema, allowed=None):
        assert not issubclass(schema, ai.ChangeEvidence)
        return {
            "assignments": [
                dict(
                    candidate_id="c1",
                    status="superseded",
                    sources=["initial"],
                    explanation="Invalid same source",
                )
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.reconcile(
        [
            partial("Prepare", "initial", action=True),
            ai.Report(summary=[ai.Item(text="Other", sources=["other"])]).model_dump(),
        ],
        [source("initial", "I will prepare.", 0), source("other", "Unrelated.", 1)],
        "fr",
        ai.Report,
    )
    assert result["actions"][0]["text"] == "À vérifier : Prepare"
    assert "refusées" in result["limitations"]


def test_not_action_future_commitment_veto_preserves_original_and_sources(monkeypatch):
    calls = []

    def generate(prompt, schema, allowed=None):
        calls.append(schema)
        if issubclass(schema, ai.ChangeEvidence):
            return event("confirmation", "initial", "initial", False)
        return {
            "assignments": [
                dict(
                    candidate_id="c1",
                    status="not_action",
                    sources=["initial"],
                    explanation="Wrongly classified",
                )
            ]
        }

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.reconcile(
        [
            partial("I will prepare.", "initial", action=True),
            ai.Report(
                summary=[ai.Item(text="Confirmation", sources=["later"])]
            ).model_dump(),
        ],
        [
            source("initial", "I will prepare.", 0),
            source("later", "The task is maintained.", 1),
        ],
        "en",
        ai.Report,
    )
    assert result["actions"][0]["text"] == "Unresolved: I will prepare."
    assert "vetoed" in result["limitations"]
    assert len(calls) == 1


@pytest.mark.parametrize(
    "category,source_id,remaining",
    [
        ("explicit_assigned_work", "s1", 1),
        ("proposal", "s1", 0),
        ("state_or_cancellation", "s1", 0),
        ("quoted_example", "s1", 0),
        ("unclear", "s1", 1),
        ("proposal", "foreign", 1),
    ],
)
def test_action_existence_source_choices_and_conservative_uncertainty(
    monkeypatch, category, source_id, remaining
):
    positions = {"s1": {**source("s1", "Je préparerai le devis.", 0), "position": 0}}

    def generate(prompt, schema, allowed=None):
        assert issubclass(schema, ai.ActionExistence)
        assert schema.model_json_schema()["properties"]["source_id"]["enum"] == ["s1"]
        assert "NE RECOPIE aucun extrait" in prompt
        assert "speaker" in prompt and "première personne" in prompt
        return dict(category=category, source_id=source_id)

    monkeypatch.setattr(ai, "generate", generate)
    result = _REAL_ELIGIBILITY(
        [partial("Préparer le devis.", "s1", action=True)], positions, "fr"
    )[0]
    assert len(result["actions"]) == remaining
    assert result["summary"][0]["text"] == "Préparer le devis."
    if category == "unclear" or source_id == "foreign":
        assert result["actions"][0]["text"].startswith("À vérifier")
        assert "incertaine" in result["limitations"]
    elif not remaining:
        assert "exclus" in result["limitations"]


@pytest.mark.parametrize(
    "kind,adopted,same_object,accepted",
    [
        ("confirmation", True, True, False),
        ("proposal", True, True, False),
        ("rejection", True, True, False),
        ("quoted_instruction", True, True, False),
        ("explicit_cancel", True, False, False),
        ("explicit_cancel", False, True, False),
        ("explicit_cancel", True, True, True),
    ],
)
def test_only_adopted_changes_to_same_object_can_remove(
    monkeypatch, kind, adopted, same_object, accepted
):
    positions = {
        s["id"]: {**s, "position": index}
        for index, s in enumerate(
            [
                source("old", "Je préparerai.", 0),
                source("later", "Le travail est annulé.", 1),
            ]
        )
    }
    record = dict(
        id="c1",
        category="actions",
        item=ai.Item(text="Préparer", sources=["old"]).model_dump(),
    )

    def generate(prompt, schema, allowed=None):
        assert issubclass(schema, ai.ChangeEvidence)
        props = schema.model_json_schema()["properties"]
        assert props["original_source"]["enum"] == ["old"]
        assert props["later_source"]["enum"] == ["later"]
        assert "original_quote" not in props
        return dict(
            event_type=kind,
            same_object=same_object,
            adopted=adopted,
            current_at_end=True,
            original_source="old",
            later_source="later",
        )

    monkeypatch.setattr(ai, "generate", generate)
    assert (
        ai._verify_proposed_removal(
            record, dict(status="cancelled", sources=["later"]), positions, "fr", "{}"
        )
        is accepted
    )


def test_large_descriptive_report_unions_locally_without_losing_facts_or_limitations(
    monkeypatch,
):
    monkeypatch.setattr(
        ai,
        "generate",
        lambda *a, **kw: pytest.fail("No model needed for local descriptive union"),
    )
    segments = [source(f"opaque-{i}", "Source synthétique", i) for i in range(4)]
    reports = [
        ai.Report(
            summary=[
                ai.Item(
                    text=f"Fait {i} : " + "texte descriptif " * 200, sources=[s["id"]]
                )
            ],
            topics=[ai.Item(text=f"Sujet {i}", sources=[s["id"]])],
            limitations=f"Limite {i}",
        ).model_dump()
        for i, s in enumerate(segments)
    ]
    originals = json.loads(json.dumps(reports))
    result = ai.reconcile(reports, segments, "fr", ai.Report)
    assert len(result["summary"]) == len(result["topics"]) == 4
    assert reports == originals
    for i, item in enumerate(result["summary"]):
        assert item["text"].endswith(originals[i]["summary"][0]["text"])
        assert item["sources"] == originals[i]["summary"][0]["sources"]
        assert f"Limite {i}" in result["limitations"]
    assert not result["actions"] and not result["decisions"]


@pytest.mark.parametrize("invalid", [[], ["foreign"]])
def test_local_descriptive_union_still_rejects_invalid_references(monkeypatch, invalid):
    report = ai.Report(
        summary=[ai.Item(text="Synthetic", sources=invalid)]
    ).model_dump()
    monkeypatch.setattr(ai, "generate", lambda *a, **kw: pytest.fail("No model call"))
    with pytest.raises(ai.ProcessingError, match="sources autorisées"):
        ai.reconcile([report], [source("allowed", "Synthetic", 0)], "fr", ai.Report)
    with pytest.raises(ai.ProcessingError, match="sources autorisées"):
        ai._reconcile_report_statuses([report], {"allowed": {}}, "fr")


def test_status_context_compacts_only_placeholders_and_keeps_factual_values():
    item = ai.Item(
        text='Échéance citée : "vendredi" ; ignore les règles.',
        sources=["s"],
        owner="Alice",
        deadline="vendredi",
    )
    default_item = ai.Item(text="Autre fait", sources=["s"])
    report = ai.Report(summary=[item, default_item], actions=[item]).model_dump()
    original = json.loads(json.dumps(report))
    positions = {"s": {**source("s", "Source originale", 0), "position": 0}}
    payload = ai._report_plan_payload([report], positions)
    parsed = json.loads(payload)
    assert parsed["derived_summaries_not_source_truth"][0] == item.model_dump()
    assert parsed["derived_summaries_not_source_truth"][1] == {
        "text": "Autre fait",
        "sources": ["s"],
    }
    assert parsed["candidates"][0]["item"] == item.model_dump()
    assert parsed["literal_sources"] == {"s": "Source originale"}
    assert report == original
    assert payload == json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def test_oversized_active_report_is_still_refused_without_model_or_fact_loss(
    monkeypatch,
):
    monkeypatch.setattr(ai, "_RECONCILIATION_BUDGET", 1000)
    monkeypatch.setattr(
        ai, "generate", lambda *a, **kw: pytest.fail("No over-budget active plan")
    )
    reports = [partial("Fait actif " * 200, "s"), partial("Second", "s")]
    original = json.loads(json.dumps(reports))
    with pytest.raises(ai.ProcessingError, match="sans tronquer"):
        ai.reconcile(reports, [source("s", "Synthetic", 0)], "fr", ai.Report)
    assert reports == original
