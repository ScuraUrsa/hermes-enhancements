"""ytdigest CLI entry point: subcommand dispatch and the config error path.

Everything here is hermetic: argparse is driven through ``sys.argv``, and the
target command functions are replaced by recorders, so nothing touches the
network, ffmpeg, model providers, Home Assistant or Notion.
"""

from __future__ import annotations

import sys

import pytest

from ytdigest import cli


@pytest.fixture()
def recorder(monkeypatch):
    """Replace every cmd_* handler with a recorder returning 7."""
    calls = []

    def make(name):
        def fn(cfg, a):
            calls.append((name, cfg, a))
            return 7

        return fn

    for name in ("cmd_run", "cmd_add", "cmd_compare", "cmd_discover", "cmd_categorize",
                 "cmd_rerender", "cmd_worker", "cmd_backlog", "cmd_gate", "cmd_status", "cmd_serve"):
        monkeypatch.setattr(cli, name, make(name))
    return calls


@pytest.fixture()
def loaded(monkeypatch):
    """Record what main() passes to config.load instead of reading a file."""
    seen = []
    sentinel = {"data_dir": "/tmp/ytdigest-sentinel", "report_language": "pl"}

    def fake_load(path=None):
        seen.append(path)
        return sentinel

    monkeypatch.setattr(cli.config, "load", fake_load)
    return seen, sentinel


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["ytdigest", *argv])
    return cli.main()


def test_main_dispatches_status(monkeypatch, recorder, loaded):
    seen, sentinel = loaded
    assert _run(monkeypatch, "status") == 7
    assert [c[0] for c in recorder] == ["cmd_status"]
    _, cfg, args = recorder[0]
    assert cfg is sentinel
    assert args.cmd == "status"
    assert seen == [None]


def test_main_passes_config_path_through(monkeypatch, recorder, loaded):
    seen, _ = loaded
    assert _run(monkeypatch, "--config", "/etc/ytdigest.yaml", "status") == 7
    assert seen == ["/etc/ytdigest.yaml"]
    assert recorder[0][2].cmd == "status"


def test_main_dispatches_run(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "run", "dQw4w9WgXcQ", "--no-notion", "--analyzer", "frames", "--json") == 7
    args = recorder[0][2]
    assert args.url == "dQw4w9WgXcQ"
    assert args.no_notion is True
    assert args.analyzer == "frames"
    assert args.json is True


def test_main_run_defaults(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "run", "dQw4w9WgXcQ") == 7
    args = recorder[0][2]
    assert args.no_notion is False
    assert args.analyzer is None
    assert args.json is False


def test_main_dispatches_add(monkeypatch, recorder, loaded, tmp_path):
    ids = tmp_path / "wl.txt"
    ids.write_text("dQw4w9WgXcQ\n", encoding="utf-8")
    assert _run(monkeypatch, "add", "--file", str(ids), "--account", "fjkazmierczak",
                "--playlist", "Do obejrzenia", "--now") == 7
    args = recorder[0][2]
    assert args.urls == []
    assert args.file == str(ids)
    assert args.account == "fjkazmierczak"
    assert args.playlist == "Do obejrzenia"
    assert args.now is True
    assert args.backlog is False


def test_main_dispatches_compare(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "compare", "dQw4w9WgXcQ", "--refs", "a:1,b:2",
                "--notion-parent", "page-1", "--title", "T") == 7
    args = recorder[0][2]
    assert args.urls == ["dQw4w9WgXcQ"]
    assert args.refs == "a:1,b:2"
    assert args.notion_parent == "page-1"
    assert args.title == "T"


def test_main_dispatches_discover(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "discover", "--days", "30", "--ids-file", "a.txt",
                "--ids-file", "b.txt", "--skip-shorts", "--min-seconds", "180",
                "--max-per-channel", "3", "--queue") == 7
    args = recorder[0][2]
    assert args.account == "fjkazmierczak"
    assert args.days == 30
    assert args.ids_file == ["a.txt", "b.txt"]
    assert args.no_subs is False
    assert args.skip_shorts is True
    assert args.min_seconds == 180
    assert args.max_per_channel == 3
    assert args.queue is True


def test_main_dispatches_categorize(monkeypatch, recorder, loaded, tmp_path):
    assert _run(monkeypatch, "categorize", "list.tsv", "--out", str(tmp_path), "--min-score", "5") == 7
    args = recorder[0][2]
    assert args.input == "list.tsv"
    assert args.out == str(tmp_path)
    assert args.min_score == 5


def test_main_dispatches_rerender(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "rerender", "--video", "aaaaaaaaaaa", "--video", "bbbbbbbbbbb",
                "--notion", "--refetch", "--data-dir", "/tmp/other") == 7
    args = recorder[0][2]
    assert args.video == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
    assert args.notion is True
    assert args.refetch is True
    assert args.data_dir == "/tmp/other"


def test_main_dispatches_worker_defaults(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "worker") == 7
    args = recorder[0][2]
    assert args.idle_only is False
    assert args.only_user is False
    assert args.max_videos == 5
    assert args.max_minutes == 25


def test_main_dispatches_backlog_sync(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "backlog-sync", "--account", "a1", "--account", "a2") == 7
    assert recorder[0][0] == "cmd_backlog"
    assert recorder[0][2].account == ["a1", "a2"]


def test_main_dispatches_gate(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "gate") == 7
    assert [c[0] for c in recorder] == ["cmd_gate"]


def test_main_dispatches_serve_defaults(monkeypatch, recorder, loaded):
    assert _run(monkeypatch, "serve") == 7
    args = recorder[0][2]
    assert args.host == "127.0.0.1"
    assert args.port == 8765


def test_main_rejects_unknown_subcommand(monkeypatch, recorder, loaded):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, "upload")
    assert exc.value.code == 2
    assert recorder == []


def test_main_rejects_missing_subcommand(monkeypatch, recorder, loaded):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch)
    assert exc.value.code == 2
    assert recorder == []


@pytest.mark.parametrize("argv", [
    ("run",),                                  # url is required
    ("categorize", "list.tsv"),                # --out is required
    ("discover", "--days", "not-a-number"),    # type=int
])
def test_main_rejects_bad_arguments(monkeypatch, recorder, loaded, argv):
    with pytest.raises(SystemExit) as exc:
        _run(monkeypatch, *argv)
    assert exc.value.code == 2
    assert recorder == []


def test_main_reports_config_error_without_traceback(monkeypatch, recorder, capsys):
    """A broken/absent --config must be a controlled message, not a traceback."""

    def boom(path=None):
        raise FileNotFoundError(f"no such config file: {path}")

    monkeypatch.setattr(cli.config, "load", boom)
    rc = _run(monkeypatch, "--config", "/nope/ytdigest.yaml", "status")
    out, err = capsys.readouterr()
    assert rc == 2
    assert recorder == []
    assert "config error" in err
    assert "/nope/ytdigest.yaml" in err
    assert "Traceback" not in err + out


def test_main_reports_malformed_config_without_traceback(monkeypatch, recorder, capsys):
    """PyYAML raises on malformed YAML; the CLI must report it, not dump a stack."""

    def boom(path=None):
        raise ValueError("while parsing a block mapping")

    monkeypatch.setattr(cli.config, "load", boom)
    rc = _run(monkeypatch, "status")
    out, err = capsys.readouterr()
    assert rc == 2
    assert recorder == []
    assert "config error" in err
    assert "while parsing a block mapping" in err
    assert "Traceback" not in err + out
