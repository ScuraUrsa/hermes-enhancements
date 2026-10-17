"""pantry-guard — no "dodałem" from the pantry skill unless dom.py really saved something.

Small local models (Qwen3.5-4B on llama.cpp) sometimes reply "Dodałem mleko ✅" without calling
``dom.py`` at all, or after a batch where some lines failed. Hooks can only replace the final
text (no retry), so the guard replaces a false write claim with an honest "nothing was saved"
message, and appends the ❌ lines a partial batch reply left out.

Hooks: ``pre_llm_call`` resets the per-session buffer, ``post_tool_call`` records every terminal
call to dom.py with its exit code and output, ``transform_llm_output`` checks the reply.

Settings (``plugins.entries.pantry-guard.settings``): ``enabled`` (true), ``models`` (list of
model names to guard; ``["*"]`` = every model; default ``["qwen3.5-4b"]``).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .guard import Buffer, DomCall, check, is_dom_command, parse_terminal_result

logger = logging.getLogger(__name__)

DEFAULT_MODELS = ["qwen3.5-4b"]

_ctx: Any = None
_buffer = Buffer()


def _setting(key: str, default: Any) -> Any:
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    return default if value is None else value


def _guarded(model: str) -> bool:
    if not _setting("enabled", True):
        return False
    models = _setting("models", DEFAULT_MODELS) or []
    if "*" in models:
        return True
    name = (model or "").lower()
    return any(m and m.lower() in name for m in models)


def on_pre_llm_call(session_id: str = "", user_message: Any = "", **_: Any) -> None:
    text = user_message if isinstance(user_message, str) else ""
    _buffer.start(session_id or "", text)
    return None  # never inject context


def on_post_tool_call(tool_name: str = "", args: Any = None, result: Any = None, session_id: str = "",
                      **_: Any) -> None:
    if tool_name != "terminal" or not isinstance(args, dict):
        return
    command = str(args.get("command") or "")
    if not is_dom_command(command):
        return
    code, output = parse_terminal_result(result)
    _buffer.record(session_id or "", DomCall(command=command, exit_code=code, output=output))


def on_transform_llm_output(response_text: str = "", session_id: str = "", model: str = "",
                            **_: Any) -> Optional[str]:
    turn = _buffer.take(session_id or "")
    if not _guarded(model):
        return None
    try:
        replacement = check(response_text, turn)
    except Exception:  # fail open: never break a turn
        logger.warning("pantry-guard: check failed", exc_info=True)
        return None
    if replacement is not None:
        logger.warning("pantry-guard: replaced a write claim (session=%s, model=%s, dom calls=%d)",
                       session_id, model, len(turn.calls))
    return replacement


def register(ctx: Any) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("transform_llm_output", on_transform_llm_output)
