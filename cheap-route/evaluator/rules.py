"""Hard rules that decide a route without asking the model.

They only ever force ``hermes``: anything that mentions Filip's own systems, data,
identifiers or asks for an action stays with the agent. ``None`` means "ask the model".
"""

from __future__ import annotations

import re

# Identifiers from timeplane / kanban / git that a public chatbot cannot know about.
_IDS = re.compile(r"\b(T\d{1,4}|G\d{1,2}|Q[1-4]|R\d{1,3}|PR\s?#?\d+|t_[0-9a-f]{6,})\b")

# Names of services and places that only exist in Filip's setup.
_MINE = re.compile(
    r"\b(hermes|honcho|kanban|timeplane|crewai|ollama|claude|notion|bitwarden|bws|syncthing|"
    r"home assistant|unity-orchestrator|vm|wobi|matrix|tailscale|rclone|quota|budget\.py|"
    r"koalamis6|praktyki\.ftims|kazmierczak)\b",
    re.I,
)

# Possessives and first-person references in Polish and English.
_PERSONAL = re.compile(
    r"\b(mój|moja|moje|moich|moim|moją|mojego|mojej|mnie|u mnie|nasz|nasza|nasze|naszej|"
    r"mam|mamy|chcę|chce|muszę|musze|jadę|jade|idę|ide|czuję|czuje|zrobiłem|zrobilem|wróciłem|wrocilem|"
    r"my|mine|our|i have|i want|i need)\b",
    re.I,
)

# Second-person forms and planning words addressed to the agent ("jak implementujesz", "pomysł: ...").
_SECOND_PERSON = re.compile(
    r"\b(ty|ciebie|tobie|twój|twoja|twoje|twoich|twoim|implementujesz|robisz|masz|możesz|mozesz|potrafisz|"
    r"pamiętasz|pamietasz|wiesz|widzisz|pomysł|pomysl|lista rozwiązań|lista rozwiazan|budżet|budzet|budget|"
    r"you|your|yours|idea|budget)\b",
    re.I,
)

# File names, scripts and exit codes: questions about code that only Filip's repos hold.
_CODE = re.compile(r"\b\w+\.(py|sh|ps1|yml|yaml|md|json|toml|service|env)\b|\bexit\s?\d+\b|\bcc_run\b", re.I)

# Requests for an action the agent must perform.
_ACTION = re.compile(
    r"\b(dodaj|wyślij|wyslij|uruchom|zapisz|przesuń|przesun|przypomnij|zapamiętaj|zapamietaj|"
    r"sprawdź|sprawdz|zrób|zrob|usuń|usun|wpisz|wykonaj|zaplanuj|zainstaluj|napraw|"
    r"add|send|run|save|move|remind|remember|check|delete|install|fix|open|start|stop)\b",
    re.I,
)

# Conversation glue, pings and tests: never worth a public chatbot.
_GLUE = re.compile(
    r"^(ok|okej|dzięki|dzieki|thanks|thx|tak|nie|wróciłem|wrocilem|idę|ide|test|ping|hej|cześć|czesc|"
    r"are you there|działa\??|jesteś\??)\b",
    re.I,
)


def hard_route(text: str, has_tool_history: bool = False) -> str | None:
    """Return ``"hermes"`` when a rule fires, else ``None`` (let the model decide)."""
    t = (text or "").strip()
    if not t or len(t) < 8:
        return "hermes"
    if has_tool_history:
        return "hermes"
    if _GLUE.match(t) or _IDS.search(t) or _MINE.search(t) or _PERSONAL.search(t) or _ACTION.search(t):
        return "hermes"
    if _SECOND_PERSON.search(t) or _CODE.search(t):
        return "hermes"
    if "@" in t or "~/" in t or re.search(r"[A-Z]:\\", t) or "github.com/ScuraUrsa" in t:
        return "hermes"
    return None
