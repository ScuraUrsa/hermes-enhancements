import json
import subprocess

from ytdigest import cleanup, llm, topics, youtube

AI = {"title": "Claude Code agents with MCP: build a coding workflow", "tags": ["ai", "llm", "python"],
      "channel": "Dev", "description": "We use Claude and an MCP server."}
COOK = {"title": "Pierogi jak u babci", "tags": ["kuchnia"], "channel": "Gotuj", "description": "Przepis."}


def test_ai_software_detection():
    assert topics.is_ai_software(AI)
    assert not topics.is_ai_software(COOK, "dzisiaj robimy ciasto")


def test_topic_routes(cfg):
    cfg["topic_routes"] = {"ai_software": {"report": "claude-code:sonnet", "vision": "claude-code:sonnet"},
                           "manual": {"report": "claude-code:haiku", "off": True}}
    base = {"report": "ollama-cloud:x", "vision": "ollama-cloud:y"}
    r, why = topics.apply(base, cfg, AI, "", "manual")  # manual is off -> topic decides
    assert why == "AI/software topic" and r["report"] == "claude-code:sonnet"
    r, why = topics.apply(base, cfg, COOK, "", "backlog")
    assert why is None and r == base


class FakeClient:
    def json(self, ref, system, user, max_tokens=0):
        n = int(user.split("Fix these ")[1].split(" ")[0])
        return {"paragraphs": [f"Zdanie numer {i}, z kropką. " * 8 for i in range(n)]}


def test_cleanup_keeps_times_and_counts():
    segs = [{"start": float(t), "end": t + 5.0, "text": "zdanie numer bez kropki"} for t in range(0, 200, 10)]
    paras = cleanup.paragraphs(FakeClient(), "x", segs, "pl")
    assert [p["t"] for p in paras] == [0.0, 60.0, 120.0, 180.0]
    assert all(p.get("clean") and "," in p["text"] for p in paras)


def test_claude_code_usage_is_recorded(cfg, monkeypatch, tmp_path):
    out = {"result": '{"ok": true}', "is_error": False, "total_cost_usd": 0.0123,
           "usage": {"input_tokens": 10, "output_tokens": 50, "cache_read_input_tokens": 9000,
                     "cache_creation_input_tokens": 1200}}
    seen = {}

    def fake_run(cmd, **kw):
        seen["env"] = kw["env"]
        return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-leak")
    monkeypatch.setattr(subprocess, "run", fake_run)
    c = llm.Client(cfg, ledger=tmp_path / "spend.jsonl", tag="compare")
    assert c.json("claude-code:sonnet", "s", "u") == {"ok": True}
    d = c.usage.by_model["claude-code:sonnet"]
    assert d["cache_read_tokens"] == 9000 and d["api_equiv_usd"] == 0.0123 and c.usage.cost_usd == 0
    assert "ANTHROPIC_API_KEY" not in seen["env"]


def test_add_to_playlist_creates_once(cfg, monkeypatch):
    calls = []

    def fake_call(method, path, token, **kw):
        calls.append((method, path))
        if path == "playlists" and method == "GET":
            return {"items": []}
        if path == "playlists":
            return {"id": "PLnew"}
        return {}

    monkeypatch.setattr(youtube, "token_for", lambda cfg, alias: "tok")
    monkeypatch.setattr(youtube, "_call", fake_call)
    assert youtube.add_to_playlist(cfg, "fjkazmierczak", "Przetworzone", "abcdefghijk")
    assert not youtube.add_to_playlist(cfg, "fjkazmierczak", "Przetworzone", "abcdefghijk")
    assert youtube.add_to_playlist(cfg, "fjkazmierczak", "Przetworzone", "bbbbbbbbbbb")
    assert calls.count(("POST", "playlists")) == 1 and calls.count(("POST", "playlistItems")) == 2


def test_talking_heads_go_to_haiku(cfg):
    cfg["topic_routes"] = {"ai_software": {"report": "claude-code:sonnet", "vision": "claude-code:sonnet"},
                           "manual": {"report": "claude-code:sonnet", "vision": "claude-code:sonnet"}}
    base = {"report": "ollama-cloud:x", "vision": "ollama-cloud:y"}
    r, why = topics.apply(base, cfg, AI, "", "backlog", "podcast_talk")
    assert r["report"] == "claude-code:haiku" and "talking head" in why
    r, _ = topics.apply(base, cfg, AI, "", "backlog", "tutorial_screen")
    assert r["report"] == "claude-code:sonnet"
    r, _ = topics.apply(base, cfg, AI, "", "manual", "podcast_talk")
    assert r["report"] == "claude-code:sonnet"


def test_call_maps_http_errors(monkeypatch):
    """youtube._call is the only place that talks to the API: pin its error mapping."""
    import requests

    class Resp:
        def __init__(self, status=200, text="", payload=None):
            self.status_code = status
            self.text = text
            self._payload = payload or {}

        def json(self):
            return self._payload

    seen = {}

    def fake_request(method, url, headers=None, timeout=None, **kw):
        seen.update({"method": method, "url": url, "auth": headers["Authorization"], "timeout": timeout})
        return fake_request.response

    monkeypatch.setattr(requests, "request", fake_request)

    fake_request.response = Resp(payload={"items": [{"id": "PL1"}]})
    assert youtube._call("GET", "playlists", "tok", params={"mine": "true"}) == {"items": [{"id": "PL1"}]}
    assert seen == {"method": "GET", "url": youtube.YT + "/playlists", "auth": "Bearer tok", "timeout": 30}

    fake_request.response = Resp(status=403, text="Request had insufficient authentication scopes")
    try:
        youtube._call("POST", "playlistItems", "tok")
    except PermissionError as exc:
        assert "read-only" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("403 with insufficient scope must raise PermissionError")

    fake_request.response = Resp(status=400, text='{"error": "bad part"}')
    try:
        youtube._call("POST", "playlistItems", "tok")
    except RuntimeError as exc:
        assert "YouTube playlistItems -> 400" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("4xx must raise RuntimeError")
