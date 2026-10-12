"""Behaviour tests for cheap-route: the plugin must never leak a personal message outside,
and must fail open (agent turn) whenever the evaluator or the free channel misbehaves."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE.parent))  # package "cheap_route" is imported via the symlink below

# The plugin directory is named "plugin"; import it as a package without touching sys.modules tricks.
import importlib.util

spec = importlib.util.spec_from_file_location(
    "cheap_route_plugin", HERE / "plugin" / "__init__.py",
    submodule_search_locations=[str(HERE / "plugin")])
plugin = importlib.util.module_from_spec(spec)
sys.modules["cheap_route_plugin"] = plugin
spec.loader.exec_module(plugin)
router_mod = sys.modules["cheap_route_plugin.router"]


class FakeResult:
    def __init__(self, text):
        self.text = text


class FakeLlm:
    def __init__(self, answers):
        self.answers = answers  # task -> text or Exception
        self.calls = []

    def complete(self, messages, task=None, **kw):
        self.calls.append((task, messages[-1]["content"]))
        answer = self.answers[task]
        if isinstance(answer, Exception):
            raise answer
        return FakeResult(answer)


class FakeCtx:
    def __init__(self, answers, settings=None):
        self.llm = FakeLlm(answers)
        self.settings = settings or {}
        self.hooks = {}
        self.commands = {}
        self.aux = []

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def set_config(self, key, value):
        self.settings[key] = value

    def register_hook(self, name, fn):
        self.hooks[name] = fn

    def register_command(self, name, fn, **kw):
        self.commands[name] = fn

    def register_auxiliary_task(self, key, **kw):
        self.aux.append(key)


FREE = json.dumps({"route": "free_web", "confidence": 0.95, "reason": "wiedza ogólna"})
UNSURE = json.dumps({"route": "free_web", "confidence": 0.6, "reason": "hm"})


@pytest.fixture
def setup(tmp_path, monkeypatch):
    def make(answers, settings=None):
        ctx = FakeCtx(answers, settings)
        plugin.register(ctx)
        plugin._router = router_mod.Router(tmp_path / "decisions.jsonl")
        return ctx
    return make


def test_general_question_is_answered_by_free_channel(setup, tmp_path):
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "CRISPR to technika edycji genów."})
    out = ctx.hooks["post_gateway_admission"](session_key="s1", platform="telegram", text="Co to jest CRISPR?")
    assert out["action"] == "handled" and out["reply"].startswith("CRISPR to technika")
    assert "darmowego kanału" in out["reply"]
    rows = [json.loads(l) for l in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["outcome"] == "answered" and rows[-1]["route"] == "free_web"


@pytest.mark.parametrize("text", [
    "przesuń T25 na później", "Jakie mam jutro spotkania?", "Wyślij Kasi maila, że się spóźnię",
    "Dlaczego crewai-worker restartuje się na VM?", "Dzięki!", "ok",
])
def test_personal_or_actionable_never_leaves(setup, text):
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "leak"})
    assert ctx.hooks["post_gateway_admission"](session_key="s1", platform="cli", text=text) is None
    assert ctx.llm.calls == []  # rules decided; the model was never asked


def test_low_confidence_goes_to_agent(setup):
    ctx = setup({plugin.ROUTER_TASK: UNSURE, plugin.FREE_TASK: "leak"})
    assert ctx.hooks["post_gateway_admission"](session_key="s1", platform="cli", text="Czym różni się FDM od SLA?") is None
    assert [t for t, _ in ctx.llm.calls] == [plugin.ROUTER_TASK]


def test_evaluator_failure_fails_open(setup):
    ctx = setup({plugin.ROUTER_TASK: RuntimeError("llama-server down"), plugin.FREE_TASK: "x"})
    assert ctx.hooks["post_gateway_admission"](session_key="s1", platform="cli", text="Czym różni się FDM od SLA?") is None


def test_free_channel_failure_fails_open(setup, tmp_path):
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: RuntimeError("429")})
    assert ctx.hooks["post_gateway_admission"](session_key="s1", platform="cli", text="Czym różni się FDM od SLA?") is None
    rows = [json.loads(l) for l in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["outcome"] == "fallback"


def test_short_followup_after_agent_turn_stays_with_agent(setup):
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "leak"})
    hook = ctx.hooks["post_gateway_admission"]
    assert hook(session_key="s2", platform="cli", text="Jakie mam jutro spotkania?") is None
    # Looks general on its own, but it continues the agent's conversation.
    assert hook(session_key="s2", platform="cli", text="A w czwartek o której?") is None


def test_disabled_and_platform_filter(setup):
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "x"}, settings={"enabled": False})
    assert ctx.hooks["post_gateway_admission"](session_key="s", platform="cli", text="Co to jest CRISPR?") is None
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "x"}, settings={"platforms": ["telegram"]})
    assert ctx.hooks["post_gateway_admission"](session_key="s", platform="matrix", text="Co to jest CRISPR?") is None


def test_route_command_toggles_and_reports(setup):
    ctx = setup({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "x"})
    assert "wyłączony" in ctx.commands["route"]("off") and ctx.settings["enabled"] is False
    assert "włączony" in ctx.commands["route"]("on")
    assert "decyzji" in ctx.commands["route"]("")
