"""matrix-rooms — Hermes opens a new Matrix room for a project or a long task.

Filip's rule (24.10.2026): the main Matrix chat is for notifications, recurring things, quick talk and
current matters; projects, research and long tasks get their own room, so each has its own session and
context. Clicking works without this plugin (Filip creates a room in Element and invites the bot, which
auto-joins). This plugin covers "załóż pokój X" and Hermes deciding to move a big task by itself.

``matrix_room_create`` creates an encrypted private room through the gateway's live Matrix adapter
(same E2EE device), invites Filip with admin rights, and stores the task brief. The bot cannot start a
turn by itself in the new room, so the brief is appended (``pre_llm_call``) to Filip's first message
there. Adapter calls run on the gateway's own event loop (``runner._gateway_loop``), like voice_mirror.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_BRIEF_CHARS = 12_000
# A brief nobody picked up within this time is dropped (the room stays).
BRIEF_TTL_SECONDS = 30 * 24 * 3600


class BriefStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".matrix-rooms-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def put(self, room_id: str, name: str, brief: str, origin_room: str = "") -> None:
        with self._lock:
            data = self._load()
            data[room_id] = {"name": name, "brief": brief[:MAX_BRIEF_CHARS], "origin_room": origin_room,
                             "created": time.time()}
            self._save(data)

    def take(self, room_id: str) -> Optional[dict]:
        """Return and remove the brief for ``room_id`` (expired briefs are pruned on the way)."""
        with self._lock:
            data = self._load()
            now = time.time()
            fresh = {k: v for k, v in data.items()
                     if isinstance(v, dict) and now - float(v.get("created", 0)) < BRIEF_TTL_SECONDS}
            entry = fresh.pop(room_id, None)
            if entry is not None or len(fresh) != len(data):
                self._save(fresh)
            return entry


def brief_context(entry: dict) -> str:
    """Text appended to the first user message in the new room."""
    origin = entry.get("origin_room") or "główna rozmowa"
    return (
        f"[Kontekst pokoju „{entry.get('name', '')}”: to zadanie przeniesiono tu z rozmowy {origin}. "
        "Streszczenie zadania od Hermesa:]\n"
        f"{entry.get('brief', '')}\n"
        "[Zacznij od krótkiego potwierdzenia, czym zajmujemy się w tym pokoju, potem pracuj dalej.]"
    )


TOOLSET = "matrix_rooms"
CALL_TIMEOUT_SECONDS = 30

_ctx: Any = None
_store: Optional[BriefStore] = None

SCHEMA = {
    "name": "matrix_room_create",
    "description": (
        "Open a new private, encrypted Matrix room with Filip for one topic, so it gets its own session "
        "and context. Use it when Filip asks for a new room/conversation (\"załóż pokój …\"), and on your "
        "own when, in the MAIN Matrix chat, a request is a project, research, a long multi-step task or "
        "anything likely to take many tokens. The main chat is for notifications, recurring things, quick "
        "talk and current matters. Before moving a task on your own, say so in one line. The brief must be "
        "self-contained (goal, what is known, constraints, links, next steps): the new room starts with no "
        "history. After the call tell Filip to accept the invite and write in the new room; you continue "
        "there with the brief. Do not use it inside a room that is already about one topic."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Short room name, e.g. \"Research: laptop\" (max 60 chars)."},
            "brief": {"type": "string", "description": "Self-contained task brief for the first turn in the new room."},
            "topic": {"type": "string", "description": "Optional one-line room topic shown in the client."},
        },
        "required": ["name", "brief"],
    },
}


def _setting(key: str, default: Any) -> Any:
    try:
        value = _ctx.get_config(key, default)
    except Exception:
        return default
    return default if value is None else value


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _briefs() -> BriefStore:
    global _store
    if _store is None:
        _store = BriefStore(_hermes_home() / "matrix_rooms" / "briefs.json")
    return _store


def _session_env(name: str) -> str:
    try:
        from gateway.session_context import get_session_env
        return get_session_env(name, "") or ""
    except Exception:
        return os.environ.get(name, "")


def _matrix_adapter_and_loop():
    """``(adapter, loop)`` of the running gateway, or ``(None, None)`` outside it (cron, CLI)."""
    try:
        from gateway.config import Platform
        from gateway.run import _gateway_runner_ref
        runner = _gateway_runner_ref()
    except Exception:
        return None, None
    if runner is None:
        return None, None
    loop = getattr(runner, "_gateway_loop", None)
    if loop is not None and loop.is_closed():
        loop = None
    return getattr(runner, "adapters", {}).get(Platform.MATRIX), loop


def _invitee() -> str:
    """Who to invite: the Matrix user of this turn, else the first allowed user."""
    user = _session_env("HERMES_SESSION_USER_ID")
    if user.startswith("@"):
        return user
    for candidate in (_setting("invite", "") or os.environ.get("MATRIX_ALLOWED_USERS", "")).split(","):
        candidate = candidate.strip()
        if candidate.startswith("@"):
            return candidate
    return ""


async def _create(adapter, name: str, topic: str, invitee: str) -> str:
    from mautrix.types import RoomCreatePreset, UserID

    client = adapter._client
    initial_state = [{"type": "m.room.encryption", "state_key": "",
                      "content": {"algorithm": "m.megolm.v1.aes-sha2"}}]
    room_id = await client.create_room(
        name=name, topic=topic or None, invitees=[UserID(invitee)], is_direct=False,
        preset=RoomCreatePreset.TRUSTED_PRIVATE, initial_state=initial_state)
    room_id = str(room_id)
    joined = getattr(adapter, "_joined_rooms", None)
    if isinstance(joined, set):
        joined.add(room_id)
    return room_id


def matrix_room_create(args: dict, **_: Any) -> str:
    name = " ".join(str(args.get("name") or "").split())[:60]
    brief = str(args.get("brief") or "").strip()
    topic = " ".join(str(args.get("topic") or "").split())[:200]
    if not name or not brief:
        return json.dumps({"error": "name and brief are required"})
    adapter, loop = _matrix_adapter_and_loop()
    if adapter is None or loop is None or getattr(adapter, "_client", None) is None:
        return json.dumps({"error": "Matrix is not connected in this gateway (rooms can only be created from a gateway turn)."})
    invitee = _invitee()
    if not invitee:
        return json.dumps({"error": "No Matrix user to invite (MATRIX_ALLOWED_USERS is empty)."})
    try:
        future = asyncio.run_coroutine_threadsafe(_create(adapter, name, topic, invitee), loop)
        room_id = future.result(timeout=CALL_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("matrix-rooms: create_room failed: %s", exc)
        return json.dumps({"error": f"Creating the room failed: {exc}"})
    origin = _session_env("HERMES_SESSION_CHAT_NAME") or _session_env("HERMES_SESSION_CHAT_ID")
    _briefs().put(room_id, name, brief, origin_room=origin)
    logger.info("matrix-rooms: created %s (%s), invited %s", room_id, name, invitee)
    return json.dumps({
        "success": True, "room_id": room_id, "name": name, "invited": invitee,
        "link": f"https://matrix.to/#/{room_id}",
        "next": "Tell Filip (one line, in Polish) to accept the invite to this room and write there; "
                "the brief is handed to your first turn in that room.",
    }, ensure_ascii=False)


def on_pre_llm_call(platform: str = "", **_: Any) -> Optional[dict]:
    if platform and platform != "matrix":
        return None
    room_id = _session_env("HERMES_SESSION_CHAT_ID")
    if not room_id.startswith("!"):
        return None
    try:
        entry = _briefs().take(room_id)
    except Exception:
        logger.warning("matrix-rooms: reading the brief failed", exc_info=True)
        return None
    if not entry:
        return None
    logger.info("matrix-rooms: handed the brief to the first turn in %s", room_id)
    return {"context": brief_context(entry)}


def _matrix_configured() -> bool:
    if os.environ.get("MATRIX_HOMESERVER") or os.environ.get("MATRIX_USER_ID"):
        return True
    return _matrix_adapter_and_loop()[0] is not None


def register(ctx: Any) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_tool(
        name="matrix_room_create", toolset=TOOLSET, schema=SCHEMA, handler=matrix_room_create,
        check_fn=_matrix_configured, description=SCHEMA["description"], emoji="🚪")
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
