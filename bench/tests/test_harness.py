"""Harness tests: no network, no real agents. A fake ``claude`` script stands in for Claude Code."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from hbench import report, runner, workspace
from hbench.agents import AGENTS, RunContext
from hbench.providers import Provider, load_providers
from hbench.tasks import load_task, load_tasks, select

ROOT = Path(__file__).resolve().parent.parent


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *workspace.GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def toy(tmp_path: Path):
    """A source repo with a buggy commit and a fix commit, plus a task pointing at it."""
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    (src / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (src / "test_calc.py").write_text("from calc import add\n\ndef test_zero():\n    assert add(0, 0) == 0\n")
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "buggy")
    (src / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (src / "test_calc.py").write_text(
        "from calc import add\n\ndef test_zero():\n    assert add(0, 0) == 0\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n"
    )
    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "SECRET-FIX-MESSAGE fix add")
    fix = _git(src, "rev-parse", "HEAD")
    tdir = tmp_path / "tasks" / "toy-add"
    tdir.mkdir(parents=True)
    (tdir / "task.toml").write_text(
        f'repo = "{src}"\nfix_commit = "{fix}"\ncategory = "bugfix"\ntags = ["toy"]\n'
        'hidden_tests = ["test_calc.py"]\n[verify]\ncommand = "python -m pytest -q -p no:cacheprovider test_calc.py"\n'
    )
    (tdir / "instruction.md").write_text("add() subtracts instead of adding. Fix it.\n")
    return load_task(tdir), src


def test_oracle_passes_noop_fails(toy, tmp_path):
    task, _ = toy
    o = runner.run_attempt(task, "oracle", runner.NO_PROVIDER, "-", tmp_path / "out")
    n = runner.run_attempt(task, "noop", runner.NO_PROVIDER, "-", tmp_path / "out")
    assert o["solved"] is True and o["tests_passed"] == 2
    assert n["solved"] is False and n["tests_failed"] == 1
    assert o["files_changed"] == 1  # oracle never applies the hidden tests itself


def test_workspace_hides_history_and_hidden_tests(toy, tmp_path):
    task, src = toy
    ws = tmp_path / "ws"
    workspace.prepare(task, src, ws)
    log = _git(ws, "log", "--all", "--format=%s")
    assert "SECRET-FIX-MESSAGE" not in log and len(log.splitlines()) == 1
    assert "test_add" not in (ws / "test_calc.py").read_text()


FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path("calc.py").write_text("def add(a, b):\n    return a + b\n")
pathlib.Path(os.environ["CLAUDE_CONFIG_DIR"], "env.json").write_text(json.dumps(dict(os.environ)))
print(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Edit"}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
                  "total_cost_usd": 0.0123, "usage": {"input_tokens": 1000, "output_tokens": 200,
                  "cache_read_input_tokens": 50, "cache_creation_input_tokens": 10}}))
"""


@pytest.fixture
def fake_claude(tmp_path):
    p = tmp_path / "fake-claude"
    p.write_text(FAKE_CLAUDE)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_claude_code_adapter_with_anthropic(toy, tmp_path, fake_claude):
    task, _ = toy
    prov = Provider(name="anthropic", kind="anthropic")
    rec = runner.run_attempt(
        task, "claude-code", prov, "sonnet", tmp_path / "out", {"binary": fake_claude}, keep_workspace=True
    )
    assert rec["solved"] is True, rec
    assert rec["input_tokens"] == 1000 and rec["output_tokens"] == 200
    assert rec["cost_usd"] == 0.0123 and rec["turns"] == 3 and rec["tool_calls"] == 1
    cmd = (Path(rec["outdir"]) / "command.txt").read_text()
    assert "--output-format stream-json" in cmd and "--model sonnet" in cmd


def test_claude_code_adapter_routes_to_ollama(toy, tmp_path, fake_claude, monkeypatch):
    task, _ = toy
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "subscription-token")
    prov = Provider(name="ollama-pc", kind="ollama", base_url="http://10.0.0.5:11434", local=True)
    rec = runner.run_attempt(task, "claude-code", prov, "qwen3-coder:30b", tmp_path / "out", {"binary": fake_claude})
    env = json.loads((Path(rec["outdir"]) / "claude-config" / "env.json").read_text())
    assert env["ANTHROPIC_BASE_URL"] == "http://10.0.0.5:11434"
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == "qwen3-coder:30b"
    assert env["CLAUDE_CODE_SUBAGENT_MODEL"] == "qwen3-coder:30b"
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env  # subscription token never goes to another endpoint
    assert rec["cost_usd"] is None  # list-price cost is meaningless for a local model


def _ctx(tmp_path, kind, **kw):
    task = load_tasks(ROOT / "tasks")[0]
    return RunContext(task, tmp_path, tmp_path, tmp_path, Provider(name=kind, kind=kind, **kw), "m1", 60)


def test_copilot_env_mapping(tmp_path):
    argv, env = AGENTS["copilot-cli"]().command(_ctx(tmp_path, "ollama", base_url="http://h:11434", local=True))
    assert env["COPILOT_PROVIDER_BASE_URL"] == "http://h:11434/v1"
    assert env["COPILOT_MODEL"] == "m1" and env["COPILOT_OFFLINE"] == "true"
    argv, env = AGENTS["copilot-cli"]().command(_ctx(tmp_path, "github"))
    assert "--model" in argv and "COPILOT_PROVIDER_BASE_URL" not in env


def test_copilot_parse_counts_tool_starts(tmp_path):
    events = [
        {"type": "assistant.turn_start", "data": {"turnId": "0"}},
        {"type": "assistant.tool_call_delta", "data": {"toolCallId": "c1"}},
        {"type": "tool.execution_start", "data": {"toolCallId": "c1", "toolName": "bash"}},
        {"type": "tool.execution_complete", "data": {"toolCallId": "c1"}},
        {"type": "assistant.turn_start", "data": {"turnId": "1"}},
        {"type": "result", "exitCode": 0, "usage": {"premiumRequests": 0}},
    ]
    out = tmp_path / "agent.stdout"
    out.write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n")
    m = AGENTS["copilot-cli"]().parse(_ctx(tmp_path, "ollama"), out)
    assert m["tool_calls"] == 1 and m["turns"] == 2 and m["agent_status"] == "success"


def test_claude_cost_only_for_anthropic(tmp_path):
    out = tmp_path / "agent.stdout"
    out.write_text(json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.5, "num_turns": 3}))
    assert AGENTS["claude-code"]().parse(_ctx(tmp_path, "anthropic"), out)["cost_usd"] == 0.5
    assert AGENTS["claude-code"]().parse(_ctx(tmp_path, "ollama"), out)["cost_usd"] is None


def test_zed_env_mapping(tmp_path):
    argv, env = AGENTS["zed"]().command(_ctx(tmp_path, "ollama", base_url="http://h:11434"))
    providers = json.loads(env["ZED_OPENAI_COMPATIBLE_PROVIDERS"])
    assert providers["hbench"]["api_url"] == "http://h:11434/v1"
    assert argv[argv.index("--model") + 1] == "hbench/m1"
    argv, _ = AGENTS["zed"]().command(_ctx(tmp_path, "anthropic"))
    assert argv[argv.index("--model") + 1] == "anthropic/m1"


def test_unsupported_provider_is_a_harness_error(toy, tmp_path):
    task, _ = toy
    rec = runner.run_attempt(task, "zed", Provider(name="github", kind="github"), "x", tmp_path / "out")
    assert rec["solved"] is None and "cannot use provider" in rec["error"]


def test_report_markdown():
    rows = [
        {
            "task": "a",
            "category": "bugfix",
            "agent": "claude-code",
            "provider": "anthropic",
            "model": "s",
            "solved": True,
            "duration_sec": 10,
            "output_tokens": 100,
            "cost_usd": 0.5,
        },
        {
            "task": "b",
            "category": "bugfix",
            "agent": "claude-code",
            "provider": "anthropic",
            "model": "s",
            "solved": False,
            "duration_sec": 30,
            "output_tokens": 300,
            "cost_usd": 0.5,
        },
        {
            "task": "a",
            "category": "bugfix",
            "agent": "zed",
            "provider": "ollama-pc",
            "model": "q",
            "solved": None,
            "error": "boom",
        },
    ]
    md = report.markdown(rows)
    assert "| claude-code | anthropic | s | 1/2 | 50% | 20s" in md
    assert "$1.00 | $1.00" in md
    assert "(+1 err)" in md


def test_repo_files_parse():
    assert {"anthropic", "ollama-pc", "ollama-cloud", "github"} <= set(load_providers(ROOT / "providers.toml"))
    cells, patterns, repeats = runner.expand_matrix(ROOT / "matrix.example.toml")
    assert cells and repeats >= 1
    tasks = load_tasks(ROOT / "tasks")
    assert len(tasks) >= 7 and all(t.verify and t.hidden_tests for t in tasks)
    assert select(tasks, ["tag:private"]) and select(tasks, ["crewai-*"])
    assert os.path.exists(ROOT / "DESIGN.md")
