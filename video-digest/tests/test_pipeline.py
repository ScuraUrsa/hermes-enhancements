"""End-to-end flow with YouTube, models and Notion faked; ffmpeg is real."""
import json

import pytest

from ytdigest import fetch, gemini, llm, notion, pipeline, transcript

INFO = {
    "id": "abcdefghijk", "title": "Jak działa inflacja", "channel": "Ekonomia", "duration": 40,
    "upload_date": "20260101", "language": "pl", "description": "opis", "tags": ["ekonomia"],
    "categories": ["Education"], "chapters": [], "subtitles": {}, "automatic_captions": {},
}
SEGS = [{"start": 0.0, "end": 9.0, "text": "Inflacja to wzrost cen."}, {"start": 10.0, "end": 19.0, "text": "Banki podnoszą stopy."}]
REPORT = {"one_line": "Krótko o inflacji.", "about": "O inflacji.", "text_summary": "Ceny rosną.",
          "visual_summary": "Wykresy.", "key_points": ["a", "b"], "life_applications": ["oszczędzaj"],
          "action_items": ["sprawdź lokatę"], "tags": ["Ekonomia", "#inflacja"], "chapters": [{"t": 0, "title": "Start"}],
          "notable_quotes": [{"t": 0, "quote": "Inflacja to wzrost cen."}], "related_suggestions": ["stopy procentowe"],
          "confidence": 0.8}


class FakeNotion:
    pages = {}

    def __init__(self, ds, token=None, session=None):
        self.ds = ds


@pytest.fixture
def faked(monkeypatch):
    calls = {"notion": [], "gemini": 0, "llm": []}
    monkeypatch.setattr(fetch, "probe", lambda url, cookies=None: dict(INFO))
    monkeypatch.setattr(transcript, "get", lambda info, cfg, work, cookies=None, audio_getter=None:
                        {"source": "whisper_groq", "language": "pl", "segments": list(SEGS)})
    monkeypatch.setattr(notion, "Notion", FakeNotion)

    def write_report(nt, bundle_dir, bundle, rep, run, cfg):
        calls["notion"].append((bundle, rep, run))
        return "https://www.notion.so/page"

    monkeypatch.setattr(notion, "write_report", write_report)

    def fake_json(self, ref, system, user, images=None, max_tokens=4000):
        calls["llm"].append(ref)
        self._record(ref, llm.split_ref(ref)[1], 1000, 200)
        if "classify" in system or "video_type from" in user or "Video types (pick exactly one)" in system:
            return {"video_type": "explainer_visual", "is_artistic": False, "confidence": 0.9}
        if images:
            return {"frames": [{"n": i + 1, "caption": f"kadr {i}", "adds_information": True} for i in range(len(images))]}
        return dict(REPORT)

    monkeypatch.setattr(llm.Client, "json", fake_json)
    return calls


def test_gemini_url_path(cfg, faked, monkeypatch):
    def fake_analyse(client, model, bundle, cfg, fps, hint=""):
        faked["gemini"] += 1
        client._record("gemini-url:" + model, model, 20000, 1500)
        from ytdigest.report import normalise
        return normalise(dict(REPORT), "explainer_visual", bundle, "pl"), [{"t": 12, "caption": "wykres CPI"}]

    monkeypatch.setattr(gemini, "analyse", fake_analyse)
    cfg["gemini_enabled"] = True
    res = pipeline.process("https://youtu.be/abcdefghijk", cfg, log=lambda m: None)
    assert res["status"] == "done" and res["notion_url"]
    assert faked["gemini"] == 1
    bundle, rep, run = faked["notion"][0]
    assert bundle["schema"] == "video_bundle/v1" and bundle["published_at"] == "2026-01-01"
    assert rep["tags"] == ["ekonomia", "inflacja"]
    assert run["visual"] and run["cost_usd"] > 0
    saved = json.loads((tmp := pipeline.Path(cfg["data_dir"]) / "bundles" / "abcdefghijk" / "bundle.json").read_text())
    assert saved["transcript"]["source"] == "whisper_groq"
    assert "Krótko o inflacji" in res["report_md"]


def test_gemini_is_off_by_default(cfg, faked, monkeypatch, synthetic_video):
    monkeypatch.setattr(gemini, "analyse", lambda *a, **k: pytest.fail("Gemini must not be called"))
    monkeypatch.setattr(fetch, "download_video", lambda url, out, h, cookies=None: synthetic_video)
    res = pipeline.process("abcdefghijk", cfg, log=lambda m: None)
    assert res["status"] == "done" and not any("gemini" in m for m in res["models"])


def test_falls_back_to_frames_when_gemini_fails(cfg, faked, monkeypatch, synthetic_video):
    cfg["gemini_enabled"] = True
    def boom(*a, **k):
        raise llm.LLMError("GEMINI_API_KEY not set")

    monkeypatch.setattr(gemini, "analyse", boom)
    monkeypatch.setattr(fetch, "download_video", lambda url, out, h, cookies=None: synthetic_video)
    res = pipeline.process("abcdefghijk", cfg, log=lambda m: None)
    assert res["status"] == "done"
    bundle, rep, run = faked["notion"][-1]
    assert bundle["frames"] and all(f["caption"] for f in bundle["frames"])
    assert any("gemma4:31b" in r for r in faked["llm"])  # vision model used
    assert run["visual"] and not run.get("degraded")


def _frames_path(monkeypatch, synthetic_video):
    monkeypatch.setattr(gemini, "analyse", lambda *a, **k: (_ for _ in ()).throw(llm.LLMError("no key")))
    monkeypatch.setattr(fetch, "download_video", lambda url, out, h, cookies=None: synthetic_video)


def test_retired_vision_model_falls_back(cfg, faked, monkeypatch, synthetic_video):
    _frames_path(monkeypatch, synthetic_video)
    real = llm.Client.json

    def json_410_for_main(self, ref, system, user, images=None, max_tokens=4000):
        if images and "gemma4:31b" in ref:
            raise llm.LLMError(f"{ref} -> 410: model was retired")
        return real(self, ref, system, user, images=images, max_tokens=max_tokens)

    monkeypatch.setattr(llm.Client, "json", json_410_for_main)
    res = pipeline.process("abcdefghijk", cfg, log=lambda m: None)
    _, _, run = faked["notion"][-1]
    assert res["status"] == "done" and run["visual"] and run["vision_model"].endswith("glm-5.3-flash")
    assert not res["degraded"]


def test_all_frames_failing_marks_run_degraded(cfg, faked, monkeypatch, synthetic_video):
    _frames_path(monkeypatch, synthetic_video)
    real = llm.Client.json

    def json_no_vision(self, ref, system, user, images=None, max_tokens=4000):
        if images:
            raise llm.LLMError(f"{ref} -> 410: retired")
        return real(self, ref, system, user, images=images, max_tokens=max_tokens)

    monkeypatch.setattr(llm.Client, "json", json_no_vision)
    logs = []
    res = pipeline.process("abcdefghijk", cfg, log=logs.append)
    _, _, run = faked["notion"][-1]
    assert res["degraded"] == "vision" and run["visual"] is False
    assert any("visual analysis failed for all frames" in m for m in logs)
    assert "transcript only" in res["report_md"] or "tylko na transkrypcie" in res["report_md"]


def test_music_video_is_listed_without_any_model_call(cfg, faked, monkeypatch):
    monkeypatch.setattr(fetch, "probe", lambda url, cookies=None: {**INFO, "title": "Band - Hit (Official Video)", "categories": ["Music"]})
    res = pipeline.process("abcdefghijk", cfg, log=lambda m: None)
    assert res["status"] == "artistic" and res["cost_usd"] == 0
    assert faked["llm"] == []
    _, rep, _ = faked["notion"][-1]
    assert rep["is_artistic"]


def test_safe_process_reports_failures(cfg, monkeypatch):
    def broken(url, cookies=None):
        raise RuntimeError("Sign in to confirm you're not a bot")

    monkeypatch.setattr(fetch, "probe", broken)
    res = pipeline.safe_process("abcdefghijk", cfg, write_notion=False)
    assert res["status"] == "failed" and "bot" in res["error"]
