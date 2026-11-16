"""Loud degradation: a transcript that ended with source=none must be announced,
not silent. The warning is one line and carries every recorded error."""
import pytest
from ytdigest import transcript

NONE_TR = {"source": "none", "language": None, "segments": [],
           "errors": ["manual: no track", "groq: GROQ_API_KEY not set"]}


def test_warning_lists_every_recorded_error():
    warn = transcript.degradation_warning(NONE_TR)
    assert warn is not None and "\n" not in warn
    assert "WARNING" in warn and "transcript" in warn
    assert "manual: no track" in warn and "groq: GROQ_API_KEY not set" in warn


def test_no_warning_when_a_transcript_exists():
    ok = {"source": "whisper_groq", "language": "pl", "segments": [{"start": 0, "end": 1, "text": "hi"}],
          "errors": ["manual: no track"]}
    assert transcript.degradation_warning(ok) is None


def test_warning_even_without_recorded_errors():
    blank = {"source": "none", "language": None, "segments": [], "errors": []}
    warn = transcript.degradation_warning(blank)
    assert warn is not None and "\n" not in warn and "WARNING" in warn


def test_missing_source_is_treated_as_lost():
    assert transcript.degradation_warning({}) is not None


# --- pipeline wiring: a lost transcript must be announced in the log ---

from ytdigest import fetch, llm, notion, pipeline  # noqa: E402
from test_pipeline import FakeNotion, INFO, REPORT  # noqa: E402

LOST = {"source": "none", "language": None, "segments": [],
        "errors": ["manual: no track", "groq: GROQ_API_KEY not set", "local: ffmpeg boom"]}


@pytest.fixture
def faked_lost(monkeypatch):
    """Same fakes as test_pipeline.faked, but every transcription step fails."""
    calls = {"notion": []}
    monkeypatch.setattr(fetch, "probe", lambda url, cookies=None: dict(INFO))
    monkeypatch.setattr(transcript, "get",
                        lambda info, cfg, work, cookies=None, audio_getter=None: dict(LOST))
    monkeypatch.setattr(notion, "Notion", FakeNotion)
    monkeypatch.setattr(notion, "write_report", lambda *a, **k: "https://www.notion.so/page")

    def fake_json(self, ref, system, user, images=None, max_tokens=4000):
        self._record(ref, llm.split_ref(ref)[1], 1000, 200)
        if "classify" in system or "video_type from" in user or "Video types (pick exactly one)" in system:
            return {"video_type": "explainer_visual", "is_artistic": False, "confidence": 0.9}
        return dict(REPORT)

    monkeypatch.setattr(llm.Client, "json", fake_json)
    return calls


def test_lost_transcript_is_announced_loudly(cfg, faked_lost, monkeypatch, synthetic_video):
    monkeypatch.setattr(fetch, "download_video", lambda url, out, h, cookies=None: synthetic_video)
    logs = []
    res = pipeline.process("abcdefghijk", cfg, log=logs.append)
    assert res["status"] == "done"
    warnings = [m for m in logs if "WARNING" in m and "no transcript" in m]
    assert len(warnings) == 1
    assert "manual: no track" in warnings[0] and "groq: GROQ_API_KEY not set" in warnings[0]
    assert "local: ffmpeg boom" in warnings[0] and "\n" not in warnings[0]