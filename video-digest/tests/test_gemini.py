"""Hermetic tests for ytdigest.gemini: the "Gemini watches the URL" prompt and the
parsing of the model's answer.

No network, no real key: ``requests.post`` is faked, the client is a stub that only
records usage, and ``GEMINI_API_KEY`` is a dummy value set per test.
"""

import json

import pytest


SEGS = [
    {"start": 0.0, "end": 9.0, "text": "Inflacja to wzrost cen."},
    {"start": 10.0, "end": 19.0, "text": "Banki podnoszą stopy."},
]

BUNDLE = {
    "video_id": "abcdefghijk",
    "url": "https://www.youtube.com/watch?v=abcdefghijk",
    "title": "Jak działa inflacja",
    "channel": "Ekonomia",
    "duration_sec": 600,
    "published_at": "2026-01-01",
    "yt_tags": ["ekonomia", "inflacja"],
    "yt_chapters": [{"t": 0, "title": "Wstęp"}, {"t": 300, "title": "Stopy"}],
    "description": "Autor opowiada o inflacji.",
    "yt_categories": ["Education"],
    "language": "pl",
    "transcript": {"source": "youtube_auto", "language": "pl", "segments": SEGS},
}

REPORT = {
    "one_line": "Krótko o inflacji.",
    "about": "O inflacji i stopach.",
    "text_summary": "Ceny rosną, banki podnoszą stopy.",
    "visual_summary": "Wykres CPI.",
    "key_points": ["ceny rosną", "stopy w górę"],
    "life_applications": ["oszczędzaj"],
    "action_items": [],
    "tags": ["Ekonomia", "#inflacja"],
    "video_type": "explainer_visual",
    "chapters": [{"t": 0, "title": "Wstęp"}],
    "notable_quotes": [{"t": 0, "quote": "Inflacja to wzrost cen."}],
    "related_suggestions": ["stopy procentowe"],
    "confidence": 0.8,
    "frames_described": [{"t": 12, "caption": "wykres CPI"}],
}


def bundle(**over):
    return {**BUNDLE, **over}


class FakeClient:
    """Stands in for llm.Client: only _record is needed by analyse()."""

    def __init__(self):
        self.recorded = []

    def _record(self, ref, model, i, o, seconds=0.0):
        self.recorded.append((ref, model, i, o))


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def payload_for(answer, prompt_tokens=1500, out_tokens=700, thoughts=100):
    """A generateContent response whose first candidate's text is ``answer``."""
    text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"promptTokenCount": prompt_tokens, "candidatesTokenCount": out_tokens,
                          "thoughtsTokenCount": thoughts},
    }


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    """Never reach the network and never read a real key."""
    import requests

    from ytdigest import shared

    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_GENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("network call: requests.post"))
    monkeypatch.setattr("time.sleep", lambda *_: None)
    monkeypatch.setattr(shared, "vbench_prompts", lambda: None)
    return monkeypatch


def serve(monkeypatch, *responses):
    """Queue up generateContent responses (dicts) and return the list of sent bodies."""
    import requests

    seen = []
    queue = list(responses)

    def fake_post(url, params=None, json=None, timeout=None):
        seen.append({"url": url, "params": params, "body": json, "timeout": timeout})
        item = queue.pop(0)
        if isinstance(item, FakeResponse):
            return item
        return FakeResponse(200, item)

    monkeypatch.setattr(requests, "post", fake_post)
    return seen


def run(client=None, cfg=None, fps=0.5, hint="", b=None, model="gemini-2.5-flash-lite"):
    from ytdigest import gemini

    return gemini.analyse(client or FakeClient(), model, b or bundle(), cfg or {"report_language": "pl"},
                          fps, hint)


def test_malformed_json_from_model_is_a_controlled_llm_error(monkeypatch):
    """A model answer with braces but broken JSON must not leak JSONDecodeError
    into the pipeline: callers only handle LLMError."""
    from ytdigest import llm

    serve(monkeypatch, payload_for('{"one_line": "x", "about": }'))

    with pytest.raises(llm.LLMError) as exc:
        run()

    assert not isinstance(exc.value, json.JSONDecodeError)


# --- _prompt(): what the model is told -------------------------------------------------


def prompt(b=None, lang="pl", hint=""):
    from ytdigest import gemini

    return gemini._prompt(b or bundle(), lang, hint)


def test_prompt_carries_the_metadata_and_asks_for_the_artistic_shortcut():
    p = prompt()

    assert "Jak działa inflacja" in p
    assert "Ekonomia" in p
    assert "set is_artistic true" in p
    assert "frames_described" in p


def test_prompt_lists_every_video_type_the_pipeline_accepts():
    from ytdigest.routing import VIDEO_TYPES

    p = prompt()

    assert "First decide video_type from: " + ", ".join(VIDEO_TYPES) in p


def test_prompt_includes_the_transcript_hint_only_when_there_is_one():
    hint = "[00:00] Inflacja to wzrost cen.\n[00:10] Banki podnoszą stopy."

    with_hint = prompt(hint=hint)
    without_hint = prompt(hint="")

    assert "A transcript is available" in with_hint
    assert "Banki podnoszą stopy." in with_hint
    assert "A transcript is available" not in without_hint


def test_prompt_truncates_a_long_transcript_hint_to_3000_chars():
    p = prompt(hint="x" * 5000)

    assert "x" * 3000 in p
    assert "x" * 3001 not in p


def test_prompt_switches_the_field_instructions_language():
    assert "Polish" in prompt(lang="pl")
    assert "English" in prompt(lang="en")


# --- analyse(): request shape, usage, answer handling -----------------------------------


def test_analyse_returns_the_normalised_report_and_the_described_frames(monkeypatch):
    serve(monkeypatch, payload_for(REPORT))

    rep, frames = run()

    assert rep["one_line"] == "Krótko o inflacji."
    assert rep["video_type"] == "explainer_visual"
    assert rep["is_artistic"] is False
    assert rep["tags"] == ["ekonomia", "inflacja"]  # normalise() lowercases and strips '#'
    assert frames == [{"t": 12, "caption": "wykres CPI"}]


def test_analyse_posts_to_the_gemini_endpoint_for_the_given_model(monkeypatch):
    seen = serve(monkeypatch, payload_for(REPORT))

    run(model="gemini-2.5-flash")

    assert seen[0]["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    )
    assert seen[0]["params"] == {"key": "dummy-test-key"}
    assert seen[0]["timeout"] == 900


def test_analyse_sends_the_url_as_file_data_so_google_fetches_the_video(monkeypatch):
    seen = serve(monkeypatch, payload_for(REPORT))

    run(fps=1.0)

    parts = seen[0]["body"]["contents"][0]["parts"]
    assert parts[0]["file_data"] == {"file_uri": BUNDLE["url"], "mime_type": "video/*"}
    assert parts[0]["video_metadata"] == {"fps": 1.0}
    assert seen[0]["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert seen[0]["body"]["generationConfig"]["mediaResolution"] == "MEDIA_RESOLUTION_LOW"


def test_analyse_clamps_the_frame_rate_to_the_api_minimum(monkeypatch):
    seen = serve(monkeypatch, payload_for(REPORT))

    run(fps=0.0)

    assert seen[0]["body"]["contents"][0]["parts"][0]["video_metadata"] == {"fps": 0.05}


def test_analyse_records_usage_including_thinking_tokens(monkeypatch):
    serve(monkeypatch, payload_for(REPORT, prompt_tokens=1500, out_tokens=700, thoughts=100))
    client = FakeClient()

    run(client=client)

    assert client.recorded == [("gemini-url:gemini-2.5-flash-lite", "gemini-2.5-flash-lite", 1500, 800)]


def test_analyse_accepts_a_video_type_outside_the_allowed_list_as_other(monkeypatch):
    serve(monkeypatch, payload_for({**REPORT, "video_type": "unboxing_magic"}))

    rep, _ = run()

    assert rep["video_type"] == "other"


def test_analyse_parses_json_wrapped_in_a_markdown_fence(monkeypatch):
    fenced = "Here is the report:\n```json\n" + json.dumps(REPORT, ensure_ascii=False) + "\n```"
    serve(monkeypatch, payload_for(fenced))

    rep, frames = run()

    assert rep["one_line"] == "Krótko o inflacji."
    assert frames == [{"t": 12, "caption": "wykres CPI"}]


def test_analyse_ignores_frames_without_a_timestamp(monkeypatch):
    payload = {**REPORT, "frames_described": [{"t": 5, "caption": "slajd"}, {"caption": "bez czasu"}, "śmieć", {"t": 30}]}
    serve(monkeypatch, payload_for(payload))

    _, frames = run()

    assert frames == [{"t": 5, "caption": "slajd"}, {"t": 30}]


def test_analyse_marks_artistic_content_and_forces_the_music_type(monkeypatch):
    serve(monkeypatch, payload_for({**REPORT, "video_type": "vlog_travel", "is_artistic": True}))

    rep, _ = run()

    assert rep["is_artistic"] is True
    assert rep["video_type"] == "music_artistic"


def test_analyse_treats_the_music_type_as_artistic_even_without_the_flag(monkeypatch):
    payload = {k: v for k, v in REPORT.items() if k != "is_artistic"}
    serve(monkeypatch, payload_for({**payload, "video_type": "music_artistic"}))

    rep, _ = run()

    assert rep["is_artistic"] is True
    assert rep["video_type"] == "music_artistic"


# --- analyse(): failures ------------------------------------------------------------------


def test_analyse_refuses_to_run_without_a_key(monkeypatch):
    from ytdigest import llm

    monkeypatch.delenv("GEMINI_API_KEY")

    with pytest.raises(llm.LLMError, match="GEMINI_API_KEY not set"):
        run()


def test_analyse_does_not_retry_a_client_error(monkeypatch):
    from ytdigest import llm

    seen = serve(monkeypatch, FakeResponse(400, text="bad request body"))

    with pytest.raises(llm.LLMError, match="gemini-2.5-flash-lite -> 400"):
        run()

    assert len(seen) == 1


def test_analyse_retries_transient_statuses_then_succeeds(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("unreachable"))
    seen = serve(
        monkeypatch,
        FakeResponse(429, text="rate limited"),
        FakeResponse(503, text="overloaded"),
        payload_for(REPORT),
    )

    rep, _ = run()

    assert len(seen) == 3
    assert rep["one_line"] == "Krótko o inflacji."


def test_analyse_gives_up_after_four_transient_failures(monkeypatch):
    from ytdigest import llm

    seen = serve(monkeypatch, *[FakeResponse(429, text="rate limited") for _ in range(4)])

    with pytest.raises(llm.LLMError, match="kept failing"):
        run()

    assert len(seen) == 4


def test_analyse_reports_a_blocked_prompt_as_a_controlled_error(monkeypatch):
    from ytdigest import llm

    serve(monkeypatch, {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})

    with pytest.raises(llm.LLMError) as exc:
        run()

    assert "no candidates" in str(exc.value)
    assert "SAFETY" in str(exc.value)


def test_analyse_treats_an_empty_answer_as_a_controlled_error(monkeypatch):
    from ytdigest import llm

    serve(monkeypatch, payload_for(""))

    with pytest.raises(llm.LLMError, match="no JSON object in model output"):
        run()


# --- the vbench branch: the benchmark supplies its own prompt ------------------------------


def test_analyse_uses_the_vbench_prompt_when_the_benchmark_is_armed(monkeypatch, hermetic):
    from ytdigest import shared

    seen = serve(monkeypatch, payload_for(REPORT))

    class Benchmark:
        VIDEO_URL_USER = "Watch {title} and report."

        @staticmethod
        def report_system(lang):
            return f"BENCH SYSTEM {lang}"

    monkeypatch.setattr(shared, "vbench_prompts", lambda: Benchmark)

    run()

    body = seen[0]["body"]
    assert body["system_instruction"]["parts"][0]["text"] == "BENCH SYSTEM pl"
    assert body["contents"][0]["parts"][1]["text"] == "Watch Jak działa inflacja and report."
