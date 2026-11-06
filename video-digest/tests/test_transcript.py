"""Contract tests for the transcript routing core (``transcript.get``).

These tests pin *behaviour*, not implementation: which step wins, in which order
the configured steps are tried, when audio is (not) fetched, and exactly what
the caller gets when every backend fails. They are fully hermetic: the fetch
layer is faked, the ASR backends are either faked or forced to be unimportable
through ``sys.modules``, and an autouse fixture makes any socket use fail, so
this file passes on a host without network, ffmpeg or the heavy ``local-asr``
extras.

Why this file exists: on 2026-10-24 both ASR backends were missing in the
deployment venv (``faster_whisper`` / ``onnx_asr`` -> ModuleNotFoundError), so
every video without captions silently ended as ``source: "none"`` and nothing
caught it, because no test touched the routing at all.
``test_every_missing_backend_is_reported_as_an_error`` is the regression pin.

Pinned contract detail (measured, ``transcript.py:167``): on success ``get()``
returns ``{"source", **backend_result}`` and *drops* the errors collected from
earlier failing steps; ``errors`` is only present in the ``source: "none"``
result. ``test_success_does_not_expose_partial_errors`` states that explicitly
so a future behaviour change is a visible decision, not an accident.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from ytdigest import fetch, transcript

INFO = {
    "id": "abcdefghijk",
    "webpage_url": "https://www.youtube.com/watch?v=abcdefghijk",
    "title": "Test video",
    "duration": 600,  # 10 min, far below the local cap
    "language": "pl-PL",
}

VTT = """WEBVTT

00:00:00.000 --> 00:00:02.000
dzień dobry

00:00:02.000 --> 00:00:04.000
dzisiaj o AI
"""

SEGMENTS = [
    {"start": 0.0, "end": 2.0, "text": "dzień dobry"},
    {"start": 2.0, "end": 4.0, "text": "dzisiaj o AI"},
]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Any attempt to open a socket fails the test loudly."""

    def boom(*args, **kwargs):
        raise AssertionError("transcript tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket.socket, "connect_ex", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


@pytest.fixture(autouse=True)
def _no_asr_modules(monkeypatch):
    """Backends are unimportable unless a test explicitly fakes them.

    ``None`` in ``sys.modules`` makes ``import faster_whisper`` raise ImportError,
    which is exactly the deployment situation these tests must stay honest about.
    """
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    monkeypatch.setitem(sys.modules, "onnx_asr", None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


class AudioSpy:
    """Lazy ``audio_getter`` that records how often it was asked for audio."""

    def __init__(self, path: Path):
        self.path = path
        self.calls = 0

    def __call__(self) -> Path:
        self.calls += 1
        return self.path


def fake_fetch(monkeypatch, work: Path, calls: list[str], captions: dict | None = None) -> None:
    """Fake the fetch layer; every call is appended to ``calls``.

    ``captions`` maps a step name (``manual``/``auto``) to the ``(lang, kind)``
    tuple ``fetch.pick_caption`` would return; missing steps have no track.
    """
    tracks = captions or {}

    def pick_caption(info, kind, langs):
        calls.append(f"pick:{kind}")
        return tracks.get(kind)

    def download_caption(url, lang_key, kind, out_dir, cookies=None):
        calls.append(f"caption:{kind}")
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"captions.{kind}.vtt"
        path.write_text(VTT, encoding="utf-8")
        return path

    def download_audio(url, out_dir, cookies=None):
        calls.append("download_audio")
        return work / "audio.m4a"

    monkeypatch.setattr(fetch, "pick_caption", pick_caption)
    monkeypatch.setattr(fetch, "download_caption", download_caption)
    monkeypatch.setattr(fetch, "download_audio", download_audio)


def fake_backend(calls: list[str], name: str, result: dict | None = None, raise_exc: BaseException | None = None):
    """Fake ASR backend that logs ``name`` and either returns ``result`` or raises."""

    def run(*args, **kwargs):
        calls.append(name)
        if raise_exc is not None:
            raise raise_exc
        return dict(result or {})

    return run


def order(cfg: dict, *steps: str) -> dict:
    return {**cfg, "transcript_order": list(steps)}


def name_for(step: str) -> str:
    """Backend function name a routing step calls (for call-log assertions)."""
    return {"groq": "whisper_groq", "parakeet": "parakeet", "local": "whisper_local"}[step]


# --- captions win, and nothing below them is touched -------------------------


def test_manual_caption_short_circuits_every_whisper_step(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls, {"manual": ("pl", "manual")})
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", {"segments": SEGMENTS}))
    monkeypatch.setattr(transcript, "parakeet", fake_backend(calls, "parakeet", {"segments": SEGMENTS}))
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS}))

    out = transcript.get(dict(INFO), cfg, tmp_path, audio_getter=AudioSpy(tmp_path / "a.m4a"))

    assert out == {"source": "youtube_manual", "language": "pl", "segments": SEGMENTS}
    assert calls == ["pick:manual", "caption:manual"]


def test_caption_success_never_calls_download_audio(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls, {"manual": ("pl", "manual")})
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", {"segments": SEGMENTS}))

    out = transcript.get(dict(INFO), cfg, tmp_path)  # no audio_getter -> fetch.download_audio would be used

    assert out["source"] == "youtube_manual"
    assert "download_audio" not in calls


def test_audio_getter_is_lazy_and_reused_across_backends(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)  # no captions at all
    spy = AudioSpy(tmp_path / "a.m4a")
    monkeypatch.setattr(
        transcript,
        "whisper_groq",
        fake_backend(calls, "groq", raise_exc=transcript.TranscriptUnavailable("GROQ_API_KEY not set")),
    )
    monkeypatch.setattr(transcript, "parakeet", fake_backend(calls, "parakeet", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "manual", "groq", "parakeet"), tmp_path, audio_getter=spy)

    assert out["source"] == "parakeet_local"
    assert spy.calls == 1  # downloaded once, then reused by the second backend
    assert calls == ["pick:manual", "groq", "parakeet"]


# --- configured order -------------------------------------------------------


def test_steps_are_tried_in_configured_order(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(
        transcript,
        "whisper_groq",
        fake_backend(calls, "groq", raise_exc=transcript.TranscriptUnavailable("GROQ_API_KEY not set")),
    )
    monkeypatch.setattr(transcript, "parakeet", fake_backend(calls, "parakeet", {"segments": []}))
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS, "language": "pl"}))

    tcfg = order(cfg, "manual", "groq", "parakeet", "local", "auto")
    out = transcript.get(dict(INFO), tcfg, tmp_path)

    assert out["source"] == "whisper_local"
    assert calls == ["pick:manual", "download_audio", "groq", "parakeet", "local"]


def test_reordered_config_changes_which_step_runs_first(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", {"segments": SEGMENTS, "language": "en"}))
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "local", "groq"), tmp_path)

    assert out["source"] == "whisper_local"
    assert calls == ["download_audio", "local"]


def test_success_does_not_expose_partial_errors(tmp_path, cfg, monkeypatch):
    """Measured contract (transcript.py:167): errors are dropped on success."""
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(
        transcript,
        "whisper_groq",
        fake_backend(calls, "groq", raise_exc=transcript.TranscriptUnavailable("GROQ_API_KEY not set")),
    )
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "groq", "local"), tmp_path)

    assert out["source"] == "whisper_local"
    assert "errors" not in out


# --- 40-minute guard for local Whisper -------------------------------------


def test_local_step_is_skipped_when_video_exceeds_the_cap(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS}))

    out = transcript.get({**INFO, "duration": 41 * 60}, order(cfg, "local"), tmp_path)

    assert out == {
        "source": "none",
        "language": "pl",
        "segments": [],
        "errors": ["local: video longer than 40 min"],
    }
    assert calls == []  # the cap is checked before any audio download


def test_local_step_runs_at_the_cap_boundary(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get({**INFO, "duration": 40 * 60}, order(cfg, "local"), tmp_path)

    assert out["source"] == "whisper_local"
    assert calls == ["download_audio", "local"]


# --- failure handling: one error entry per step, never an exception ----------


def test_every_missing_backend_is_reported_as_an_error(tmp_path, cfg, monkeypatch):
    fake_fetch(monkeypatch, tmp_path, [])

    out = transcript.get(dict(INFO), cfg, tmp_path)

    assert out == {
        "source": "none",
        "language": "pl",
        "segments": [],
        "errors": [
            "manual: no track",
            "groq: GROQ_API_KEY not set",
            "parakeet: onnx-asr not installed",
            "local: faster-whisper not installed",
            "auto: no track",
        ],
    }


def test_missing_faster_whisper_is_an_error_entry_not_an_exception(tmp_path, cfg, monkeypatch):
    fake_fetch(monkeypatch, tmp_path, [])

    out = transcript.get(dict(INFO), order(cfg, "local"), tmp_path)

    assert out == {"source": "none", "language": "pl", "segments": [], "errors": ["local: faster-whisper not installed"]}


def test_missing_faster_whisper_lets_the_next_step_win(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "local", "groq"), tmp_path)

    assert out["source"] == "whisper_groq"
    assert calls == ["download_audio", "groq"]


def test_unexpected_backend_exception_is_reported_with_type(tmp_path, cfg, monkeypatch):
    fake_fetch(monkeypatch, tmp_path, [])
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend([], "groq", raise_exc=RuntimeError("ffmpeg exploded")))

    out = transcript.get(dict(INFO), order(cfg, "groq"), tmp_path)

    assert out == {"source": "none", "language": "pl", "segments": [], "errors": ["groq: RuntimeError: ffmpeg exploded"]}


def test_unexpected_backend_exception_lets_the_next_step_win(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", raise_exc=RuntimeError("ffmpeg exploded")))
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "groq", "local"), tmp_path)

    assert out["source"] == "whisper_local"
    assert calls == ["download_audio", "groq", "local"]


# --- an empty result is a failure, not a success ----------------------------


def test_empty_backend_segments_are_treated_as_failure(tmp_path, cfg, monkeypatch):
    fake_fetch(monkeypatch, tmp_path, [])
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend([], "groq", {"segments": [], "language": "en"}))

    out = transcript.get(dict(INFO), order(cfg, "groq"), tmp_path)

    assert out == {"source": "none", "language": "pl", "segments": [], "errors": ["groq: empty"]}


def test_empty_backend_segments_fall_through_to_the_next_step(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", {"segments": [], "language": "en"}))
    monkeypatch.setattr(transcript, "whisper_local", fake_backend(calls, "local", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "groq", "local"), tmp_path)

    assert out["source"] == "whisper_local"
    assert calls == ["download_audio", "groq", "local"]


def test_empty_caption_file_is_treated_as_failure(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls, {"manual": ("pl", "manual")})
    monkeypatch.setattr(fetch, "download_caption", lambda *a, **k: None)

    out = transcript.get(dict(INFO), order(cfg, "manual"), tmp_path)

    assert out == {"source": "none", "language": "pl", "segments": [], "errors": ["manual: empty"]}
    assert calls == ["pick:manual"]


# --- unknown steps are survivable ------------------------------------------


def test_unknown_step_is_recorded_as_an_error(tmp_path, cfg, monkeypatch):
    fake_fetch(monkeypatch, tmp_path, [])

    out = transcript.get(dict(INFO), order(cfg, "bogus"), tmp_path)

    assert out == {"source": "none", "language": "pl", "segments": [], "errors": ["bogus: unknown step"]}


def test_unknown_step_does_not_stop_the_loop(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "whisper_groq", fake_backend(calls, "groq", {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, "bogus", "groq"), tmp_path)

    assert out["source"] == "whisper_groq"
    assert "groq" in calls


# --- source labels travel into bundles/reports: pin the mapping -------------


def test_source_names_mapping_is_pinned():
    assert transcript.SOURCE_NAMES == {
        "manual": "youtube_manual",
        "auto": "youtube_auto",
        "groq": "whisper_groq",
        "local": "whisper_local",
        "parakeet": "parakeet_local",
    }


@pytest.mark.parametrize(
    ("step", "expected_source"),
    [("groq", "whisper_groq"), ("parakeet", "parakeet_local"), ("local", "whisper_local")],
)
def test_backend_steps_report_the_documented_source(tmp_path, cfg, monkeypatch, step, expected_source):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    for name in ("whisper_groq", "parakeet", "whisper_local"):
        monkeypatch.setattr(transcript, name, fake_backend(calls, name, {"segments": SEGMENTS, "language": "pl"}))

    out = transcript.get(dict(INFO), order(cfg, step), tmp_path)

    assert out["source"] == expected_source
    assert calls == ["download_audio", name_for(step)]


def test_auto_caption_source_and_language_code(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls, {"auto": ("pl-orig", "auto")})

    out = transcript.get(dict(INFO), order(cfg, "auto"), tmp_path)

    assert out["source"] == "youtube_auto"
    assert out["language"] == "pl"  # the "-orig" suffix is stripped
    assert out["segments"] == SEGMENTS


def test_parakeet_language_falls_back_to_the_info_hint(tmp_path, cfg, monkeypatch):
    calls: list[str] = []
    fake_fetch(monkeypatch, tmp_path, calls)
    monkeypatch.setattr(transcript, "parakeet", fake_backend(calls, "parakeet", {"segments": SEGMENTS, "language": None}))

    out = transcript.get(dict(INFO), order(cfg, "parakeet"), tmp_path)

    assert out["source"] == "parakeet_local"
    assert out["language"] == "pl"
