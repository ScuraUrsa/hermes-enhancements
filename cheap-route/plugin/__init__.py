"""cheap-route — decide before the agent turn whether a free LLM channel can answer.

``post_gateway_admission`` runs every inbound gateway message through the hard rules and the
evaluator model (auxiliary task ``cheap_route_router``, meant for a local llama-server). A
general-knowledge question with no personal context is answered by the free channel (auxiliary
task ``cheap_route_free``, e.g. Gemini on the free API tier) and the agent turn is skipped.
Everything else, and every failure, falls through to the ordinary Hermes turn.

Older Hermes (the fork pin a6ede70 / v0.20.0 on the prod VM) has no ``post_gateway_admission``;
there the plugin uses ``pre_gateway_dispatch`` (sync, before auth): rule-forced messages pass
through untouched, the rest is taken over (``skip``), evaluated in a thread, answered through the
adapter, or re-dispatched to the gateway unchanged when Hermes should handle it.

Settings (``plugins.entries.cheap-route.settings``): ``enabled`` (true), ``threshold`` (0.8),
``footer`` (true), ``platforms`` (list; empty = all), ``max_answer_chars`` (2000), ``router_timeout``
(seconds, 30).
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from .router import FREE_WEB, HERMES, Router, decide
from .rules import hard_route

logger = logging.getLogger(__name__)

ROUTER_TASK = "cheap_route_router"
FREE_TASK = "cheap_route_free"
PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")

_FREE_SYSTEM = (
    "Odpowiadasz krótko i rzeczowo po polsku (albo w języku pytania). Nie masz dostępu do żadnych "
    "prywatnych danych użytkownika; jeśli pytanie ich wymaga, powiedz, że trzeba zapytać Hermesa."
)

_FOOTER = "\n\n_[odpowiedź z darmowego kanału; napisz „Hermes, …”, jeśli chcesz pełnej obsługi]_"

_ctx: Any = None
_router: Optional[Router] = None
# Events the compat hook already evaluated and re-dispatched: let them through on the second pass.
_passthrough: set = set()


def _setting(key: str, default: Any) -> Any:
    getter = getattr(_ctx, "get_config", None)
    if getter is None:  # older Hermes: read plugins.entries.cheap-route.settings from config.yaml
        getter = _setting_from_config
    try:
        value = getter(key, default)
    except Exception:
        return default
    return default if value is None else value


def _setting_from_config(key: str, default: Any) -> Any:
    from hermes_cli.config import load_config

    entries = ((load_config() or {}).get("plugins") or {}).get("entries") or {}
    settings = (entries.get("cheap-route") or {}).get("settings") or {}
    return settings.get(key, default)


def _llm_takes_task() -> bool:
    try:
        return "task" in inspect.signature(_ctx.llm.complete).parameters
    except (TypeError, ValueError):
        return True


def _complete(task: str, messages: list, purpose: str, **kw: Any) -> str:
    """Run ``messages`` on the auxiliary ``task``, never on the user's main model.

    Newer Hermes routes ``ctx.llm.complete(task=...)`` through the plugin's auxiliary slot. In v0.20
    ``PluginLlm.complete`` has no ``task`` (it would use the main model), so go to the auxiliary
    client directly; it reads ``auxiliary.<task>`` with the defaults registered below.
    """
    if _llm_takes_task():
        return _ctx.llm.complete(messages=messages, task=task, purpose=purpose, **kw).text or ""
    from agent.auxiliary_client import call_llm

    response = call_llm(task=task, messages=messages, **kw)
    return response.choices[0].message.content or ""


def _evaluate(text: str) -> str:
    return _complete(
        ROUTER_TASK, [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
        "cheap-route.evaluate", temperature=0.0, max_tokens=200, timeout=float(_setting("router_timeout", 30)),
    )


def _answer_free(text: str) -> str:
    return _complete(
        FREE_TASK, [{"role": "system", "content": _FREE_SYSTEM}, {"role": "user", "content": text}],
        "cheap-route.answer", max_tokens=1024, timeout=60,
    ).strip()


def on_admission(session_key: str = "", platform: str = "", text: str = "", **_: Any) -> Optional[dict]:
    """Consume the message with a free answer, or return None so Hermes handles it."""
    if not _setting("enabled", True) or not text or not text.strip():
        return None
    platforms = _setting("platforms", []) or []
    if platforms and platform not in platforms:
        return None
    t0 = time.time()
    try:
        decision = decide(text, _evaluate, float(_setting("threshold", 0.8)),
                          has_recent_agent_turn=_router.recent_agent_turn(session_key))
    except Exception:  # evaluator down → the agent answers, as if the plugin were absent
        logger.warning("cheap-route: evaluator failed; agent turn", exc_info=True)
        return None
    if decision.route != FREE_WEB:
        _router.remember(session_key, HERMES)
        _router.log(session_key, platform, text, decision, "agent", time.time() - t0)
        return None
    try:
        answer = _answer_free(text)
    except Exception:
        logger.warning("cheap-route: free channel failed; agent turn", exc_info=True)
        answer = ""
    if not answer:
        _router.remember(session_key, HERMES)
        _router.log(session_key, platform, text, decision, "fallback", time.time() - t0)
        return None
    answer = _finish_answer(answer)
    _router.remember(session_key, FREE_WEB)
    _router.log(session_key, platform, text, decision, "answered", time.time() - t0)
    return {"action": "handled", "reply": answer}


def _finish_answer(answer: str) -> str:
    answer = answer[: int(_setting("max_answer_chars", 2000))]
    return answer + _FOOTER if _setting("footer", True) else answer


# ---------------------------------------------------------------- Hermes <= v0.20 (pre_gateway_dispatch)
def _event_key(event: Any) -> tuple:
    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", "") or ""
    return (platform, str(getattr(source, "chat_id", "")), str(getattr(event, "message_id", "") or id(event)))


def _session_key(event: Any) -> str:
    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", "") or ""
    return f"{platform}:{getattr(source, 'chat_id', '')}:{getattr(source, 'user_id', '') or ''}"


def on_dispatch(event: Any = None, gateway: Any = None, **_: Any) -> Optional[dict]:
    """Compat hook: take over a candidate message (``skip``) and finish it asynchronously."""
    if event is None or gateway is None or not _setting("enabled", True):
        return None
    text = (getattr(event, "text", "") or "").strip()
    if not text or text.startswith("/") or getattr(event, "media_urls", None):
        return None
    source = getattr(event, "source", None)
    platform = getattr(getattr(source, "platform", None), "value", "") or ""
    platforms = _setting("platforms", []) or []
    if platforms and platform not in platforms:
        return None
    key = _event_key(event)
    if key in _passthrough:
        _passthrough.discard(key)
        return None
    try:  # the hook runs before auth: never answer a stranger
        if not gateway._is_user_authorized(source):
            return None
    except Exception:
        return None
    session_key = _session_key(event)
    if hard_route(text) is not None or (
            _router.recent_agent_turn(session_key) and len(text) <= 60):
        _router.remember(session_key, HERMES)
        _router.log(session_key, platform, text, decide(text, lambda _t: "", 1.0,
                    has_recent_agent_turn=True), "agent", 0.0)
        return None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    loop.create_task(_dispatch_async(event, gateway, session_key, platform, text))
    return {"action": "skip", "reason": "cheap-route: evaluating"}


async def _dispatch_async(event: Any, gateway: Any, session_key: str, platform: str, text: str) -> None:
    t0 = time.time()
    answer = ""
    decision = None
    try:
        decision = await asyncio.to_thread(decide, text, _evaluate, float(_setting("threshold", 0.8)))
        if decision.route == FREE_WEB:
            answer = await asyncio.to_thread(_answer_free, text)
    except Exception:
        logger.warning("cheap-route: evaluator or free channel failed; agent turn", exc_info=True)
    source = event.source
    adapter = gateway._adapter_for_source(source)
    if answer and decision is not None:
        try:
            metadata = gateway._thread_metadata_for_source(source)
        except Exception:
            metadata = None
        try:
            await adapter.send(source.chat_id, _finish_answer(answer), metadata=metadata)
            _router.remember(session_key, FREE_WEB)
            _router.log(session_key, platform, text, decision, "answered", time.time() - t0)
            return
        except Exception:
            logger.warning("cheap-route: send failed; agent turn", exc_info=True)
    _router.remember(session_key, HERMES)
    if decision is not None:
        _router.log(session_key, platform, text, decision, "fallback" if decision.route == FREE_WEB else "agent",
                    time.time() - t0)
    _passthrough.add(_event_key(event))
    try:
        await adapter.handle_message(event)
    except Exception:
        _passthrough.discard(_event_key(event))
        logger.error("cheap-route: re-dispatch failed; message lost", exc_info=True)


def _route_command(raw_args: str) -> str:
    arg = (raw_args or "").strip().lower()
    if arg in ("on", "off"):
        setter = getattr(_ctx, "set_config", None)
        if setter is None:
            return "Ten Hermes nie zapisuje ustawień pluginów; wyłącz plugin w config.yaml (plugins.enabled)."
        setter("enabled", arg == "on")
        return f"cheap-route {'włączony' if arg == 'on' else 'wyłączony'}."
    s = _router.stats()
    state = "włączony" if _setting("enabled", True) else "wyłączony"
    return (f"cheap-route {state}, próg {_setting('threshold', 0.8)}. Ostatnie {s.get('rows', 0)} decyzji: "
            f"darmowy kanał {s.get('free_web', 0)} (odpowiedziane {s.get('answered_free', 0)}, "
            f"fallback {s.get('fallbacks', 0)}), reguły {s.get('by_rule', 0)}. "
            "Użyj `/route on|off`.")


def _pick_hook() -> str:
    """``post_gateway_admission`` where Hermes knows it, else the older ``pre_gateway_dispatch``."""
    try:
        from hermes_cli.plugins import VALID_HOOKS
    except Exception:
        return "post_gateway_admission"
    return "post_gateway_admission" if "post_gateway_admission" in VALID_HOOKS else "pre_gateway_dispatch"


def register(ctx: Any) -> None:
    global _ctx, _router
    _ctx = ctx
    try:
        from plugins.plugin_storage import plugin_data_dir
        log_path = plugin_data_dir("cheap-route") / "decisions.jsonl"
    except Exception:  # older Hermes without plugin_storage
        home = Path(os.environ.get("HERMES_HOME") or "~/.hermes").expanduser()
        log_path = home / "plugin-data" / "cheap-route" / "decisions.jsonl"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        log_path = None
    _router = Router(log_path)
    ctx.register_auxiliary_task(
        ROUTER_TASK, display_name="cheap-route: ewaluator",
        description="Mały lokalny model (llama.cpp), który klasyfikuje pytanie przed turą agenta.",
        # Qwen3.5 "thinks" by default and then returns no content within max_tokens: the chat-template
        # kwargs switch that off (llama-server also gets --chat-template-kwargs in the WOBI unit).
        defaults={"provider": "custom", "base_url": "http://127.0.0.1:8082/v1", "model": "local", "api_key": "none",
                  "extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
    )
    ctx.register_auxiliary_task(
        FREE_TASK, display_name="cheap-route: darmowy kanał",
        description="Darmowe API (np. Gemini na darmowym poziomie), które odpowiada na pytania ogólne.",
        defaults={"provider": "gemini", "model": "gemini-3.6-flash"},
    )
    ctx.register_hook(_pick_hook(), on_admission if _pick_hook() == "post_gateway_admission" else on_dispatch)
    ctx.register_command("route", _route_command, description="cheap-route: status, on, off", args_hint="[on|off]")
