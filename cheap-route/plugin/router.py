"""Routing logic for the cheap-route plugin, kept free of Hermes imports so it is unit-testable.

``decide`` combines the hard rules with the evaluator model; ``Router`` holds the per-session
memory (a short follow-up after an agent turn stays with the agent) and the decision log.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .rules import hard_route

FREE_WEB = "free_web"
HERMES = "hermes"

# A follow-up this short, this soon after an agent turn, continues that conversation.
_FOLLOWUP_MAX_CHARS = 60
_FOLLOWUP_WINDOW_S = 15 * 60


@dataclass
class Decision:
    route: str
    confidence: float
    reason: str
    by_rule: bool = False
    raw: dict = field(default_factory=dict)


def parse_model_json(text: str) -> dict:
    """The evaluator answers with one JSON object; tolerate prose around it."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def decide(text: str, evaluate: Callable[[str], str], threshold: float, *, has_recent_agent_turn: bool = False) -> Decision:
    """Rules first (they only ever force ``hermes``), then the model; anything unclear → ``hermes``."""
    forced = hard_route(text)
    if forced is None and has_recent_agent_turn and len(text.strip()) <= _FOLLOWUP_MAX_CHARS:
        forced = HERMES
    if forced is not None:
        return Decision(forced, 1.0, "rule", by_rule=True)
    raw = parse_model_json(evaluate(text))
    route = str(raw.get("route", HERMES)).strip().lower()
    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(raw.get("reason", ""))[:120]
    if route == FREE_WEB and confidence >= threshold:
        return Decision(FREE_WEB, confidence, reason, raw=raw)
    return Decision(HERMES, confidence, reason or "below threshold", raw=raw)


class Router:
    """Per-process state: last route per session and an append-only JSONL decision log."""

    def __init__(self, log_path: Optional[Path]):
        self._log_path = log_path
        self._last: dict[str, tuple[str, float]] = {}

    def recent_agent_turn(self, session_key: str, now: Optional[float] = None) -> bool:
        last = self._last.get(session_key)
        if not last:
            return False
        route, when = last
        return route == HERMES and (now or time.time()) - when < _FOLLOWUP_WINDOW_S

    def remember(self, session_key: str, route: str, now: Optional[float] = None) -> None:
        self._last[session_key] = (route, now or time.time())

    def log(self, session_key: str, platform: str, text: str, decision: Decision, outcome: str, latency_s: float) -> None:
        if self._log_path is None:
            return
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "session": session_key, "platform": platform,
            "text": text[:120], "route": decision.route, "confidence": round(decision.confidence, 2),
            "reason": decision.reason, "by_rule": decision.by_rule, "outcome": outcome,
            "latency_s": round(latency_s, 2),
        }
        with open(self._log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def stats(self, last_n: int = 200) -> dict:
        """Counts over the newest ``last_n`` log rows, for ``/route status``."""
        if self._log_path is None or not self._log_path.exists():
            return {"rows": 0}
        rows = []
        with open(self._log_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        rows = rows[-last_n:]
        free = [r for r in rows if r.get("route") == FREE_WEB]
        answered = [r for r in free if r.get("outcome") == "answered"]
        return {
            "rows": len(rows), "free_web": len(free), "answered_free": len(answered),
            "fallbacks": len(free) - len(answered),
            "by_rule": sum(1 for r in rows if r.get("by_rule")),
        }
