"""cheap-route — decide before the agent turn whether a free LLM channel can answer.

``post_gateway_admission`` runs every inbound gateway message through the hard rules and the
evaluator model (auxiliary task ``cheap_route_router``, meant for a local llama-server). A
general-knowledge question with no personal context is answered by the free channel (auxiliary
task ``cheap_route_free``, e.g. Gemini on the free API tier) and the agent turn is skipped.
Everything else, and every failure, falls through to the ordinary Hermes turn.

Settings (``plugins.entries.cheap-route.settings``): ``enabled`` (true), ``threshold`` (0.8),
``footer`` (true), ``platforms`` (list; empty = all), ``max_answer_chars`` (2000).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from .router import FREE_WEB, HERMES, Router, decide

logger = logging.getLogger(__name__)

ROUTER_TASK = "cheap_route_router"
FREE_TASK = "cheap_route_free"
PROMPT = (Path(__file__).parent / "prompt.md").read_text(encoding="utf-8")

_FREE_SYSTEM = (
    "Odpowiadasz krótko i rzeczowo po polsku (albo w języku pytania). Nie masz dostępu do żadnych "
    "prywatnych danych użytkownika; jeśli pytanie ich wymaga, powiedz, że trzeba zapytać Hermesa."
)

_ctx: Any = None
_router: Optional[Router] = None


def _setting(key: str, default: Any) -> Any:
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    return default if value is None else value


def _evaluate(text: str) -> str:
    result = _ctx.llm.complete(
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
        task=ROUTER_TASK, temperature=0.0, max_tokens=200, timeout=30, purpose="cheap-route.evaluate",
    )
    return result.text or ""


def _answer_free(text: str) -> str:
    result = _ctx.llm.complete(
        messages=[{"role": "system", "content": _FREE_SYSTEM}, {"role": "user", "content": text}],
        task=FREE_TASK, max_tokens=1024, timeout=60, purpose="cheap-route.answer",
    )
    return (result.text or "").strip()


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
    answer = answer[: int(_setting("max_answer_chars", 2000))]
    if _setting("footer", True):
        answer += "\n\n_[odpowiedź z darmowego kanału; napisz „Hermes, …”, jeśli chcesz pełnej obsługi]_"
    _router.remember(session_key, FREE_WEB)
    _router.log(session_key, platform, text, decision, "answered", time.time() - t0)
    return {"action": "handled", "reply": answer}


def _route_command(raw_args: str) -> str:
    arg = (raw_args or "").strip().lower()
    if arg in ("on", "off"):
        _ctx.set_config("enabled", arg == "on")
        return f"cheap-route {'włączony' if arg == 'on' else 'wyłączony'}."
    s = _router.stats()
    state = "włączony" if _setting("enabled", True) else "wyłączony"
    return (f"cheap-route {state}, próg {_setting('threshold', 0.8)}. Ostatnie {s.get('rows', 0)} decyzji: "
            f"darmowy kanał {s.get('free_web', 0)} (odpowiedziane {s.get('answered_free', 0)}, "
            f"fallback {s.get('fallbacks', 0)}), reguły {s.get('by_rule', 0)}. "
            "Użyj `/route on|off`.")


def register(ctx: Any) -> None:
    global _ctx, _router
    _ctx = ctx
    try:
        from plugins.plugin_storage import plugin_data_dir
        log_path = plugin_data_dir("cheap-route") / "decisions.jsonl"
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
    ctx.register_hook("post_gateway_admission", on_admission)
    ctx.register_command("route", _route_command, description="cheap-route: status, on, off", args_hint="[on|off]")
