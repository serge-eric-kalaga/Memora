"""Bounded source processing tests; real integration is scripts/memora-qa-local.py."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "memora_ai_test", Path(__file__).parents[1] / "api/memora/ai.py"
)
ai = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai)


def test_long_sources_preserved_without_truncation():
    segments = [{"id": f"s{i}", "text": "French English " * 200} for i in range(70)]
    groups = list(ai.batches(segments))
    assert len(groups) > 1
    assert [item for group in groups for item in group] == segments


def test_audio_duration_bound_and_corruption(tmp_path):
    fixture = Path(__file__).parent / "fixtures/memora/french.aiff"
    assert 1 < ai.validate_audio(fixture, 60) < 60
    with pytest.raises(ValueError, match="maximale"):
        ai.validate_audio(fixture, 1)
    corrupt = tmp_path / "broken.wav"
    corrupt.write_bytes(b"not an audio file")
    with pytest.raises(ValueError, match="corrompu"):
        ai.validate_audio(corrupt, 60)


def test_invented_sources_removed_and_missing_answer(monkeypatch):
    monkeypatch.setattr(
        ai, "generate", lambda *_: {"answer": "Invented", "sources": ["other-meeting"]}
    )
    result = ai.answer([{"id": "s1", "text": "Budget open"}], "Budget?", "fr")
    assert result["sources"] == []
    assert "pas présente" in result["answer"]


def test_chat_reduction_cannot_publish_an_answer_without_sources(monkeypatch):
    segments = [{"id": f"s{i}", "text": "source " * 20} for i in range(2)]
    monkeypatch.setattr(ai, "batches", lambda units: iter([[unit] for unit in units]))

    def generate(prompt, schema, allowed):
        if "réponses partielles" in prompt:
            return {"answer": "Une affirmation sans preuve", "sources": []}
        return {"answer": "Information source", "sources": [allowed[0]]}

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.answer(segments, "Quelle information ?", "fr")
    assert result["sources"] == []
    assert "références vérifiables" in result["answer"]


def test_english_missing_answer_and_report_warnings_are_in_english(monkeypatch):
    monkeypatch.setattr(ai, "generate", lambda *_: {"answer": "", "sources": []})
    assert (
        "not present"
        in ai.answer([{"id": "s1", "text": "Budget open"}], "When?", "en")["answer"]
    )
    generated = ai.Report(
        summary=[ai.Item(text="Check the source", sources=["u1"])],
        actions=[ai.Item(text="Prepare", sources=["u1"])],
    ).model_dump()
    monkeypatch.setattr(ai, "generate", lambda *_: generated)
    result = ai.report([{"id": "s1", "text": "Prepare", "uncertain": True}], "en")
    assert "flagged as uncertain" in result["limitations"]
    assert "Check speaker labels" in result["limitations"]
    assert "attribution is unavailable" not in result["limitations"]
    assert result["actions"][0]["owner"] == "Not specified"
    assert result["actions"][0]["deadline"] == "Not specified"


def test_uncertainty_is_kept_when_reading_units_join_fragments(monkeypatch):
    segments = [
        {
            "id": "s1",
            "start": 0,
            "end": 2,
            "text": "Alice préparera",
            "uncertain": False,
        },
        {"id": "s2", "start": 2, "end": 3, "text": "vendredi.", "uncertain": True},
    ]
    assert ai.reading_units(segments)[0]["uncertain"] is True
    assert '"uncertain": true' in ai.report_prompt(segments, "fr")
    monkeypatch.setattr(
        ai,
        "generate",
        lambda *_: ai.Report(
            summary=[ai.Item(text="À vérifier", sources=["u1"])]
        ).model_dump(),
    )
    assert (
        "1/2 passages signalés incertains" in ai.report(segments, "fr")["limitations"]
    )


def test_reading_units_conservative_and_preserve_original_sources():
    segments = [
        {"id": "s1", "start": 0, "end": 4, "text": "Alice préparera la démonstration"},
        {"id": "s2", "start": 4, "end": 5, "text": "vendredi."},
        {"id": "s3", "start": 5, "end": 8, "text": "Budget ouvert."},
    ]
    units = ai.reading_units(segments)
    assert units[0]["text"] == "Alice préparera la démonstration vendredi."
    assert units[0]["source_ids"] == ["s1", "s2"]
    assert units[1]["source_ids"] == ["s3"]
    assert segments[0]["text"] == "Alice préparera la démonstration"
    for fragment in (
        "Alice revient.",
        "La réunion vendredi.",
        "Nous proposons vendredi.",
    ):
        assert (
            len(ai.reading_units([segments[0], {**segments[1], "text": fragment}])) == 2
        )
    assert (
        len(
            ai.reading_units([{**segments[0], "text": "Alice préparera."}, segments[1]])
        )
        == 2
    )
    assert len(ai.reading_units([segments[0], {**segments[1], "start": 12}])) == 2
    assert (
        len(ai.reading_units([segments[0], {**segments[1], "text": "vendredi?"}])) == 2
    )
    assert (
        len(
            ai.reading_units(
                [
                    {"id": "s1", "text": "Alice préparera"},
                    {"id": "s2", "text": "vendredi."},
                ]
            )
        )
        == 2
    )


def test_report_unit_provenance_expands_and_guessed_original_ids_rejected(monkeypatch):
    segments = [
        {"id": "s1", "start": 0, "end": 4, "text": "Alice préparera la démonstration"},
        {"id": "s2", "start": 4, "end": 5, "text": "vendredi."},
        {"id": "s3", "start": 5, "end": 8, "text": "Budget ouvert."},
    ]
    report = ai.Report(
        summary=[ai.Item(text="Synthèse", sources=["u1"])],
        actions=[
            ai.Item(text="Préparer", owner="Alice", deadline="vendredi", sources=["u1"])
        ],
        open_questions=[ai.Item(text="Budget", sources=["u2"])],
    ).model_dump()
    monkeypatch.setattr(ai, "generate", lambda *_: report)
    result = ai.report(segments, "fr")
    assert result["actions"][0]["sources"] == ["s1", "s2"]
    assert result["open_questions"][0]["sources"] == ["s3"]
    invalid = ai.Report(
        summary=[ai.Item(text="Réindexation incohérente", sources=["s1"])]
    ).model_dump()
    monkeypatch.setattr(ai, "generate", lambda *_: invalid)
    with pytest.raises(ValueError, match="résumé"):
        ai.report(segments, "fr")


def test_speaker_time_metadata_and_distinct_fragment_attribution():
    segments = [
        {
            "id": "s1",
            "start": 2,
            "end": 4,
            "speaker": "Alice",
            "text": "Je préparerai la démonstration",
        },
        {"id": "s2", "start": 4, "end": 5, "speaker": "Bob", "text": "vendredi."},
        {
            "id": "s3",
            "start": 6,
            "end": 7,
            "speaker": "Bob",
            "text": "Mon budget reste ouvert.",
        },
    ]
    units = ai.reading_units(segments)
    assert units[0]["speaker"] is None
    assert units[0]["start"] == 2 and units[0]["end"] == 5
    assert [part["speaker"] for part in units[0]["speaker_parts"]] == ["Alice", "Bob"]
    assert [part["text"] for part in units[0]["speaker_parts"]] == [
        segments[0]["text"],
        "vendredi.",
    ]
    assert [(part["start"], part["end"]) for part in units[0]["speaker_parts"]] == [
        (2, 4),
        (4, 5),
    ]
    assert "speaker_parts" not in units[1]
    assert units[1]["speaker"] == "Bob"
    context = ai.source_context(units)
    assert context[0]["speaker_parts"][0]["text"] == segments[0]["text"]
    assert "source_id" not in context[0]["speaker_parts"][0]
    assert "source_ids" not in context[0]
    assert segments[0]["end"] == 4
    missing = ai.reading_units(
        [{"id": "s4", "text": "Source sans horodatage", "speaker": "Alice"}]
    )[0]
    assert missing["start"] is None and missing["end"] is None


def test_report_builds_global_units_before_batch_boundary(monkeypatch):
    import json

    segments = [
        {
            "id": "s1",
            "start": 0,
            "end": 2,
            "speaker": "Bob",
            "text": "Autre sujet. " * 20,
        },
        {
            "id": "s2",
            "start": 3,
            "end": 5,
            "speaker": "Alice",
            "text": "Je préparerai la démonstration",
        },
        {"id": "s3", "start": 5, "end": 6, "speaker": "Alice", "text": "vendredi."},
    ]
    original_batches = ai.batches
    limit = sum(len(json.dumps(s, ensure_ascii=False)) for s in segments[:2]) + 1
    assert len(list(original_batches(segments, limit=limit))) == 2
    seen = []

    def batched(units):
        assert units[1]["source_ids"] == ["s2", "s3"]
        return original_batches(units, limit=limit)

    def generate(prompt, schema, allowed=None):
        if issubclass(schema, ai.ActionExistence):
            raw = json.loads(prompt.rsplit("\n", 1)[1])
            return {
                "category": "explicit_assigned_work",
                "source_id": next(iter(raw["original_sources"])),
            }
        context = json.loads(prompt.rsplit("\n", 1)[1])
        if isinstance(context, dict):
            return {
                "assignments": [
                    {
                        "candidate_id": record["id"],
                        "status": "work_to_do"
                        if record["category"] == "actions"
                        else "current",
                        "sources": record["item"]["sources"],
                        "explanation": "Source conservée",
                    }
                    for record in context["candidates"]
                ]
            }
        seen.extend(context)
        actions = [
            ai.Item(
                text="Préparer vendredi",
                owner="Alice",
                deadline="vendredi",
                sources=[unit["id"]],
            )
            for unit in context
            if "Je préparerai" in unit["text"]
        ]
        return ai.Report(
            summary=[ai.Item(text="Synthèse", sources=[allowed[0]])], actions=actions
        ).model_dump()

    monkeypatch.setattr(ai, "batches", batched)
    monkeypatch.setattr(ai, "generate", generate)
    result = ai.report(segments, "fr")
    assert [unit["id"] for unit in seen] == ["u1", "u2"]
    assert (
        seen[1]["speaker"] == "Alice" and seen[1]["start"] == 3 and seen[1]["end"] == 6
    )
    assert result["actions"][0]["sources"] == ["s2", "s3"]


def test_chat_uses_canonical_metadata_and_remaps_original_sources(monkeypatch):
    import json

    segments = [
        {
            "id": "s8",
            "start": 3,
            "end": 5,
            "speaker": "Alice",
            "text": "Je préparerai la démonstration",
        },
        {"id": "s9", "start": 5, "end": 6, "speaker": "Alice", "text": "vendredi."},
    ]

    def generate(prompt, schema, allowed):
        context, _ = json.JSONDecoder().raw_decode(prompt.split("UNITÉS:\n", 1)[1])
        assert allowed == ["u1"]
        assert context[0]["speaker"] == "Alice" and context[0]["start"] == 3
        assert context[0]["speaker_parts"][1]["text"] == "vendredi."
        return {"answer": "Alice, vendredi.", "sources": ["u1"]}

    monkeypatch.setattr(ai, "generate", generate)
    assert ai.answer(segments, "Qui prépare et quand ?", "fr")["sources"] == [
        "s8",
        "s9",
    ]
    monkeypatch.setattr(
        ai, "generate", lambda *_: {"answer": "ID original deviné", "sources": ["s8"]}
    )
    assert ai.answer(segments, "Qui prépare ?", "fr")["sources"] == []


def test_chat_reduction_keeps_original_ids_after_unit_remap(monkeypatch):
    segments = [
        {"id": "s10", "speaker": "Alice", "text": "Source première. " * 20},
        {"id": "s20", "speaker": "Bob", "text": "Source seconde. " * 20},
    ]
    monkeypatch.setattr(ai, "batches", lambda units: iter([[unit] for unit in units]))
    phases = []

    def generate(prompt, schema, allowed):
        if "réponses partielles" in prompt:
            assert sorted(allowed) == ["s10", "s20"]
            phases.append("reduce")
            return {
                "answer": "Synthèse avec références originales",
                "sources": list(allowed),
            }
        assert all(source.startswith("u") for source in allowed)
        phases.append("map")
        return {"answer": "Information sourcée", "sources": [allowed[0]]}

    monkeypatch.setattr(ai, "generate", generate)
    result = ai.answer(segments, "Quelles informations ?", "fr")
    assert set(result["sources"]) == {"s10", "s20"}
    assert phases == ["map", "map", "reduce"]


def test_report_prompt_accepts_prebuilt_units_without_reindexing():
    units = ai.reading_units(
        [
            {
                "id": "s17",
                "speaker": "Alice",
                "start": 10,
                "end": 12,
                "text": "Je préparerai.",
            }
        ]
    )
    units[0]["id"] = "u17"
    prompt = ai.report_prompt(None, "fr", units=units)
    assert '"sources": ["u17"]' in prompt and '"id": "u17"' in prompt
    assert '"speaker": "Alice"' in prompt and '"start": 10' in prompt


def test_structured_report_requires_summary_and_all_categories():
    schema = ai.generation_schema(ai.Report, ["u1"])
    assert {"summary", "topics", "decisions", "actions", "open_questions"} <= set(
        schema["required"]
    )
    assert schema["properties"]["summary"]["minItems"] == 1
    assert schema["$defs"]["Item"]["properties"]["sources"]["items"]["enum"] == ["u1"]
    assert schema["$defs"]["Item"]["properties"]["sources"]["minItems"] == 1


def test_generate_disables_server_truncation_and_context_shifting(monkeypatch):
    import json
    import httpx

    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"answer": "Réponse synthétique", "sources": ["u1"]}
                    )
                }
            },
        )

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        ai.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    result = ai.generate("Source synthétique autorisée", ai.Answer, ["u1"])
    assert result["sources"] == ["u1"]
    assert captured["truncate"] is False and captured["shift"] is False
    assert "truncate" not in captured["options"] and "shift" not in captured["options"]
    assert captured["format"]["properties"]["sources"]["items"]["enum"] == ["u1"]


def test_generate_context_overflow_is_safe_processing_error(monkeypatch):
    import httpx

    marker = "SYNTHETIC_PRIVATE_SOURCE_DO_NOT_ECHO"

    def handler(_request):
        return httpx.Response(
            400,
            json={
                "error": f"request (12016 tokens) exceeds the available context size (2048 tokens), {marker}"
            },
        )

    real_client = httpx.Client
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        ai.httpx, "Client", lambda **kwargs: real_client(transport=transport, **kwargs)
    )
    with pytest.raises(ai.ProcessingError, match="troncature silencieuse") as raised:
        ai.generate(marker, ai.Answer, ["u1"])
    message = str(raised.value)
    assert marker not in message and "12016" not in message and "2048" not in message


@pytest.mark.parametrize("failure", [False, True])
def test_generation_and_mlx_share_resource_guard(monkeypatch, tmp_path, failure):
    """Hold generation, prove ASR cannot enter, then verify failure releases guard."""
    import json
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import httpx
    from api.memora import ai, asr_mlx

    entered = threading.Event()
    release = threading.Event()
    asr_entered = threading.Event()
    asr_waiting = threading.Event()
    guard = threading.Lock()

    class InstrumentedGuard:
        def __enter__(self):
            if threading.current_thread().name.endswith("_1"):
                asr_waiting.set()
            guard.acquire()

        def __exit__(self, *_):
            guard.release()

    monkeypatch.setattr(ai, "_lock", InstrumentedGuard())
    monkeypatch.setenv("MEMORA_ASR_ENGINE", "mlx-whisper")

    def handler(_request):
        entered.set()
        assert release.wait(3)
        if failure:
            raise httpx.ConnectError("Synthetic unavailable service")
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps({"answer": "Synthetic", "sources": []})
                }
            },
        )

    def transcribe(*args, **kwargs):
        asr_entered.set()
        return []

    real_client = httpx.Client
    monkeypatch.setattr(
        ai.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(asr_mlx, "transcribe", transcribe)
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="heavy") as pool:
        generation = pool.submit(ai.generate, "Synthetic", ai.Answer)
        assert entered.wait(3)
        speech = pool.submit(ai.transcribe, tmp_path / "synthetic.wav")
        try:
            assert asr_waiting.wait(3)
            assert not asr_entered.is_set()
        finally:
            release.set()
        if failure:
            with pytest.raises(httpx.ConnectError):
                generation.result(timeout=3)
        else:
            assert generation.result(timeout=3)["answer"] == "Synthetic"
        assert speech.result(timeout=3) == []
        assert asr_entered.is_set()
    assert guard.acquire(blocking=False)
    guard.release()


def test_report_omits_missing_value_placeholders_without_rewriting_real_tasks(
    monkeypatch,
):
    result = ai.Report(
        summary=[
            ai.Item(text="Proposition de révision non approuvée.", sources=["u1"])
        ],
        actions=[
            ai.Item(text="Non précisé.", sources=["u1"]),
            ai.Item(
                text="Saisir la mention Non précisé dans le formulaire.", sources=["u1"]
            ),
        ],
        open_questions=[ai.Item(text="No open question", sources=["u1"])],
    ).model_dump()
    monkeypatch.setattr(ai, "generate", lambda *_: result)
    report = ai.report([{"id": "s1", "text": "Source synthétique."}], "fr")
    assert len(report["actions"]) == 1
    assert (
        report["actions"][0]["text"]
        == "Saisir la mention Non précisé dans le formulaire."
    )
    assert report["open_questions"] == []
