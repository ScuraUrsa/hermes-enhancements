"""Pure logic of pantry-guard: per-session turn buffer and the reply check (no Hermes imports)."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

# "dodałem", "zapisałam", "zaktualizowałem", "przeniosłem", "usunąłem", "wyrzuciłem", "zmieniłem",
# "oznaczyłem", "wpisałem", "odnotowałem", plus the impersonal "dodano/zapisano/…" forms.
_CLAIM = re.compile(
    r"\b(?:"
    r"doda(?:łe|ła)m|dodano"
    r"|zapisa(?:łe|ła)m|zapisano"
    r"|zaktualizowa(?:łe|ła)m|zaktualizowano"
    r"|przeni(?:osłe|osła)m|przeniesiono"
    r"|usun(?:ąłe|ęła)m|usunięto"
    r"|wyrzuci(?:łe|ła)m|wyrzucono"
    r"|zmieni(?:łe|ła)m|zmieniono"
    r"|oznaczy(?:łe|ła)m|oznaczono"
    r"|wpisa(?:łe|ła)m|wpisano"
    r"|odnotowa(?:łe|ła)m|odnotowano"
    r"|zużyto"
    r"|(?:zapisa|doda|zaktualizowa)(?:ne|ny|na)|przeniesi(?:one|ony|ona)|usunię(?:te|ty|ta)"
    r")\b",
    re.IGNORECASE,
)

# A reply that already says something was NOT saved is honest about the failure.
_ADMITS_FAILURE = re.compile(r"nie\s+(?:zosta\w+\s+)?(?:za)?pisa|nie\s+uda|❌|nie\s+doda|nie\s+zapisano", re.IGNORECASE)

# Words that tie a turn to the pantry / apartment map when no dom.py call happened at all.
_PANTRY_WORDS = re.compile(
    r"spiżar|lodów|zamrażar|szaf|półk|szuflad|komod|regał|piwnic|mapa\s+mieszkania|termin\s+ważno|ważn[ey]\s+do"
    r"|przywioz|kupi[łl]|zuży|wyrzuci|chemi[aię]|ubrani",
    re.IGNORECASE,
)

_DOM = re.compile(r"(?:^|[\s/'\"])dom\.py\b|(?:^|[\s;&|])dom\s+(?:add|use|throw|move|set|batch|map)\b")


@dataclass
class DomCall:
    command: str
    exit_code: Optional[int]
    output: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    @property
    def failed_lines(self) -> list[str]:
        return [ln.strip() for ln in self.output.splitlines() if ln.lstrip().startswith("❌")]

    @property
    def any_success(self) -> bool:
        """True when the call saved at least one thing (exit 0, or a partial batch with ✅ lines)."""
        return self.ok or any(ln.lstrip().startswith("✅") for ln in self.output.splitlines())


@dataclass
class Turn:
    user_message: str = ""
    calls: list[DomCall] = field(default_factory=list)


def is_dom_command(command: str) -> bool:
    return bool(command) and bool(_DOM.search(command))


def parse_terminal_result(result: Any) -> tuple[Optional[int], str]:
    """``(exit_code, output)`` from the terminal tool envelope ``{"output", "exit_code", "error"}``."""
    data = result
    if isinstance(result, str):
        try:
            data = json.loads(result)
        except (ValueError, TypeError):
            return None, result
    if not isinstance(data, dict):
        return None, str(result or "")
    code = data.get("exit_code")
    try:
        code = int(code) if code is not None else None
    except (TypeError, ValueError):
        code = None
    output = str(data.get("output") or "")
    if data.get("error"):
        output = (output + "\n" + str(data["error"])).strip()
    return code, output


class Buffer:
    """Per-session record of the current turn. pre_llm_call resets it; post_tool_call fills it."""

    def __init__(self, max_sessions: int = 256):
        self._turns: dict[str, Turn] = {}
        self._lock = threading.Lock()
        self._max = max_sessions

    def start(self, session_id: str, user_message: str = "") -> None:
        with self._lock:
            self._turns.pop(session_id, None)
            if len(self._turns) >= self._max:
                self._turns.pop(next(iter(self._turns)))
            self._turns[session_id] = Turn(user_message=user_message or "")

    def record(self, session_id: str, call: DomCall) -> None:
        with self._lock:
            self._turns.setdefault(session_id, Turn()).calls.append(call)

    def take(self, session_id: str) -> Turn:
        with self._lock:
            return self._turns.pop(session_id, None) or Turn()


NOT_SAVED = (
    "⚠️ Nic nie zostało zapisane w spiżarni. Odpowiedź modelu mówiła, że zapisał, "
    "ale nie było udanego wywołania dom.py w tej turze. Napisz proszę jeszcze raz, co dodać."
)


# An empty final reply as Hermes hands it to the hook: blank, the "(empty)" sentinel, or the
# turn-completion explainer's "⚠️ No reply: …" (empty content after retries).
_NO_REPLY = re.compile(r"^\s*(?:\(empty\)\s*$|⚠️\s*No reply:)")

NO_REPLY_HEADER = "Model nie napisał odpowiedzi. Wynik dom.py z tej tury:"
_MAX_FALLBACK_LINES = 15


def _call_summary(call: DomCall) -> list[str]:
    lines = [ln.strip() for ln in call.output.splitlines() if ln.strip()]
    marked = [ln for ln in lines if ln.startswith(("✅", "❌", "Wykonano"))]
    if marked:
        return marked
    mark = "✅" if call.ok else f"❌ (exit {call.exit_code})"
    return [f"{mark} {ln}" for ln in lines[:5]] or [mark]


def fallback_reply(turn: Turn) -> str:
    lines = [ln for c in turn.calls for ln in _call_summary(c)]
    if len(lines) > _MAX_FALLBACK_LINES:
        lines = lines[:_MAX_FALLBACK_LINES] + ["…"]
    return NO_REPLY_HEADER + "\n" + "\n".join(lines)


def check(reply: str, turn: Turn) -> Optional[str]:
    """Return the replacement reply, or None when the reply may go out unchanged."""
    if turn.calls and (not (reply or "").strip() or _NO_REPLY.match(reply)):
        # Thinking ate the answer after dom.py ran: show what dom.py actually did.
        return fallback_reply(turn)
    if not reply or not _CLAIM.search(reply):
        return None
    if not turn.calls:
        # No dom.py at all: only a pantry-related claim is ours to stop.
        if not (_PANTRY_WORDS.search(reply) or _PANTRY_WORDS.search(turn.user_message)):
            return None
        if _ADMITS_FAILURE.search(reply):
            return None
        return NOT_SAVED
    if not any(c.any_success for c in turn.calls):
        if _ADMITS_FAILURE.search(reply):
            return None
        return NOT_SAVED
    failed = [ln for c in turn.calls for ln in c.failed_lines]
    if failed and not _ADMITS_FAILURE.search(reply):
        return reply.rstrip() + "\n\n⚠️ Tego NIE zapisano:\n" + "\n".join(failed)
    return None
