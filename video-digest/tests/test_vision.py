"""Hermetic tests for ytdigest.vision: the frame-captioning prompt, the transcript
window around each frame, and the per-batch failure handling.

No network, no real key: the client is a stub that records what it was asked and
returns canned JSON. Frames live in a tmp directory so no real video is needed.
"""

import pytest

from ytdigest import vision

SEGS = [
    {"start": 0.0, "end": 9.0, "text": "Inflacja to wzrost cen."},
    {"start": 10.0, "end": 19.0, "text": "Banki podnoszą stopy."},
    {"start": 100.0, "end": 109.0, "text": "Na koniec wykres CPI."},
]


class StubClient:
    """Records every call; returns queued answers or raises queued errors."""

    def __init__(self, *answers):
        self.calls = []
        self.queue = list(answers)

    def json(self, ref, system, user, images=None, max_tokens=None):
        self.calls.append(
            {"ref": ref, "system": system, "user": user, "images": images, "max_tokens": max_tokens}
        )
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def frames_of(*times, ocr=None):
    out = []
    for n, t in enumerate(times, 1):
        out.append({"t": float(t), "path": f"f{n:02d}.jpg", "reason": "scene", "ocr_text": ocr})
    return out


@pytest.fixture(autouse=True)
def no_benchmark(monkeypatch):
    from ytdigest import shared

    monkeypatch.setattr(shared, "vbench_prompts", lambda: None)


def answer(*captions, on_screen=None):
    """A model answer: one entry per image, in order."""
    frames = []
    for n, cap in enumerate(captions, 1):
        frames.append({
            "n": n,
            "caption": cap,
            "on_screen_text": (on_screen or {}).get(n, ""),
            "adds_information": True,
        })
    return {"frames": frames}


# --- _context(): the speech window around one frame ---------------------------------------


def test_context_takes_only_segments_within_the_window():
    assert vision._context(SEGS, 15.0) == "Inflacja to wzrost cen. Banki podnoszą stopy."


def test_context_is_empty_when_no_segment_is_near():
    assert vision._context(SEGS, 500.0) == ""


def test_context_is_empty_for_an_empty_transcript():
    assert vision._context([], 12.0) == ""


def test_context_includes_a_segment_that_ends_exactly_at_the_window_edge():
    segs = [{"start": 0.0, "end": 10.0, "text": "krawędź"}]  # end == t - window

    assert vision._context(segs, 30.0, window=20.0) == "krawędź"


def test_context_includes_a_segment_that_starts_exactly_at_the_window_edge():
    segs = [{"start": 40.0, "end": 49.0, "text": "krawędź"}]  # start == t + window

    assert vision._context(segs, 20.0, window=20.0) == "krawędź"


def test_context_excludes_a_segment_just_outside_the_window():
    segs = [{"start": 40.1, "end": 49.0, "text": "za daleko"}]

    assert vision._context(segs, 20.0, window=20.0) == ""


def test_context_truncates_to_600_chars():
    segs = [{"start": 0.0, "end": 10.0, "text": "y" * 900}]

    ctx = vision._context(segs, 5.0)

    assert len(ctx) == 600


# --- describe(): batching and what the model is asked -------------------------------------


def test_describe_sends_one_call_per_batch(tmp_path):
    client = StubClient(answer("a", "b", "c", "d", "e", "f"), answer("g"))
    frames = frames_of(*range(7))

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl", batch=6)

    assert len(client.calls) == 2


def test_describe_sends_absolute_image_paths_and_the_token_budget(tmp_path):
    client = StubClient(answer("slajd"))
    frames = frames_of(5)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    call = client.calls[0]
    assert call["images"] == [tmp_path / "f01.jpg"]
    assert call["max_tokens"] == 1500
    assert call["system"] == vision.SYSTEM
    assert call["ref"] == "vision:x"


def test_describe_labels_each_image_with_its_timestamp_and_nearby_speech(tmp_path):
    client = StubClient(answer("slajd"))
    frames = frames_of(15)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    user = client.calls[0]["user"]
    assert 'Image 1 at 15s. Speech around it: "Inflacja to wzrost cen. Banki podnoszą stopy."' in user
    assert "in Polish" in user


def test_describe_asks_for_english_captions_when_the_report_language_is_english(tmp_path):
    client = StubClient(answer("slide"))

    vision.describe(client, "vision:x", tmp_path, frames_of(1), SEGS, "en")

    assert "in English" in client.calls[0]["user"]


def test_describe_does_nothing_at_all_without_frames(tmp_path):
    client = StubClient()

    vision.describe(client, "vision:x", tmp_path, [], SEGS, "pl")

    assert client.calls == []


# --- describe(): writing the answer back into the frames ----------------------------------


def test_describe_fills_caption_and_adds_information(tmp_path):
    client = StubClient(answer("wykres CPI rośnie"))
    frames = frames_of(15)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["caption"] == "wykres CPI rośnie"
    assert frames[0]["adds_information"] is True


def test_describe_keeps_the_ocr_text_that_was_already_read(tmp_path):
    client = StubClient(answer("slajd", on_screen={1: "tekst z modelu"}))
    frames = frames_of(15, ocr="tekst z OCR")

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["ocr_text"] == "tekst z OCR"


def test_describe_uses_the_model_text_when_ocr_did_not_run(tmp_path):
    client = StubClient(answer("slajd", on_screen={1: "tekst z modelu"}))
    frames = frames_of(15)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["ocr_text"] == "tekst z modelu"


def test_describe_leaves_a_frame_caption_empty_when_the_model_skips_it(tmp_path):
    client = StubClient(answer("tylko pierwszy"))
    frames = frames_of(15, 45)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["caption"] == "tylko pierwszy"
    assert frames[1]["caption"] is None


def test_describe_matches_answers_by_the_n_field_not_by_position(tmp_path):
    client = StubClient({"frames": [{"n": 2, "caption": "drugi"}, {"n": 1, "caption": "pierwszy"}]})
    frames = frames_of(15, 45)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert [f["caption"] for f in frames] == ["pierwszy", "drugi"]


# --- describe(): one bad batch must not sink the rest --------------------------------------


def test_describe_records_the_error_and_keeps_the_other_batches(tmp_path):
    client = StubClient(RuntimeError("model refused"), answer("drugi batch"))
    frames = frames_of(*range(7))

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl", batch=6)

    assert frames[0]["caption"] is None
    assert frames[0]["error"] == "model refused"
    assert frames[6]["caption"] == "drugi batch"


def test_describe_truncates_a_long_error_message(tmp_path):
    client = StubClient(RuntimeError("x" * 500))

    frames = frames_of(1)
    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert len(frames[0]["error"]) == 200


# --- the vbench branch: the benchmark supplies the prompt ---------------------------------


class StubBenchmark:
    VISION_SYSTEM = "BENCH VISION"

    def __init__(self):
        self.used = []

    def vision_user(self, title, items):
        self.used.append((title, items))
        return "bench prompt"


def test_describe_uses_the_benchmark_prompt_when_the_benchmark_is_armed(tmp_path, monkeypatch):
    from ytdigest import shared

    bench = StubBenchmark()
    monkeypatch.setattr(shared, "vbench_prompts", lambda: bench)
    client = StubClient({"frames": [{"caption": "kadr", "visual_only": "wykres"}]})
    frames = frames_of(15)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl", title="Tytuł")

    assert bench.used == [("Tytuł", [(15.0, "Inflacja to wzrost cen. Banki podnoszą stopy.")])]
    assert client.calls[0]["system"] == "BENCH VISION"
    assert client.calls[0]["user"] == "bench prompt"
    assert frames[0]["visual_only"] == "wykres"
    assert frames[0]["adds_information"] is True


def test_vbench_branch_tolerates_a_batch_error(tmp_path, monkeypatch):
    from ytdigest import shared

    monkeypatch.setattr(shared, "vbench_prompts", lambda: StubBenchmark())
    client = StubClient(ValueError("boom"))
    frames = frames_of(1)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["caption"] is None
    assert frames[0]["error"] == "boom"


def test_vbench_branch_leaves_missing_answers_empty(tmp_path, monkeypatch):
    from ytdigest import shared

    monkeypatch.setattr(shared, "vbench_prompts", lambda: StubBenchmark())
    client = StubClient({"frames": []})
    frames = frames_of(15)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["caption"] is None
    assert frames[0]["visual_only"] == ""
    assert frames[0]["adds_information"] is False


def test_vbench_branch_fills_ocr_text_when_ocr_did_not_run(tmp_path, monkeypatch):
    from ytdigest import shared

    monkeypatch.setattr(shared, "vbench_prompts", lambda: StubBenchmark())
    client = StubClient({"frames": [{"caption": "kadr", "on_screen_text": "tekst z kadru"}]})
    frames = frames_of(15)

    vision.describe(client, "vision:x", tmp_path, frames, SEGS, "pl")

    assert frames[0]["ocr_text"] == "tekst z kadru"
