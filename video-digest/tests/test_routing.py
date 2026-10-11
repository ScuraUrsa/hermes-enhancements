import json

from ytdigest import llm, routing


def test_defaults_without_vbench(cfg):
    t = routing.load(cfg)
    assert routing.route(t, "music_artistic")["skip"]
    assert routing.route(t, "unknown")["analyzer"] == "gemini_url"


def _write(tmp_path, table):
    p = tmp_path / "routing.json"
    p.write_text(json.dumps(table))
    return str(p)


def test_provisional_vbench_keeps_gemini_and_takes_fallback_models(cfg, tmp_path):
    cfg["routing_file"] = _write(tmp_path, {
        "schema": "vbench_routing/v1", "provisional": True,
        "default": {"classify": "ollama-cloud:gpt-oss:20b", "vision": "ollama-cloud:gemma3:27b", "report": "ollama-cloud:deepseek-v4-flash", "frames_per_min": 1.5, "skip": False},
        "podcast_talk": {"vision": "ollama-cloud:gemma3:12b", "frames_per_min": 0.5, "low_confidence": True, "evidence": {}},
        "transcribe": {"default": {"ref": "groq:whisper-large-v3-turbo"}},
    })
    t = routing.load(cfg)
    r = routing.route(t, "podcast_talk")
    assert r["analyzer"] == "gemini_url" and r["vision"] == "ollama-cloud:gemma3:12b" and r["frames_per_min"] == 0.5
    assert t["default"]["report"] == "ollama-cloud:deepseek-v4-flash"
    assert "transcribe" not in t and t["_transcribe_groq_model"] == "whisper-large-v3-turbo"


def test_final_vbench_table_drives_analyzer(cfg, tmp_path):
    cfg["routing_file"] = _write(tmp_path, {
        "provisional": False,
        "default": {"report": "ollama-cloud:deepseek-v4-flash"},
        "tutorial_screen": {"report": "gemini-video:gemini-2.5-flash@fps=1", "vision": None},
    })
    t = routing.load(cfg)
    assert routing.route(t, "other")["analyzer"] == "frames"
    tut = routing.route(t, "tutorial_screen")
    assert tut["analyzer"] == "gemini_url" and tut["url_model"] == "gemini:gemini-2.5-flash" and tut["url_fps"] == 1.0
    assert not tut["report"].startswith("gemini-video")


def test_ref_options():
    assert llm.split_ref("gemini-video:gemini-2.5-flash-lite@fps=0.2") == ("gemini-video", "gemini-2.5-flash-lite")
    assert llm.ref_options("gemini-video:x@fps=0.2") == {"fps": "0.2"}
    assert llm.split_ref("ollama-cloud:gpt-oss:120b") == ("ollama-cloud", "gpt-oss:120b")


def test_vbench_vision_fallback_is_read_per_type(tmp_path):
    import json as _json
    from ytdigest import routing as r
    p = tmp_path / "routing.json"
    p.write_text(_json.dumps({"provisional": True, "default": {"vision": "ollama-cloud:gemma3:27b",
                 "vision_fallback": "ollama-cloud:gemma3:4b"}}))
    table = r.load({"routing_file": str(p)})
    assert table["tutorial_screen"]["vision_fallback"] == "ollama-cloud:gemma3:4b"
