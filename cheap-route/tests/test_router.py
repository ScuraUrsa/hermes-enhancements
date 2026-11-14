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


# ---------------------------------------------------------------- Hermes <= v0.20 compat (pre_gateway_dispatch)
import asyncio
from types import SimpleNamespace


class FakeAdapter:
    def __init__(self):
        self.sent = []
        self.redispatched = []

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        self.sent.append((chat_id, content))

    async def handle_message(self, event):
        self.redispatched.append(event)
        # the gateway runs the hook again on re-dispatch
        plugin.on_dispatch(event=event, gateway=self.gateway)


class FakeGateway:
    def __init__(self, authorized=True):
        self.adapter = FakeAdapter()
        self.adapter.gateway = self
        self.authorized = authorized

    def _is_user_authorized(self, source):
        return self.authorized

    def _adapter_for_source(self, source):
        return self.adapter

    def _thread_metadata_for_source(self, source):
        return {}


def _event(text, message_id="m1"):
    source = SimpleNamespace(platform=SimpleNamespace(value="telegram"), chat_id="42", user_id="7")
    return SimpleNamespace(text=text, source=source, message_id=message_id, media_urls=[])


def _register(answers, tmp_path):
    ctx = FakeCtx(answers)
    plugin.register(ctx)
    plugin._router = router_mod.Router(tmp_path / "decisions.jsonl")
    plugin._passthrough.clear()
    return ctx


def _run_dispatch(answers, text, tmp_path, authorized=True):
    gw = FakeGateway(authorized)
    _register(answers, tmp_path)

    async def go():
        result = plugin.on_dispatch(event=_event(text), gateway=gw)
        for _ in range(20):
            await asyncio.sleep(0)
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending)
        return result

    return asyncio.run(go()), gw


def test_dispatch_rule_forced_message_passes_through_untouched(tmp_path):
    result, gw = _run_dispatch({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "Lima."}, "Dodaj T12 do kanbana", tmp_path)
    assert result is None
    assert gw.adapter.sent == [] and gw.adapter.redispatched == []


def test_dispatch_free_answer_is_sent_through_the_adapter(tmp_path):
    result, gw = _run_dispatch({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "Lima."}, "Jaka jest stolica Peru?", tmp_path)
    assert result == {"action": "skip", "reason": "cheap-route: evaluating"}
    assert len(gw.adapter.sent) == 1 and gw.adapter.sent[0][0] == "42"
    assert gw.adapter.sent[0][1].startswith("Lima.") and "darmowego kanału" in gw.adapter.sent[0][1]
    assert gw.adapter.redispatched == []


def test_dispatch_hermes_decision_is_redispatched_once(tmp_path):
    answers = {plugin.ROUTER_TASK: '{"route": "hermes", "confidence": 0.9}', plugin.FREE_TASK: "Lima."}
    result, gw = _run_dispatch(answers, "Jaka jest stolica Peru?", tmp_path)
    assert result["action"] == "skip"
    assert gw.adapter.sent == []
    assert len(gw.adapter.redispatched) == 1
    assert plugin._passthrough == set()


def test_dispatch_evaluator_failure_redispatches(tmp_path):
    answers = {plugin.ROUTER_TASK: RuntimeError("down"), plugin.FREE_TASK: "Lima."}
    result, gw = _run_dispatch(answers, "Jaka jest stolica Peru?", tmp_path)
    assert result["action"] == "skip"
    assert gw.adapter.sent == [] and len(gw.adapter.redispatched) == 1


def test_dispatch_unauthorized_sender_is_left_to_the_gateway(tmp_path):
    result, gw = _run_dispatch({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "Lima."},
                               "Jaka jest stolica Peru?", tmp_path, authorized=False)
    assert result is None and gw.adapter.sent == []


def test_dispatch_commands_and_media_are_left_to_the_gateway(tmp_path):
    gw = FakeGateway()
    _register({plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "Lima."}, tmp_path)
    assert plugin.on_dispatch(event=_event("/route"), gateway=gw) is None
    ev = _event("Jaka jest stolica Peru?")
    ev.media_urls = ["/tmp/x.jpg"]
    assert plugin.on_dispatch(event=ev, gateway=gw) is None


class V020Llm:
    """Hermes v0.20 ``PluginLlm.complete``: no ``task`` keyword, it would run on the main model."""

    def __init__(self):
        self.calls = []

    def complete(self, messages, *, provider=None, model=None, temperature=None, max_tokens=None,
                 timeout=None, agent_id=None, profile=None, purpose=None):
        self.calls.append(messages[-1]["content"])
        raise AssertionError("main model must not be used")


def _fake_aux_client(monkeypatch, answers):
    calls = []

    def call_llm(task=None, *, messages, **kw):
        calls.append((task, kw))
        answer = answers[task]
        if isinstance(answer, Exception):
            raise answer
        message = types.SimpleNamespace(content=answer)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    agent_pkg = types.ModuleType("agent")
    aux = types.ModuleType("agent.auxiliary_client")
    aux.call_llm = call_llm
    agent_pkg.auxiliary_client = aux
    monkeypatch.setitem(sys.modules, "agent", agent_pkg)
    monkeypatch.setitem(sys.modules, "agent.auxiliary_client", aux)
    return calls


def test_v020_llm_goes_through_auxiliary_tasks_not_the_main_model(tmp_path, monkeypatch):
    calls = _fake_aux_client(monkeypatch, {plugin.ROUTER_TASK: FREE, plugin.FREE_TASK: "Lima."})
    gw = FakeGateway(True)
    ctx = _register({}, tmp_path)
    ctx.llm = V020Llm()
    ctx.settings["router_timeout"] = 8

    async def go():
        plugin.on_dispatch(event=_event("Jaka jest stolica Peru?"), gateway=gw)
        for _ in range(20):
            await asyncio.sleep(0)
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending)

    asyncio.run(go())
    assert [t for t, _ in calls] == [plugin.ROUTER_TASK, plugin.FREE_TASK]
    assert calls[0][1]["timeout"] == 8.0 and calls[0][1]["temperature"] == 0.0
    assert ctx.llm.calls == []
    assert gw.adapter.sent and "Lima." in gw.adapter.sent[0][1]
