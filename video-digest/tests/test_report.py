"""Contract tests for ``ytdigest/report.py`` — the transcript -> report stage.

Hermetic by construction: no network, no API keys, no ``~/.hermes/ytdigest/config.yaml``
(the ``cfg`` fixture from ``conftest.py`` pins data dir and config path to ``tmp_path``).
The model is replaced by a recorder that keeps every prompt, so the tests pin what
the stage *asks* and what it *returns*, not how it is wired internally.

Every test name states the contract it protects.
"""

from __future__ import annotations

import pytest

from ytdigest import report, shared


class FakeClient:
    """Stands in for ``llm.Client``: records prompts, replays canned answers."""

    def __init__(self, reply: dict | None = None, notes=None):
        self.reply = dict(reply or {})
        self.calls: list[tuple] = []
        self._notes = notes or (lambda system, user: "N[" + user[:12] + "]")

    def complete(self, ref, system, user, images=None, json_mode=False, max_tokens=4000):
        self.calls.append(("complete", ref, system, user, max_tokens))
        return self._notes(system, user)

    def json(self, ref, system, user, images=None, max_tokens=4000):
        self.calls.append(("json", ref, system, user, max_tokens))
        return dict(self.reply)

    @property
    def json_calls(self):
        return [c for c in self.calls if c[0] == "json"]

    @property
    def complete_calls(self):
        return [c for c in self.calls if c[0] == "complete"]


class FakeVP:
    """Looks like ``vbench.prompts``: the benchmark's stage prompts."""

    NOTES_SYSTEM = "VBENCH NOTES SYSTEM"

    def __init__(self):
        self.seen: dict = {}

    def report_system(self, lang):
        self.seen["system_lang"] = lang
        return f"VBENCH SYSTEM ({lang})"

    def report_user(self, meta, video_type, body, frames):
        self.seen["meta"] = meta
        self.seen["video_type"] = video_type
        self.seen["body"] = body
        self.seen["frames"] = frames
        return "VBENCH USER"


@pytest.fixture(autouse=True)
def _no_vbench(monkeypatch):
    """Default to ytdigest's own prompts; vbench tests opt in explicitly."""
    monkeypatch.setattr(shared, "vbench_prompts", lambda: None)


def make_bundle(**over) -> dict:
    b = {
        "title": "Jak działa inflacja",
        "channel": "Ekonomia",
        "duration_sec": 120,
        "language": "pl",
        "published_at": "2026-01-01",
        "yt_tags": ["ekonomia", "pieniadze"],
        "description": "opis od autora",
        "yt_chapters": [],
        "frames": [],
        "transcript": {
            "source": "youtube_manual",
            "language": "pl",
            "segments": [{"start": 0.0, "end": 5.0, "text": "Inflacja to wzrost cen."}],
        },
    }
    b.update(over)
    return b


def seg(start, text, end=None):
    return {"start": float(start), "end": float(end if end is not None else start + 1), "text": text}


# --------------------------------------------------------------------------- language


def test_lang_name_maps_the_two_supported_report_languages():
    assert report._lang_name("pl") == "Polish"
    assert report._lang_name("en") == "English"


def test_lang_name_falls_back_to_polish_for_unknown_or_empty_codes():
    assert report._lang_name("de") == "Polish"
    assert report._lang_name("") == "Polish"


# --------------------------------------------------------------------------- timeline


def test_timeline_marks_the_first_segment_and_then_only_after_the_every_threshold():
    out = report._timeline([seg(0, "raz"), seg(10, "dwa"), seg(20, "trzy"), seg(40, "cztery")])
    assert out.count("[") == 2
    assert "[00:00]" in out and "[00:40]" in out
    assert "[00:10]" not in out and "[00:20]" not in out


def test_timeline_accepts_a_custom_every_threshold():
    out = report._timeline([seg(0, "a"), seg(10, "b"), seg(20, "c")], every=15)
    assert "[00:00]" in out and "[00:20]" in out and "[00:10]" not in out


def test_timeline_renders_markers_as_mm_ss_beyond_one_minute():
    assert "[01:15]" in report._timeline([seg(75, "po minucie")])


def test_timeline_keeps_segment_text_in_order_and_strips_trailing_space():
    out = report._timeline([seg(0, "pierwszy"), seg(1, "drugi")])
    assert out.startswith("[00:00] pierwszy drugi")
    assert not out.endswith(" ")


def test_timeline_of_no_segments_is_empty():
    assert report._timeline([]) == ""


# --------------------------------------------------------------------------- frames


def test_frames_text_skips_frames_that_have_neither_caption_nor_screen_text():
    frames = [{"t": 0, "caption": "slajd"}, {"t": 5}, {"t": 9, "caption": "", "ocr_text": ""}]
    out = report._frames_text(frames)
    assert out.count("\n") == 0
    assert "slajd" in out


def test_frames_text_prefixes_each_line_with_its_timestamp():
    assert report._frames_text([{"t": 65, "caption": "wykres"}]).startswith("[01:05] wykres")


def test_frames_text_appends_screen_text_and_caps_it_at_300_chars():
    out = report._frames_text([{"t": 3, "caption": "kod", "ocr_text": "x" * 400}])
    assert "| on screen: " in out
    assert out.count("x") == 300


def test_frames_text_says_so_when_there_is_nothing_visual():
    assert report._frames_text([]) == "(no visual analysis)"
    assert report._frames_text([{"t": 1}]) == "(no visual analysis)"


# --------------------------------------------------------------------------- meta


def test_meta_carries_title_channel_duration_and_publish_date():
    meta = report._meta(make_bundle())
    for expected in ("title: Jak działa inflacja", "channel: Ekonomia", "duration_sec: 120",
                     "published_at: 2026-01-01"):
        assert expected in meta


def test_meta_caps_youtube_tags_at_twenty_and_description_at_4000_chars():
    meta = report._meta(make_bundle(yt_tags=[f"t{i}" for i in range(25)], description="Z" * 5000))
    assert "t19" in meta and "t20" not in meta
    assert meta.count("Z") == 4000


def test_meta_renders_chapters_as_seconds_and_title():
    meta = report._meta(make_bundle(yt_chapters=[{"t": 30.7, "title": "Wstęp"}, {"t": 90, "title": "Koniec"}]))
    assert "chapters: 30s Wstęp; 90s Koniec" in meta


def test_meta_tolerates_a_missing_description_and_chapters():
    b = make_bundle()
    b.pop("description")
    b.pop("yt_chapters")
    meta = report._meta(b)
    assert "description (the author's own text and links): " in meta
    assert "chapters: " in meta


# --------------------------------------------------------------------------- instructions


def test_instructions_names_the_output_language_and_the_video_type():
    text = report._instructions("pl", "explainer_visual")
    assert "Write every text field in Polish" in text
    assert "The video type is explainer_visual" in text


def test_instructions_switches_to_english_when_asked():
    assert "Write every text field in English" in report._instructions("en", "interview")


def test_instructions_lists_the_report_fields_the_model_must_return():
    text = report._instructions("pl", "x")
    for field in ("one_line", "about", "text_summary", "visual_summary", "key_points",
                  "life_applications", "action_items", "tags", "chapters",
                  "notable_quotes", "related_suggestions", "confidence"):
        assert field in text


def test_instructions_ask_for_the_time_marks_the_timeline_produced():
    assert "[mm:ss]" in report._instructions("pl", "x")


# --------------------------------------------------------------------------- normalise


def test_normalise_strips_list_items_and_drops_the_empty_ones():
    rep = report.normalise({"key_points": ["  a  ", "", "   ", "b"]}, "t", make_bundle(), "pl")
    assert rep["key_points"] == ["a", "b"]


def test_normalise_wraps_a_scalar_answer_instead_of_dropping_it():
    rep = report.normalise({"action_items": "jeden krok"}, "t", make_bundle(), "pl")
    assert rep["action_items"] == ["jeden krok"]


def test_normalise_normalises_tags_to_sorted_lowercase_topic_names():
    rep = report.normalise({"tags": ["#Ekonomia", "inflacja", "Ekonomia", "ceny, stopy"]},
                           "t", make_bundle(), "pl")
    assert rep["tags"] == ["ceny  stopy", "ekonomia", "inflacja"]


def test_normalise_caps_a_single_tag_at_ninety_chars():
    rep = report.normalise({"tags": ["z" * 200]}, "t", make_bundle(), "pl")
    assert rep["tags"] == ["z" * 90]


def test_normalise_coerces_text_fields_to_stripped_strings():
    rep = report.normalise({"one_line": "  x  ", "about": None}, "t", make_bundle(), "pl")
    assert rep["one_line"] == "x"
    assert rep["about"] == ""
    assert rep["text_summary"] == "" and rep["visual_summary"] == ""


def test_normalise_keeps_only_chapters_that_carry_a_time():
    rep = report.normalise({"chapters": [{"t": 0, "title": "a"}, {"title": "bez czasu"}, "smiec"]},
                           "t", make_bundle(), "pl")
    assert rep["chapters"] == [{"t": 0, "title": "a"}]


def test_normalise_prefers_the_authors_youtube_chapters_over_the_model_ones():
    yt = [{"t": 12, "title": "od autora"}]
    rep = report.normalise({"chapters": [{"t": 0, "title": "od modelu"}]}, "t",
                           make_bundle(yt_chapters=yt), "pl")
    assert rep["chapters"] == yt


def test_normalise_keeps_only_notable_quotes_that_have_text():
    rep = report.normalise({"notable_quotes": [{"t": 1, "quote": "cytat"}, {"t": 2}, {"t": 3, "quote": ""}]},
                           "t", make_bundle(), "pl")
    assert rep["notable_quotes"] == [{"t": 1, "quote": "cytat"}]


def test_normalise_stamps_video_type_language_and_the_not_artistic_flag():
    rep = report.normalise({"video_type": "cokolwiek", "is_artistic": True, "language": "en"},
                           "tutorial", make_bundle(), "pl")
    assert rep["video_type"] == "tutorial"
    assert rep["is_artistic"] is False
    assert rep["language"] == "pl"


def test_normalise_parses_confidence_and_defaults_missing_or_junk_to_half():
    assert report.normalise({"confidence": "0.7"}, "t", make_bundle(), "pl")["confidence"] == 0.7
    assert report.normalise({}, "t", make_bundle(), "pl")["confidence"] == 0.5
    assert report.normalise({"confidence": "duzo"}, "t", make_bundle(), "pl")["confidence"] == 0.5


def test_normalise_caps_confidence_at_three_tenths_without_a_transcript():
    b = make_bundle(transcript={"source": "none", "language": "pl", "segments": []})
    assert report.normalise({"confidence": 0.9}, "t", b, "pl")["confidence"] == 0.3
    # a report that is already less certain keeps its own, lower, value
    assert report.normalise({"confidence": 0.1}, "t", b, "pl")["confidence"] == 0.1


# --------------------------------------------------------------------------- artistic stub


def test_artistic_stub_carries_the_reason_and_marks_the_report_artistic():
    stub = report.artistic_stub(make_bundle(), "utwór muzyczny, nie ma czego streścić")
    assert stub["about"] == "utwór muzyczny, nie ma czego streścić"
    assert stub["is_artistic"] is True
    assert stub["video_type"] == "music_artistic"
    assert stub["confidence"] == 1.0


def test_artistic_stub_is_empty_but_list_shaped_and_keeps_bundle_language():
    b = make_bundle(language="en", yt_chapters=[{"t": 0, "title": "Intro"}])
    stub = report.artistic_stub(b, "powod")
    assert stub["language"] == "en"
    assert stub["chapters"] == [{"t": 0, "title": "Intro"}]
    for key in ("key_points", "life_applications", "action_items", "tags",
                "notable_quotes", "related_suggestions"):
        assert stub[key] == []
    assert stub["one_line"] == "" and stub["text_summary"] == "" and stub["visual_summary"] == ""


def test_artistic_stub_without_youtube_chapters_has_an_empty_chapter_list():
    assert report.artistic_stub(make_bundle(), "powod")["chapters"] == []


# --------------------------------------------------------------------------- transcript text


def test_transcript_text_joins_every_segment_into_one_plain_string():
    b = make_bundle(transcript={"source": "x", "language": "pl",
                                "segments": [seg(0, "Ala"), seg(1, "ma"), seg(2, "kota.")]})
    assert report.transcript_text(b) == "Ala ma kota."


# --------------------------------------------------------------------------- build


def test_build_sends_metadata_transcript_frames_and_instructions_to_the_model(cfg):
    b = make_bundle(frames=[{"t": 4, "caption": "slajd z wykresem"}])
    client = FakeClient({"one_line": "x"})
    report.build(client, "ollama-cloud:m", b, cfg, "explainer_visual")
    assert len(client.json_calls) == 1
    kind, ref, system, user, max_tokens = client.json_calls[0]
    assert ref == "ollama-cloud:m"
    assert system == report.SYSTEM
    assert max_tokens == 5000
    for expected in ("title: Jak działa inflacja", "description (the author's own text and links): opis od autora",
                     "Transcript:", "Inflacja to wzrost cen.", "slajd z wykresem",
                     "Write every text field in Polish"):
        assert expected in user


def test_build_returns_a_normalised_report_stamped_with_the_video_type(cfg):
    client = FakeClient({"one_line": "  sedno  ", "tags": ["#Ekonomia"], "confidence": "0.6"})
    rep = report.build(client, "ollama-cloud:m", make_bundle(), cfg, "tutorial")
    assert rep["one_line"] == "sedno"
    assert rep["tags"] == ["ekonomia"]
    assert rep["confidence"] == 0.6
    assert rep["video_type"] == "tutorial" and rep["language"] == "pl"


def test_build_follows_the_configured_report_language(cfg):
    c = dict(cfg, report_language="en")
    client = FakeClient({"one_line": "x"})
    rep = report.build(client, "ollama-cloud:m", make_bundle(), c, "tutorial")
    assert "Write every text field in English" in client.json_calls[0][3]
    assert rep["language"] == "en"


def test_build_maps_a_long_transcript_part_by_part_before_writing_the_report(cfg):
    c = dict(cfg, max_transcript_chars=60, chunk_chars=20)
    b = make_bundle(transcript={"source": "youtube_auto", "language": "pl",
                                "segments": [seg(i, "slow%d" % i) for i in range(10)]})
    client = FakeClient({"one_line": "x"})
    report.build(client, "ollama-cloud:m", b, c, "tutorial")
    notes_calls = client.complete_calls
    assert len(notes_calls) >= 2
    assert all(call[4] == 2500 for call in notes_calls)
    assert ("Part 1 of %d" % len(notes_calls)) in notes_calls[0][3]
    assert ("Part %d of %d" % (len(notes_calls), len(notes_calls))) in notes_calls[-1][3]
    assert "Notes from the transcript, part by part" in client.json_calls[0][3]


def test_build_says_there_is_no_transcript_and_lowers_confidence(cfg):
    b = make_bundle(transcript={"source": "none", "language": "pl", "segments": []})
    client = FakeClient({"one_line": "x", "confidence": 0.9})
    rep = report.build(client, "ollama-cloud:m", b, cfg, "tutorial")
    assert "(no transcript available)" in client.json_calls[0][3]
    assert rep["confidence"] == 0.3


# --------------------------------------------------------------------------- build: vbench route


def test_build_uses_the_vbench_prompts_when_the_benchmark_is_available(cfg, monkeypatch):
    vp = FakeVP()
    monkeypatch.setattr(shared, "vbench_prompts", lambda: vp)
    client = FakeClient({"one_line": "x"})
    b = make_bundle(audio={"music_ratio": 0.42})
    rep = report.build(client, "ollama-cloud:m", b, cfg, "explainer_visual")

    assert vp.seen["system_lang"] == "pl"
    assert vp.seen["video_type"] == "explainer_visual"
    assert vp.seen["meta"]["title"] == "Jak działa inflacja"
    assert vp.seen["meta"]["duration_min"] == pytest.approx(2.0)
    assert vp.seen["meta"]["music_ratio"] == 0.42
    assert "Inflacja to wzrost cen." in vp.seen["body"]
    assert client.json_calls[0][2] == "VBENCH SYSTEM (pl)"
    assert client.json_calls[0][3] == "VBENCH USER"
    assert rep["video_type"] == "explainer_visual"


def test_build_vbench_frames_carry_caption_and_screen_text_and_drop_silent_frames(cfg, monkeypatch):
    vp = FakeVP()
    monkeypatch.setattr(shared, "vbench_prompts", lambda: vp)
    b = make_bundle(frames=[{"t": 7, "caption": "schemat", "ocr_text": "for i in x:", "visual_only": "v"},
                            {"t": 9, "ocr_text": "bez podpisu"}])
    report.build(FakeClient({}), "ollama-cloud:m", b, cfg, "tutorial")
    assert vp.seen["frames"] == [{"t": 7, "caption": "schemat", "on_screen_text": "for i in x:",
                                  "visual_only": "v"}]


def test_build_vbench_says_there_is_no_transcript_when_segments_are_empty(cfg, monkeypatch):
    vp = FakeVP()
    monkeypatch.setattr(shared, "vbench_prompts", lambda: vp)
    b = make_bundle(transcript={"source": "none", "language": "pl", "segments": []})
    report.build(FakeClient({}), "ollama-cloud:m", b, cfg, "tutorial")
    assert vp.seen["body"] == "(no transcript available)"


def test_build_vbench_condenses_a_long_transcript_with_the_benchmark_notes_prompt(cfg, monkeypatch):
    vp = FakeVP()
    monkeypatch.setattr(shared, "vbench_prompts", lambda: vp)
    c = dict(cfg, max_transcript_chars=60, chunk_chars=20)
    b = make_bundle(transcript={"source": "youtube_auto", "language": "pl",
                                "segments": [seg(i, "slow%d" % i) for i in range(10)]})
    client = FakeClient({})
    report.build(client, "ollama-cloud:m", b, c, "tutorial")

    notes_calls = client.complete_calls
    assert len(notes_calls) >= 2
    assert all(call[2] == FakeVP.NOTES_SYSTEM for call in notes_calls)
    assert all(call[4] == 2500 for call in notes_calls)
    assert "N[" in vp.seen["body"]  # the report sees the notes, not the raw transcript
