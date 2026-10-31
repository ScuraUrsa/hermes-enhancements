"""Hermetic tests for every ytdigest CLI subcommand handler.

Each ``cmd_*`` is called directly with a ``SimpleNamespace`` of parsed args and a
tmp-dir ``cfg``; heavy collaborators (yt-dlp, ffmpeg, providers, Notion, Home
Assistant, the HTTP server) are replaced by recorders, so the whole file runs
offline in well under a second.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import ytdigest
from ytdigest import cli, notion, queue as queue_mod, render, server

VID = "dQw4w9WgXcQ"
VID2 = "T3-uFayjJBI"


def qargs(**kw):
    """Parsed-arg namespace with every default the commands read."""
    base = dict(urls=[], file=None, now=False, backlog=False, account=None, playlist=None,
                refs="", notion_parent=None, title=None, out=None, days=730, ids_file=None,
                no_subs=False, skip_shorts=False, min_seconds=0, max_per_channel=0, queue=False,
                input=None, min_score=3, video=None, data_dir=None, notion=False, refetch=False,
                idle_only=False, only_user=False, max_videos=5, max_minutes=25,
                host="127.0.0.1", port=8765, json=False, no_notion=False, analyzer=None)
    base.update(kw)
    return SimpleNamespace(**base)


def rows(cfg):
    q = cli._q(cfg)
    return {r["video_id"]: dict(r) for r in q.db.execute("SELECT * FROM videos")}


# --------------------------------------------------------------------------- cmd_run

def test_run_done_queues_video_and_prints_report(cfg, monkeypatch, capsys):
    seen = {}

    def fake_process(url, cfg_, **kw):
        seen.update(url=url, **kw)
        return {"video_id": VID, "status": "done", "title": "Tytuł", "report_md": "# raport\n",
                "notion_url": "https://notion/page-1", "cost_usd": 0.25, "trace": "log"}

    monkeypatch.setattr(cli.pipeline, "safe_process", fake_process)
    monkeypatch.setattr(cli, "notify_ha", lambda cfg_, res: seen.setdefault("notified", res))

    rc = cli.cmd_run(cfg, SimpleNamespace(url=VID, no_notion=False, analyzer="frames", json=False))

    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip() == "# raport"
    assert seen["url"] == VID
    assert seen["write_notion"] is True
    assert seen["force_analyzer"] == "frames"
    assert seen["tag"] == "manual"
    assert seen["notified"]["video_id"] == VID

    row = rows(cfg)[VID]
    assert row["status"] == "done"
    assert row["priority"] == queue_mod.USER_PRIORITY
    assert row["account"] == "ręcznie"
    assert row["notion_url"] == "https://notion/page-1"
    assert row["cost_usd"] == pytest.approx(0.25)


def test_run_no_notion_skips_notion_write(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli.pipeline, "safe_process",
                        lambda url, cfg_, **kw: seen.update(kw) or
                        {"video_id": VID, "status": "done", "report_md": "", "cost_usd": 0})
    monkeypatch.setattr(cli, "notify_ha", lambda *a: None)
    assert cli.cmd_run(cfg, SimpleNamespace(url=VID, no_notion=True, analyzer=None, json=False)) == 0
    assert seen["write_notion"] is False


def test_run_failure_reports_and_leaves_queue_untouched(cfg, monkeypatch, capsys):
    monkeypatch.setattr(cli.pipeline, "safe_process",
                        lambda url, cfg_, **kw: {"video_id": VID, "status": "failed",
                                                 "error": "boom", "trace": "TB-line"})
    monkeypatch.setattr(cli, "notify_ha", lambda *a: None)

    assert cli.cmd_run(cfg, SimpleNamespace(url=VID, no_notion=False, analyzer=None, json=False)) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"FAILED {VID}: boom" in captured.err
    assert "TB-line" in captured.err
    assert rows(cfg) == {}


def test_run_json_output_hides_trace(cfg, monkeypatch, capsys):
    monkeypatch.setattr(cli.pipeline, "safe_process",
                        lambda url, cfg_, **kw: {"video_id": VID, "status": "done",
                                                 "report_md": "x", "cost_usd": 0, "trace": "SECRET"})
    monkeypatch.setattr(cli, "notify_ha", lambda *a: None)

    assert cli.cmd_run(cfg, SimpleNamespace(url=VID, no_notion=False, analyzer=None, json=True)) == 0
    out = capsys.readouterr().out
    assert "SECRET" not in out
    assert json.loads(out)["status"] == "done"


# --------------------------------------------------------------------------- cmd_add

def test_add_inline_urls_use_mid_priority(cfg, capsys):
    rc = cli.cmd_add(cfg, qargs(urls=[VID, f"https://youtu.be/{VID2}"]))
    out = capsys.readouterr().out
    assert rc == 0
    assert f"queued: {VID}" in out
    assert f"queued: {VID2}" in out
    stored = rows(cfg)
    assert stored[VID]["priority"] == queue_mod.BACKLOG_PRIORITY + 20
    assert stored[VID]["account"] == "ręcznie"


def test_add_now_uses_user_priority(cfg):
    assert cli.cmd_add(cfg, qargs(urls=[VID], now=True)) == 0
    assert rows(cfg)[VID]["priority"] == queue_mod.USER_PRIORITY


def test_add_backlog_uses_backlog_priority(cfg):
    assert cli.cmd_add(cfg, qargs(urls=[VID], backlog=True)) == 0
    assert rows(cfg)[VID]["priority"] == queue_mod.BACKLOG_PRIORITY


def test_add_reports_already_known(cfg, capsys):
    cli.cmd_add(cfg, qargs(urls=[VID]))
    capsys.readouterr()
    assert cli.cmd_add(cfg, qargs(urls=[VID])) == 0
    assert f"already known: {VID}" in capsys.readouterr().out


def test_add_skips_non_video_urls(cfg, capsys):
    assert cli.cmd_add(cfg, qargs(urls=["https://example.com/nie-film"])) == 0
    out = capsys.readouterr().out
    assert out.startswith("skipped (not a video): https://example.com/nie-film")
    assert rows(cfg) == {}


def test_add_from_file_reports_counts_and_ignores_comments(cfg, tmp_path, capsys):
    ids = tmp_path / "watch-later.txt"
    ids.write_text(f"# eksport\n\n{VID}\nhttps://youtu.be/{VID2}\n", encoding="utf-8")
    assert cli.cmd_add(cfg, qargs(file=str(ids))) == 0
    out = capsys.readouterr().out
    assert f"{ids}: 2 queued, 0 already known, 0 skipped" in out
    assert rows(cfg)[VID]["priority"] == queue_mod.BACKLOG_PRIORITY


def test_add_from_file_with_playlist_and_account(cfg, tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text(f"{VID}\n", encoding="utf-8")
    assert cli.cmd_add(cfg, qargs(file=str(ids), playlist="Kanał: X", account="koalamis6")) == 0
    row = rows(cfg)[VID]
    assert json.loads(row["playlists"]) == ["Kanał: X"]
    assert row["account"] == "koalamis6"


# --------------------------------------------------------------------------- cmd_compare

def test_compare_prints_results_and_optional_notion(cfg, monkeypatch, capsys, tmp_path):
    seen = {}

    def fake_run(cfg_, urls, refs, log=None):
        seen.update(urls=urls, refs=refs)
        return {"dir": str(tmp_path)}

    monkeypatch.setattr(cli.compare, "run", fake_run)
    monkeypatch.setattr(cli.compare, "publish_notion",
                        lambda res, refs, parent, title: seen.update(parent=parent, title=title) or "page-9")

    assert cli.cmd_compare(cfg, qargs(urls=[VID], refs="a:1, ,b:2", notion_parent="p1", title="T")) == 0
    out = capsys.readouterr().out
    assert seen["urls"] == [VID]
    assert seen["refs"] == ["a:1", "b:2"]
    assert f"results: {tmp_path}/results.json and comparison.md" in out
    assert "notion: page-9" in out
    assert seen["parent"] == "p1"


def test_compare_reads_first_column_of_file(cfg, monkeypatch, capsys, tmp_path):
    seen = {}
    listing = tmp_path / "list.tsv"
    listing.write_text(f"{VID}\tsome title\n# comment\n{VID2}\tother\n", encoding="utf-8")
    monkeypatch.setattr(cli.compare, "run",
                        lambda cfg_, urls, refs, log=None: seen.update(urls=urls) or {"dir": "/x"})
    assert cli.cmd_compare(cfg, qargs(file=str(listing), refs="m1")) == 0
    assert seen["urls"] == [VID, VID2]
    assert "notion:" not in capsys.readouterr().out


# --------------------------------------------------------------------------- cmd_discover

def test_discover_writes_default_tsv_and_queues(cfg, monkeypatch, capsys):
    seen = {}

    def fake_run(cfg_, account, days, out, **kw):
        seen.update(account=account, days=days, out=out, **kw)
        return {"rows": [{"video_id": VID, "title": "T", "channel": "Kanał A"}],
                "summary": {"videos": 1}}

    monkeypatch.setattr(cli.discover, "run", fake_run)
    assert cli.cmd_discover(cfg, qargs(account="koalamis6", days=30, queue=True)) == 0
    out = capsys.readouterr().out
    assert seen["out"] == Path(cfg["data_dir"]) / "discover_koalamis6_30d.tsv"
    assert seen["include_subs"] is True
    assert "queued 1 new videos at priority" in out
    assert json.loads(out.strip().splitlines()[-1]) == {"videos": 1}
    row = rows(cfg)[VID]
    assert row["priority"] == cli.discover.DISCOVER_PRIORITY
    assert json.loads(row["playlists"]) == ["Kanał: Kanał A"]


def test_discover_without_queue_touches_no_db(cfg, monkeypatch, capsys, tmp_path):
    target = tmp_path / "custom.tsv"
    monkeypatch.setattr(cli.discover, "run",
                        lambda *a, **kw: {"rows": [{"video_id": VID}], "summary": {"videos": 1}})
    assert cli.cmd_discover(cfg, qargs(account="x", days=7, out=str(target), no_subs=True,
                                      skip_shorts=True, min_seconds=120, max_per_channel=2)) == 0
    out = capsys.readouterr().out
    assert "queued" not in out
    assert rows(cfg) == {}


# --------------------------------------------------------------------------- cmd_categorize

def test_categorize_prints_table(cfg, monkeypatch, capsys, tmp_path):
    seen = {}
    monkeypatch.setattr(cli.categorize, "run",
                        lambda i, o, min_score=3: seen.update(input=i, out=o, min_score=min_score) or
                        {"ai_software": {"videos": 3, "hours": 1.5,
                                         "top_channels": ["A", "B", "C", "D"]}})
    out_dir = tmp_path / "cats"
    assert cli.cmd_categorize(cfg, qargs(input="list.tsv", out=str(out_dir), min_score=5)) == 0
    out = capsys.readouterr().out
    assert seen["input"] == Path("list.tsv")
    assert seen["min_score"] == 5
    assert "ai_software" in out and "3 videos" in out and "A, B, C" in out
    assert "D" not in out
    assert f"files in {out_dir}" in out


# --------------------------------------------------------------------------- cmd_rerender

def _bundle(root: Path, vid: str, *, description: str = "opis", report: bool = True) -> Path:
    d = root / vid
    d.mkdir(parents=True)
    (d / "bundle.json").write_text(json.dumps({"video_id": vid, "url": f"https://youtu.be/{vid}",
                                               "title": "T", "description": description}),
                                   encoding="utf-8")
    if report:
        (d / "report.json").write_text(json.dumps({"report": {"tl_dr": "x"}, "run": {"model": "m"}}),
                                       encoding="utf-8")
    return d


@pytest.fixture()
def render_stub(monkeypatch):
    calls = []

    def fake_markdown(bundle, report, run, lang, notion_url=None):
        calls.append({"video_id": bundle["video_id"], "lang": lang, "url": notion_url})
        return f"# {bundle['video_id']} {notion_url or ''}\n"

    monkeypatch.setattr(render, "markdown", fake_markdown)
    return calls


def test_rerender_rewrites_report_md_for_every_bundle(cfg, render_stub, capsys):
    root = Path(cfg["data_dir"]) / "bundles"
    _bundle(root, VID)
    assert cli.cmd_rerender(cfg, qargs()) == 0
    out = capsys.readouterr().out
    assert f"{VID}: ok" in out
    assert "re-rendered 1 of 1" in out
    assert (root / VID / "report.md").read_text(encoding="utf-8").startswith(f"# {VID}")
    assert render_stub[0]["lang"] == cfg["report_language"]


def test_rerender_without_bundles_dir_is_clean(cfg, render_stub, capsys):
    assert cli.cmd_rerender(cfg, qargs()) == 0
    assert "re-rendered 0 of 0" in capsys.readouterr().out


def test_rerender_broken_bundle_does_not_abort_batch(cfg, render_stub, capsys):
    root = Path(cfg["data_dir"]) / "bundles"
    _bundle(root, VID)
    broken = root / VID2
    broken.mkdir(parents=True)
    (broken / "report.json").write_text(json.dumps({"report": {}}), encoding="utf-8")

    assert cli.cmd_rerender(cfg, qargs()) == 0
    out = capsys.readouterr().out
    assert f"{VID}: ok" in out
    assert f"{VID2}: " in out
    assert "bundle.json" in out          # the actual FileNotFoundError text
    assert "re-rendered 1 of 2" in out


def test_rerender_explicit_video_list_and_data_dir(cfg, render_stub, capsys, tmp_path):
    alt = tmp_path / "altdata"
    _bundle(alt / "bundles", VID)
    _bundle(Path(cfg["data_dir"]) / "bundles", VID2)
    assert cli.cmd_rerender(cfg, qargs(video=[VID], data_dir=str(alt))) == 0
    out = capsys.readouterr().out
    assert "re-rendered 1 of 1" in out
    assert VID in out and VID2 not in out


def test_rerender_refetch_fills_missing_description(cfg, render_stub, monkeypatch):
    root = Path(cfg["data_dir"]) / "bundles"
    d = _bundle(root, VID, description="")
    monkeypatch.setattr(cli.fetch, "probe", lambda url: {"description": "z yt-dlp"})

    assert cli.cmd_rerender(cfg, qargs(refetch=True)) == 0
    assert json.loads((d / "bundle.json").read_text(encoding="utf-8"))["description"] == "z yt-dlp"


def test_rerender_updates_existing_notion_page(cfg, render_stub, monkeypatch, capsys):
    root = Path(cfg["data_dir"]) / "bundles"
    _bundle(root, VID)
    seen = {}

    class FakeNotion:
        def __init__(self, ds):
            seen["data_source"] = ds

        def find(self, vid):
            seen["find"] = vid
            return "page-1"

    monkeypatch.setattr(ytdigest.notion, "Notion", FakeNotion)
    monkeypatch.setattr(ytdigest.notion, "write_report",
                        lambda nt, d, bundle, rep, run, cfg_: seen.update(dir=d) or "https://notion/page-1")

    assert cli.cmd_rerender(cfg, qargs(notion=True)) == 0
    out = capsys.readouterr().out
    assert seen["data_source"] == cfg["notion_data_source_id"]
    assert seen["find"] == VID
    assert f"{VID}: ok https://notion/page-1" in out
    assert render_stub[0]["url"] == "https://notion/page-1"
    assert "https://notion/page-1" in (root / VID / "report.md").read_text(encoding="utf-8")


def test_rerender_skips_notion_when_page_missing(cfg, render_stub, monkeypatch):
    root = Path(cfg["data_dir"]) / "bundles"
    _bundle(root, VID)

    class FakeNotion:
        def __init__(self, ds):
            pass

        def find(self, vid):
            return None

    monkeypatch.setattr(notion, "Notion", FakeNotion)
    monkeypatch.setattr(notion, "write_report",
                        lambda *a, **kw: pytest.fail("must not write a new page during rerender"))
    assert cli.cmd_rerender(cfg, qargs(notion=True)) == 0
    assert render_stub[0]["url"] is None


# --------------------------------------------------------------------------- cmd_worker

@pytest.fixture()
def worker(monkeypatch):
    """Fake pipeline + notify_ha; returns the list of processed calls."""
    processed = []
    notified = []

    def fake_process(url, cfg_, **kw):
        processed.append({"url": url, **kw})
        return {"video_id": kw.get("_vid") or VID, "status": "done", "cost_usd": 0.1,
                "notion_url": "https://notion/page-1"}

    monkeypatch.setattr(cli.pipeline, "safe_process", fake_process)
    monkeypatch.setattr(cli, "notify_ha", lambda cfg_, res: notified.append(res))
    return SimpleNamespace(processed=processed, notified=notified)


def test_worker_backs_off_when_lock_is_held(cfg, monkeypatch, capsys):
    def busy(lock, op):
        raise BlockingIOError(11, "resource temporarily unavailable")

    monkeypatch.setattr(cli.fcntl, "flock", busy)
    assert cli.cmd_worker(cfg, qargs()) == 0
    assert "another worker is running" in capsys.readouterr().out


def test_worker_reports_empty_queue(cfg, worker, capsys):
    assert cli.cmd_worker(cfg, qargs()) == 0
    assert "queue empty" in capsys.readouterr().out
    assert worker.processed == []


def test_worker_runs_user_queue_without_gate(cfg, worker, monkeypatch, capsys):
    cli._q(cfg).add(VID, f"https://youtu.be/{VID}", priority=queue_mod.USER_PRIORITY,
                    account="ręcznie", title="T")
    monkeypatch.setattr(cli.gate, "check", lambda cfg_: pytest.fail("user work must not consult the gate"))

    assert cli.cmd_worker(cfg, qargs(idle_only=True, max_videos=1)) == 0
    out = capsys.readouterr().out
    assert f"{VID}: done $0.1000 https://notion/page-1" in out
    assert worker.processed[0]["tag"] == "manual"
    assert worker.processed[0]["account"] == "ręcznie"
    assert len(worker.notified) == 1
    assert rows(cfg)[VID]["status"] == "done"
    assert rows(cfg)[VID]["cost_usd"] == pytest.approx(0.1)


def test_worker_stops_at_gate_when_closed(cfg, worker, monkeypatch, capsys):
    cli._q(cfg).add(VID, f"https://youtu.be/{VID}", priority=queue_mod.BACKLOG_PRIORITY, account="x")
    monkeypatch.setattr(cli.gate, "check", lambda cfg_: (False, ["NO  daily cap reached", "NO  user active"]))

    assert cli.cmd_worker(cfg, qargs(idle_only=True)) == 0
    out = capsys.readouterr().out
    assert "gate closed:\n  NO  daily cap reached\n  NO  user active" in out
    assert worker.processed == []
    assert rows(cfg)[VID]["status"] == "queued"
    assert worker.notified == []


def test_worker_only_user_leaves_backlog_alone(cfg, worker, capsys):
    cli._q(cfg).add(VID, f"https://youtu.be/{VID}", priority=queue_mod.BACKLOG_PRIORITY, account="x")
    assert cli.cmd_worker(cfg, qargs(only_user=True)) == 0
    out = capsys.readouterr().out
    assert "queue empty" not in out
    assert worker.processed == []
    assert rows(cfg)[VID]["status"] == "queued"


def test_worker_respects_max_videos(cfg, worker):
    q = cli._q(cfg)
    q.add(VID, f"https://youtu.be/{VID}", priority=queue_mod.USER_PRIORITY, account="ręcznie")
    q.add(VID2, f"https://youtu.be/{VID2}", priority=queue_mod.USER_PRIORITY, account="ręcznie")
    assert cli.cmd_worker(cfg, qargs(max_videos=1)) == 0
    assert len(worker.processed) == 1
    stored = rows(cfg)
    assert sorted([stored[VID]["status"], stored[VID2]["status"]]) == ["done", "queued"]


def test_worker_releases_stuck_rows(cfg, worker):
    q = cli._q(cfg)
    q.add(VID, f"https://youtu.be/{VID}", priority=queue_mod.USER_PRIORITY, account="ręcznie")
    q.db.execute("UPDATE videos SET status='processing', updated_at=datetime('now','-5 hours')")
    q.db.commit()
    assert cli.cmd_worker(cfg, qargs()) == 0
    assert rows(cfg)[VID]["status"] == "done"


def test_worker_failure_requeues_until_attempt_limit(cfg, worker, monkeypatch):
    cli._q(cfg).add(VID, f"https://youtu.be/{VID}", priority=queue_mod.USER_PRIORITY, account="ręcznie")
    monkeypatch.setattr(cli.pipeline, "safe_process",
                        lambda url, cfg_, **kw: {"status": "failed", "error": "boom"})
    assert cli.cmd_worker(cfg, qargs(max_videos=1)) == 0
    row = rows(cfg)[VID]
    assert row["status"] == "queued"      # attempts < MAX_ATTEMPTS -> retry later
    assert row["last_error"] == "boom"


# --------------------------------------------------------------------------- other commands

def test_backlog_sync_passes_account_list(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli.backlog, "sync", lambda cfg_, q, account: seen.update(cfg=cfg_, account=account))
    assert cli.cmd_backlog(cfg, qargs(account=["a1"])) == 0
    assert seen["account"] == ["a1"]
    assert isinstance(seen["cfg"], dict)


def test_backlog_sync_defaults_to_all_accounts(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr(cli.backlog, "sync", lambda cfg_, q, account: seen.update(account=account))
    assert cli.cmd_backlog(cfg, qargs(account=None)) == 0
    assert seen["account"] is None


def test_gate_open(cfg, monkeypatch, capsys):
    monkeypatch.setattr(cli.gate, "check", lambda cfg_: (True, ["ok  budget", "ok  idle"]))
    assert cli.cmd_gate(cfg, qargs()) == 0
    assert capsys.readouterr().out == "OPEN\n  ok  budget\n  ok  idle\n"


def test_gate_closed_exits_nonzero(cfg, monkeypatch, capsys):
    monkeypatch.setattr(cli.gate, "check", lambda cfg_: (False, ["NO  user active"]))
    assert cli.cmd_gate(cfg, qargs()) == 1
    assert capsys.readouterr().out == "CLOSED\n  NO  user active\n"


def test_status_reports_queue_and_spend(cfg, capsys):
    cli._q(cfg).add(VID, f"https://youtu.be/{VID}", priority=queue_mod.USER_PRIORITY, account="ręcznie")
    ledger = Path(cfg["data_dir"]) / "spend.jsonl"
    ledger.write_text("\n".join([
        json.dumps({"tag": "manual", "cost_usd": 0.5, "ts": "2020-01-01T00:00:00+00:00"}),
        json.dumps({"tag": "backlog", "cost_usd": 0.25, "ts": "2020-01-01T00:00:00+00:00"}),
        "not json",
    ]) + "\n", encoding="utf-8")

    assert cli.cmd_status(cfg, qargs()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["queue"] == {"queued": {"count": 1, "cost_usd": 0.0}}
    assert payload["backlog_spend_today_usd"] == 0.0     # dated 2020 -> not today
    assert payload["manual_spend_today_usd"] == 0.0


def test_status_counts_todays_spend(cfg, capsys):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    ledger = Path(cfg["data_dir"]) / "spend.jsonl"
    ledger.write_text(json.dumps({"tag": "manual", "cost_usd": 0.125, "ts": now}) + "\n", encoding="utf-8")
    assert cli.cmd_status(cfg, qargs()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["manual_spend_today_usd"] == pytest.approx(0.125)
    assert payload["backlog_spend_today_usd"] == 0.0


def test_serve_passes_notify_callback(cfg, monkeypatch):
    seen = {}

    def fake_serve(cfg_, q_path, host, port, notify=None):
        seen.update(queue=q_path, host=host, port=port, notify=notify)

    notified = []
    monkeypatch.setattr(server, "serve", fake_serve)
    monkeypatch.setattr(cli, "notify_ha", lambda cfg_, res: notified.append(res))

    assert cli.cmd_serve(cfg, qargs(host="127.0.0.1", port=9001)) == 0
    assert seen["queue"] == Path(cfg["data_dir"]) / "queue.db"
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 9001
    seen["notify"]({"video_id": VID})
    assert notified == [{"video_id": VID}]


# --------------------------------------------------------------------------- notify_ha

@pytest.fixture()
def hass(monkeypatch):
    """Stand-in for the ``requests`` module and a Home-Assistant-enabled cfg."""
    calls = []
    module = ModuleType("requests")

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return SimpleNamespace(status_code=200)

    module.post = post
    monkeypatch.setitem(sys.modules, "requests", module)
    return calls


def test_notify_ha_is_noop_without_service(cfg, hass, monkeypatch):
    monkeypatch.setenv("HASS_URL", "http://ha.local")
    monkeypatch.setenv("HASS_TOKEN", "tok")
    cli.notify_ha(cfg, {"status": "done"})
    assert hass == []


def test_notify_ha_is_noop_without_credentials(cfg, hass, monkeypatch):
    cfg["notify_ha_service"] = "notify.mobile_app_phone"
    monkeypatch.delenv("HASS_URL", raising=False)
    monkeypatch.delenv("HASS_TOKEN", raising=False)
    cli.notify_ha(cfg, {"status": "done"})
    assert hass == []


def test_notify_ha_posts_success_message(cfg, hass, monkeypatch):
    cfg["notify_ha_service"] = "notify.mobile_app_phone"
    monkeypatch.setenv("HASS_URL", "http://ha.local/")
    monkeypatch.setenv("HASS_TOKEN", "tok")

    cli.notify_ha(cfg, {"status": "done", "video_id": VID, "title": "Tytuł",
                        "one_line": "Film o niczym", "notion_url": "https://notion/page-1"})

    assert len(hass) == 1
    call = hass[0]
    assert call["url"] == "http://ha.local/api/services/notify/mobile_app_phone"
    assert call["headers"] == {"Authorization": "Bearer tok"}
    assert call["json"]["title"] == "Hermes: raport z filmu"
    assert call["json"]["message"] == "Film o niczym"
    assert call["json"]["data"]["url"] == "https://notion/page-1"
    assert call["timeout"] == 15


def test_notify_ha_posts_failure_message(cfg, hass, monkeypatch):
    cfg["notify_ha_service"] = "notify.telegram"
    monkeypatch.setenv("HASS_URL", "http://ha.local")
    monkeypatch.setenv("HASS_TOKEN", "tok")

    cli.notify_ha(cfg, {"status": "failed", "video_id": VID, "error": "x" * 500})

    call = hass[0]
    assert call["url"] == "http://ha.local/api/services/notify/telegram"
    assert call["json"]["title"] == "Hermes: nie udało się"
    assert call["json"]["message"] == "Błąd: " + "x" * 200


def test_notify_ha_falls_back_to_title_when_no_one_line(cfg, hass, monkeypatch):
    cfg["notify_ha_service"] = "notify.phone"
    monkeypatch.setenv("HASS_URL", "http://ha.local")
    monkeypatch.setenv("HASS_TOKEN", "tok")
    cli.notify_ha(cfg, {"status": "artistic", "video_id": VID, "title": "Tytuł"})
    assert hass[0]["json"]["message"] == "Tytuł"
    # no notion_url -> the notification carries no click target (empty, not a YouTube link)
    assert hass[0]["json"]["data"] == {"url": "", "clickAction": ""}


def test_notify_ha_swallows_transport_errors(cfg, monkeypatch):
    cfg["notify_ha_service"] = "notify.phone"
    monkeypatch.setenv("HASS_URL", "http://ha.local")
    monkeypatch.setenv("HASS_TOKEN", "tok")
    module = ModuleType("requests")

    def post(*a, **kw):
        raise ConnectionError("HA down")

    module.post = post
    monkeypatch.setitem(sys.modules, "requests", module)
    cli.notify_ha(cfg, {"status": "done", "video_id": VID})   # must not raise
