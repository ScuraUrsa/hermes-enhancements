import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from ytdigest import server
from ytdigest.queue import Queue


@pytest.fixture
def srv(tmp_path, monkeypatch, cfg):
    monkeypatch.setenv("YTDIGEST_TOKEN", "s3cret")
    ran = []
    monkeypatch.setattr(server.pipeline, "safe_process", lambda url, cfg, **k: ran.append(url) or {"video_id": url[-11:], "status": "done"})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(cfg, tmp_path / "q.db"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", tmp_path / "q.db", ran
    httpd.shutdown()


def _post(url, body, token=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_rejects_bad_token(srv):
    base, _, _ = srv
    assert _post(base + "/digest", {"url": "https://youtu.be/abcdefghijk", "token": "nope"})[0] == 401


def test_queue_endpoint(srv):
    base, qdb, _ = srv
    code, body = _post(base + "/queue", {"url": "https://youtu.be/abcdefghijk"}, token="s3cret")
    assert code == 202 and body["queued"] == "abcdefghijk"
    assert Queue(qdb).stats()["queued"]["count"] == 1


def test_digest_runs_now(srv):
    base, qdb, ran = srv
    with urllib.request.urlopen(base + "/digest?token=s3cret&url=https://youtu.be/abcdefghijk") as r:
        assert r.status == 202
    import time
    for _ in range(200):  # 10 s window: 2.5 s is flaky under full-suite load
        if ran:
            break
        time.sleep(0.05)
    assert ran == ["https://www.youtube.com/watch?v=abcdefghijk"]


def test_refuses_public_bind(cfg, tmp_path):
    with pytest.raises(SystemExit):
        server.serve(cfg, tmp_path / "q.db", "0.0.0.0", 0)


def test_mcp_bridge_lists_and_calls(monkeypatch, capsys):
    import io
    import json as _j

    from ytdigest import mcp_bridge

    monkeypatch.setattr(mcp_bridge, "_http", lambda m, p, params: {"status": "done", "report_md": "# R", "notion_url": "https://n"})
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "digest_youtube_video", "arguments": {"url": "dQw4w9WgXcQ"}}}]
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(_j.dumps(m) for m in msgs) + "\n"))
    mcp_bridge.main()
    out = [_j.loads(x) for x in capsys.readouterr().out.splitlines()]
    assert [o["id"] for o in out] == [1, 2, 3]
    assert len(out[1]["result"]["tools"]) == 2
    assert "# R" in out[2]["result"]["content"][0]["text"] and "https://n" in out[2]["result"]["content"][0]["text"]
