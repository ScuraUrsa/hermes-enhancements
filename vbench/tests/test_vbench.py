import json
from pathlib import Path

import pytest

from vbench import prompts as P
from vbench import route, scoring, stages
from vbench.bundle import Frame, Segment, Transcript, VideoBundle
from vbench.catalog import Catalog
from vbench.providers import Completion, Mock, ref_options, split_ref
from vbench.runner import Matrix, Runner
from vbench.transcribe import normalize_words, wer

ROOT = Path(__file__).resolve().parent.parent

LABEL = {
    "video_type": "tutorial_screen", "is_artistic": False, "language": "en",
    "key_points": [{"id": 1, "text": "Use uv to manage Python versions", "importance": 3},
                   {"id": 2, "text": "uv lock pins dependencies", "importance": 2},
                   {"id": 3, "text": "uv is written in Rust", "importance": 1}],
    "visual_facts": [{"id": 1, "t": 10.0, "text": "Terminal shows `uv python install 3.13`"}],
    "tags": ["python", "uv", "packaging"],
    "frame_captions": [{"t": 10.0, "caption": "terminal", "on_screen_text": "uv python install 3.13"}],
    "reviewed": True,
}

REPORT = {"one_line": "uv intro", "about": "a", "text_summary": "b", "visual_summary": "c",
          "key_points": ["x", "y", "z"], "life_applications": ["l"], "action_items": [], "tags": ["python", "uv", "rust"],
          "video_type": "tutorial_screen", "is_artistic": False, "language": "pl", "chapters": [], "notable_quotes": [],
          "related_suggestions": [], "confidence": 0.8}

JUDGE_REPORT = {"key_points": [{"id": 1, "verdict": "full"}, {"id": 2, "verdict": "partial"}, {"id": 3, "verdict": "missing"}],
                "visual_facts": [{"id": 1, "verdict": "full"}], "unsupported_claims": [], "tag_matches": 2,
                "usefulness": 4, "comment": "ok"}


@pytest.fixture(autouse=True)
def mock_responses():
    Mock.responses = {
        P.STAGE_MARK["classify"]: json.dumps({"video_type": "tutorial_screen", "is_artistic": False, "confidence": 0.9}),
        P.STAGE_MARK["vision"]: json.dumps({"frames": [{"t": 0, "caption": "terminal", "on_screen_text": "uv", "visual_only": ""}]}),
        P.STAGE_MARK["judge_report"]: "```json\n" + json.dumps(JUDGE_REPORT) + "\n```",
        P.STAGE_MARK["judge_vision"]: json.dumps({"visual_facts": [{"id": 1, "verdict": "full"}], "hallucinations": [],
                                                  "ocr_accuracy": 0.9}),
        P.STAGE_MARK["report"]: json.dumps(REPORT),
    }
    yield
    Mock.responses = {}


def make_bundle(root: Path, vid="vid1") -> VideoBundle:
    d = root / "bundles" / vid
    (d / "frames").mkdir(parents=True)
    (d / "frames" / "000001.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    b = VideoBundle(video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", title="uv in 5 minutes", channel="c",
                    duration_sec=300, transcript=Transcript("youtube_manual", "en",
                                                            [Segment(0, 5, "Hello, today: uv."), Segment(5, 9, "It is fast.")]),
                    frames=[Frame(10.0, "frames/000001.jpg", "scene")])
    b.save(d)
    (root / "labels").mkdir(exist_ok=True)
    (root / "labels" / f"{vid}.json").write_text(json.dumps(LABEL))
    return b


def test_bundle_roundtrip(tmp_path):
    b = make_bundle(tmp_path)
    b2 = VideoBundle.load(tmp_path / "bundles" / "vid1")
    assert b2.to_dict() == b.to_dict()
    assert b2.frame_path(b2.frames[0]).exists()
    assert b2.transcript.text().startswith("[0:00] Hello")
    assert b2.duration_bucket() == "medium"


def test_parse_json_variants():
    assert P.parse_json('<think>hmm</think>\n```json\n{"a": 1}\n```') == {"a": 1}
    assert P.parse_json('Sure! Here it is: {"a": "b \\" }", "c": [1]} trailing') == {"a": 'b " }', "c": [1]}
    with pytest.raises(ValueError):
        P.parse_json("no json here")


def test_ref_options():
    assert split_ref("ollama-cloud:qwen3-vl:235b-instruct") == ("ollama-cloud", "qwen3-vl:235b-instruct")
    assert split_ref("gemini-video:gemini-2.5-flash-lite@fps=0.2") == ("gemini-video", "gemini-2.5-flash-lite")
    assert ref_options("x:y@fps=0.2,frames=none") == {"fps": "0.2", "frames": "none"}


def test_cost_uses_base_ref_and_subscription_is_free():
    cat = Catalog.load()
    c = Completion("x", input_tokens=1_000_000, output_tokens=1_000_000)
    cost = cat.cost("ollama-cloud:deepseek-v4-flash@frames=none", c)
    assert cost.equiv_usd == pytest.approx(0.42)
    assert cost.marginal_usd == 0.0
    assert cat.cost("claude-code:haiku", Completion("x", 10, 10, reported_cost_usd=0.5)).equiv_usd == 0.5


def test_report_score_weights():
    s = scoring.score_report(LABEL, REPORT, JUDGE_REPORT, [])
    # key points weighted by importance: (3*1 + 2*0.5 + 0) / 6
    assert s["key_points"] == pytest.approx(4 / 6, abs=1e-3)
    assert s["visual"] == 1.0 and s["faithfulness"] == 1.0
    assert 0 < s["score"] < 100
    assert scoring.score_report(LABEL, REPORT, JUDGE_REPORT, ["missing about"])["score"] == 0.0
    worse = scoring.score_report(LABEL, REPORT, {**JUDGE_REPORT, "unsupported_claims": [{"severity": "major"}] * 2}, [])
    assert worse["score"] < s["score"]


def test_talk_videos_barely_weigh_visuals():
    talk = {**LABEL, "video_type": "podcast_talk"}
    no_vis = {**JUDGE_REPORT, "visual_facts": [{"id": 1, "verdict": "missing"}]}
    drop_talk = scoring.score_report(talk, REPORT, JUDGE_REPORT, [])["score"] - scoring.score_report(talk, REPORT, no_vis, [])["score"]
    drop_tut = scoring.score_report(LABEL, REPORT, JUDGE_REPORT, [])["score"] - scoring.score_report(LABEL, REPORT, no_vis, [])["score"]
    assert drop_talk < drop_tut


def test_classify_score():
    assert scoring.score_classify(LABEL, {"video_type": "tutorial_screen", "is_artistic": False})["score"] == 100
    assert scoring.score_classify(LABEL, {"video_type": "lecture_slides", "is_artistic": False})["score"] == 60
    assert scoring.score_classify(LABEL, {"video_type": "music_artistic", "is_artistic": True})["score"] == 0


def test_wer():
    assert wer(normalize_words("Ala ma kota."), normalize_words("ala ma kota")) == 0.0
    assert wer(["a", "b", "c", "d"], ["a", "x", "c"]) == 0.5
    assert normalize_words("[Music] Cześć, świecie!") == ["cześć", "świecie"]


def test_report_map_reduce_for_long_transcripts(tmp_path):
    cat = Catalog.load()
    cat.models["mock:echo"] = {"context": 50}  # tiny context forces chunking
    b = make_bundle(tmp_path)
    b.transcript.segments = [Segment(i, i + 1, "word " * 20) for i in range(30)]
    res = stages.report(cat, "mock:echo", b, "tutorial_screen", [])
    assert res.ok, res.problems
    assert len(res.calls) > 2  # several notes calls + the final report


def test_end_to_end_mock(tmp_path):
    for vid in ("vid1", "vid2"):
        make_bundle(tmp_path, vid)
    m = Matrix(bundles=tmp_path / "bundles", labels=tmp_path / "labels", out=tmp_path / "out",
               judges=["mock:echo", "mock:cheap"], workers=2,
               stages={"classify": ["mock:echo", "mock:cheap"], "vision": ["mock:echo", "mock:cheap"],
                       "report": ["mock:echo", "mock:cheap", "mock:cheap@frames=none"]})
    cat = Catalog.load()
    logs = []
    assert Runner(m, cat, logs.append).run() == 14
    assert Runner(m, cat, logs.append).run() == 0  # resumes: nothing left
    rows = route.load_rows([m.out])
    assert all(r["ok"] for r in rows), [r for r in rows if not r["ok"]]
    rep = [r for r in rows if r["stage"] == "report"]
    assert all(r["score"] > 0 and r["judge_spread"] == 0 for r in rep)
    routing = route.build_routing(rows, route.Rule(min_n=1))
    # identical quality, so the cheaper model wins every stage
    assert routing["tutorial_screen"]["report"].startswith("mock:cheap")
    assert routing["tutorial_screen"]["vision"] == "mock:cheap"
    assert routing["tutorial_screen"]["vision_fallback"] == "mock:echo"
    assert routing["default"]["classify"] == "mock:cheap"
    assert routing["music_artistic"]["skip"] is True
    md = route.leaderboard_md(rows, routing)
    assert "| tutorial_screen |" in md


def test_routing_respects_quality_bar():
    rows = []
    for i in range(3):
        rows.append({"video_id": f"v{i}", "stage": "report", "ref": "a:cheap", "video_type": "podcast_talk",
                     "score": 50.0, "ok": True, "equiv_usd": 0.001, "latency_sec": 1})
        rows.append({"video_id": f"v{i}", "stage": "report", "ref": "a:good", "video_type": "podcast_talk",
                     "score": 90.0, "ok": True, "equiv_usd": 0.01, "latency_sec": 1})
        rows.append({"video_id": f"v{i}", "stage": "report", "ref": "a:best", "video_type": "podcast_talk",
                     "score": 93.0, "ok": True, "equiv_usd": 0.10, "latency_sec": 1})
    r = route.build_routing(rows)
    assert r["podcast_talk"]["report"] == "a:good"  # within 92% of the best, far cheaper
    assert r["default"]["report"] == "a:good"


def test_video_url_model_replaces_vision_cost():
    rows = []
    for i in range(2):
        rows += [
            {"video_id": f"v{i}", "stage": "vision", "ref": "v:x", "video_type": "lecture_slides", "score": 80,
             "ok": True, "equiv_usd": 0.05, "latency_sec": 1},
            {"video_id": f"v{i}", "stage": "report", "ref": "r:x", "video_type": "lecture_slides", "score": 85,
             "ok": True, "equiv_usd": 0.01, "latency_sec": 1},
            {"video_id": f"v{i}", "stage": "video_url", "ref": "g:url", "video_type": "lecture_slides", "score": 84,
             "ok": True, "equiv_usd": 0.03, "latency_sec": 1},
        ]
    e = route.build_routing(rows)["lecture_slides"]
    assert e["report"] == "g:url" and e["vision"] is None  # 0.03 beats 0.01 + vision


def test_example_matrix_parses():
    m = Matrix.load(ROOT / "matrix.toml")
    cat = Catalog.load()
    for stage, refs in m.stages.items():
        if stage == "transcribe":
            continue
        for ref in refs:
            cat.model(ref)
            assert ref.split("@")[0] in cat.prices, ref


def test_openai_compat_request_shape(tmp_path):
    import http.server
    import threading

    from vbench.providers import ProviderConfig, get_model

    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["auth"] = self.headers.get("Authorization")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}],
                              "usage": {"prompt_tokens": 120, "completion_tokens": 7}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    img = tmp_path / "f.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    cfg = ProviderConfig("t", "openai_compat", base_url=f"http://127.0.0.1:{srv.server_port}/v1", api_key_env="VB_TEST_KEY")
    import os
    os.environ["VB_TEST_KEY"] = "k"
    c = get_model("t:qwen3-vl:235b-instruct", {"t": cfg}).complete("sys", "hi", [img], json_mode=True)
    assert c.text == '{"ok": true}' and c.input_tokens == 120 and c.output_tokens == 7
    assert seen["path"] == "/v1/chat/completions" and seen["auth"] == "Bearer k"
    body = seen["body"]
    assert body["model"] == "qwen3-vl:235b-instruct" and body["response_format"] == {"type": "json_object"}
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_claude_code_adapter_with_fake_cli(tmp_path):
    from vbench.providers import ProviderConfig, get_model

    fake = tmp_path / "claude"
    fake.write_text("#!/usr/bin/env python3\nimport json, sys, os\nprompt = sys.stdin.read()\n"
                    "assert '--model' in sys.argv and os.environ['CLAUDE_CONFIG_DIR']\n"
                    "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'result': 'R:' + str(len(prompt)),"
                    " 'usage': {'input_tokens': 10, 'cache_read_input_tokens': 5, 'output_tokens': 3}, 'total_cost_usd': 0.002,"
                    " 'num_turns': 2}))\n")
    fake.chmod(0o755)
    img = tmp_path / "f.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")
    cfg = ProviderConfig("claude-code", "claude_code", extra={"binary": str(fake)})
    c = get_model("claude-code:haiku", {"claude-code": cfg}).complete("sys", "describe", [img])
    assert c.text.startswith("R:") and c.input_tokens == 15 and c.reported_cost_usd == 0.002


def test_schemas_match():
    jsonschema = pytest.importorskip("jsonschema")
    sch = {n: json.loads((ROOT / "schemas" / f"{n}.schema.json").read_text()) for n in ("video_bundle", "video_report", "routing")}
    jsonschema.validate(json.loads((ROOT / "routing.json").read_text()), sch["routing"])
    jsonschema.validate(REPORT, sch["video_report"])


def test_unavailable_models_are_skipped(tmp_path, monkeypatch):
    import vbench.providers as prov

    make_bundle(tmp_path)
    cat = Catalog.load()
    monkeypatch.setattr(prov, "list_live_models",
                        lambda cfg: {"gemma3:27b", "deepseek-v4.1-flash"} if cfg.name == "ollama-cloud" else None)
    gone = cat.unavailable(["ollama-cloud:qwen3-vl:235b-instruct", "ollama-cloud:gemma3:27b@x=1", "mock:echo"])
    assert list(gone) == ["ollama-cloud:qwen3-vl:235b-instruct"]
    m = Matrix(bundles=tmp_path / "bundles", labels=tmp_path / "labels", out=tmp_path / "out", judges=["mock:echo"],
               stages={"vision": ["ollama-cloud:qwen3-vl:235b-instruct", "mock:cheap"]})
    r = Runner(m, cat, lambda s: None)
    r.drop_unavailable()
    assert r.m.stages["vision"] == ["mock:cheap"]


def test_routing_has_no_retired_models():
    r = json.loads((ROOT / "routing.json").read_text())
    refs = {v for e in r.values() if isinstance(e, dict) for k, v in e.items() if k in ("vision", "report", "classify", "vision_fallback")}
    assert not any("qwen3-vl" in str(x) for x in refs)
