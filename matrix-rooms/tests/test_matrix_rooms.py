"""Behaviour tests for matrix-rooms with a fake gateway runner and a fake mautrix client (no Hermes needed)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "matrix_rooms_plugin", HERE / "plugin" / "__init__.py", submodule_search_locations=[str(HERE / "plugin")])
plugin = importlib.util.module_from_spec(spec)
sys.modules["matrix_rooms_plugin"] = plugin
spec.loader.exec_module(plugin)
briefs = plugin


class FakeCtx:
    def __init__(self, settings=None):
        self.settings, self.tools, self.hooks = settings or {}, {}, {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_tool(self, name, toolset, schema, handler, **kw):
        self.tools[name] = (toolset, schema, handler, kw)

    def register_hook(self, name, fn):
        self.hooks[name] = fn


class FakeClient:
    def __init__(self):
        self.calls = []

    async def create_room(self, **kw):
        self.calls.append(kw)
        return "!new:example.org"


class FakeAdapter:
    def __init__(self):
        self._client = FakeClient()
        self._joined_rooms = set()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Running gateway loop in a thread, fake runner with a Matrix adapter, session env, brief store in tmp."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    adapter = FakeAdapter()
    session = {"HERMES_SESSION_USER_ID": "@filip:example.org", "HERMES_SESSION_CHAT_ID": "!main:example.org"}
    monkeypatch.setattr(plugin, "_matrix_adapter_and_loop", lambda: (adapter, loop))
    monkeypatch.setattr(plugin, "_session_env", lambda name: session.get(name, ""))
    monkeypatch.setattr(plugin, "_store", briefs.BriefStore(tmp_path / "briefs.json"))
    # mautrix stand-ins (the plugin imports them lazily inside the gateway).
    types_mod = types.ModuleType("mautrix.types")
    types_mod.RoomCreatePreset = types.SimpleNamespace(TRUSTED_PRIVATE="trusted_private_chat")
    types_mod.UserID = str
    monkeypatch.setitem(sys.modules, "mautrix", types.ModuleType("mautrix"))
    monkeypatch.setitem(sys.modules, "mautrix.types", types_mod)
    plugin.register(FakeCtx())
    yield types.SimpleNamespace(adapter=adapter, session=session)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)


def test_register_exposes_tool_and_hooks():
    ctx = FakeCtx()
    plugin.register(ctx)
    assert "matrix_room_create" in ctx.tools
    assert ctx.tools["matrix_room_create"][0] == "matrix_rooms"
    assert set(ctx.hooks) == {"pre_llm_call"}


def test_create_room_is_encrypted_and_invites_the_sender(env):
    out = json.loads(plugin.matrix_room_create({"name": "Research: laptop", "brief": "Find a laptop under 5k."}))
    assert out["success"] and out["room_id"] == "!new:example.org"
    call = env.adapter._client.calls[0]
    assert call["invitees"] == ["@filip:example.org"]
    assert call["preset"] == "trusted_private_chat"
    assert call["initial_state"][0]["type"] == "m.room.encryption"
    assert "!new:example.org" in env.adapter._joined_rooms


def test_brief_goes_to_first_turn_in_new_room_only_once(env):
    plugin.matrix_room_create({"name": "Projekt X", "brief": "Cel: zrobić X."})
    env.session["HERMES_SESSION_CHAT_ID"] = "!new:example.org"
    first = plugin.on_pre_llm_call(platform="matrix")
    assert "Cel: zrobić X." in first["context"] and "Projekt X" in first["context"]
    assert plugin.on_pre_llm_call(platform="matrix") is None


def test_no_injection_in_other_rooms_or_platforms(env):
    plugin.matrix_room_create({"name": "Projekt X", "brief": "Cel."})
    assert plugin.on_pre_llm_call(platform="matrix") is None  # still in the main room
    env.session["HERMES_SESSION_CHAT_ID"] = "!new:example.org"
    assert plugin.on_pre_llm_call(platform="telegram") is None


def test_falls_back_to_allowed_users(env, monkeypatch):
    env.session.pop("HERMES_SESSION_USER_ID")
    monkeypatch.setenv("MATRIX_ALLOWED_USERS", "@admin:example.org,@other:example.org")
    plugin.matrix_room_create({"name": "A", "brief": "B"})
    assert env.adapter._client.calls[0]["invitees"] == ["@admin:example.org"]


def test_errors_are_reported_not_raised(env, monkeypatch):
    assert "error" in json.loads(plugin.matrix_room_create({"name": "", "brief": "x"}))
    monkeypatch.setattr(plugin, "_matrix_adapter_and_loop", lambda: (None, None))
    assert "error" in json.loads(plugin.matrix_room_create({"name": "A", "brief": "B"}))


def test_create_failure_returns_error(env):
    async def boom(**kw):
        raise RuntimeError("M_FORBIDDEN")
    env.adapter._client.create_room = boom
    out = json.loads(plugin.matrix_room_create({"name": "A", "brief": "B"}))
    assert "M_FORBIDDEN" in out["error"]


def test_expired_briefs_are_dropped(tmp_path, monkeypatch):
    store = briefs.BriefStore(tmp_path / "b.json")
    store.put("!old:x", "Old", "brief")
    data = json.loads((tmp_path / "b.json").read_text())
    data["!old:x"]["created"] = 0
    (tmp_path / "b.json").write_text(json.dumps(data))
    assert store.take("!old:x") is None
