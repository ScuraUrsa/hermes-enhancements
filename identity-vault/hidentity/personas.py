"""Identities agents create for Filip (Filip 2026-10-27: Hermes and Claude may create new identities).

Two kinds, both stored as Bitwarden *Identity* items in the identity folder next to ``Prawdziwy Ja``:

- ``self-variant``  a formal or private version of Filip: chosen fields copied from the real identity
                    inside this module (values never printed), with its own e-mail. It carries his real
                    data, so creating one asks Filip and using it asks every time by default.
- ``persona``       a generated identity, loosely or not at all tied to Filip (e.g. for sign-ups where
                    he does not want to give his real data, or for browsing over Tor). Creating one
                    needs no consent; sharing its data is free, creating accounts or logging in with it
                    still asks (consent ``account``) unless Filip lowers it to ``none`` in Bitwarden.

Agents can never create a ``real`` identity, overwrite an existing one or set consent ``none``.
"""

from __future__ import annotations

import random
import re
import unicodedata
from collections.abc import Iterable
from datetime import date

from . import accounts
from .bw import IDENTITY, Bw, BwError, field_value, set_field

AGENT_CONSENT = ("always", "account")  # ``none`` is Filip's call, made in Bitwarden

_FIRST_M = ["Adam", "Bartosz", "Jakub", "Kamil", "Krzysztof", "Łukasz", "Marcin", "Michał", "Paweł", "Tomasz"]
_FIRST_F = ["Agnieszka", "Anna", "Ewa", "Joanna", "Katarzyna", "Magdalena", "Marta", "Natalia", "Paulina", "Zofia"]
_LAST = [
    ("Nowak", "Nowak"),
    ("Wójcik", "Wójcik"),
    ("Kowalczyk", "Kowalczyk"),
    ("Lewandowski", "Lewandowska"),
    ("Zieliński", "Zielińska"),
    ("Szymański", "Szymańska"),
    ("Woźniak", "Woźniak"),
    ("Dąbrowski", "Dąbrowska"),
    ("Kozłowski", "Kozłowska"),
    ("Mazur", "Mazur"),
]
_CITIES = ["Warszawa", "Kraków", "Wrocław", "Poznań", "Gdańsk", "Łódź", "Lublin", "Katowice", "Szczecin", "Toruń"]

_SHAREABLE_SETTABLE = set(accounts.SHAREABLE)


def _ascii(s: str) -> str:
    s = s.replace("ł", "l").replace("Ł", "L")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def plus_address(base: str, tag: str) -> str:
    """``filip@gmail.com`` + ``shop`` -> ``filip+shop@gmail.com`` (one inbox, a distinct address)."""
    local, sep, domain = base.partition("@")
    if not sep or not local or "." not in domain:
        raise ValueError(f"not an e-mail address: {base!r}")
    tag = re.sub(r"[^a-z0-9]+", "-", _ascii(tag).lower()).strip("-")
    if not tag:
        raise ValueError("the plus tag is empty")
    return f"{local.split('+', 1)[0]}+{tag}@{domain}"


def generate(rng: random.Random | None = None, today: date | None = None) -> dict[str, str]:
    """Plausible, made-up Polish identity data. Not tied to any real person on purpose."""
    rng = rng or random.SystemRandom()
    today = today or accounts._today()
    female = rng.random() < 0.5
    first = rng.choice(_FIRST_F if female else _FIRST_M)
    last = rng.choice(_LAST)[1 if female else 0]
    born = date(today.year - rng.randint(24, 45), rng.randint(1, 12), rng.randint(1, 28))
    username = f"{_ascii(first).lower()}.{_ascii(last).lower()}{rng.randint(10, 99)}"
    return {
        "first_name": first,
        "last_name": last,
        "username": username,
        "city": rng.choice(_CITIES),
        "country": "PL",
        "custom:birth_date": born.isoformat(),
    }


def create(
    bw: Bw,
    *,
    name: str,
    kind: str,
    purpose: str,
    created_by: str,
    email: str = "",
    email_plus: str = "",
    copy_fields: Iterable[str] = (),
    values: dict[str, str] | None = None,
    consent: str = "",
    rng: random.Random | None = None,
) -> dict:
    """Create an identity item. Returns what was stored, as field names plus non-copied values only."""
    if kind not in ("self-variant", "persona"):
        raise ValueError("kind must be self-variant or persona; agents never create a real identity")
    if not purpose.strip():
        raise ValueError("purpose is required: say what this identity is for")
    name = name.strip()
    if not name or name == accounts.REAL_IDENTITY:
        raise ValueError(f"pick a name other than {accounts.REAL_IDENTITY!r}")
    consent = consent or ("always" if kind == "self-variant" else "account")
    if consent not in AGENT_CONSENT:
        raise ValueError(f"consent must be one of {AGENT_CONSENT}; only Filip can set 'none' in Bitwarden")
    folder_id = bw.ensure_folder(accounts.IDENTITY_FOLDER)
    if any(i.get("name") == name for i in bw.list_items(folder_id=folder_id) if i.get("type") == IDENTITY):
        raise BwError(f"An identity named {name!r} already exists in {accounts.IDENTITY_FOLDER!r}.")

    data: dict[str, str] = {}
    copied: list[str] = []
    if kind == "self-variant":
        real = accounts.load_identity(bw, accounts.REAL_IDENTITY)
        picked = real.pick(list(copy_fields) or ["first_name", "last_name", "country"])
        data.update(picked)
        copied = sorted(picked)
    else:
        if copy_fields:
            raise ValueError("a persona copies nothing from the real identity; use kind self-variant")
        data.update(generate(rng))
    for k, v in (values or {}).items():
        key = k.removeprefix("custom:")
        if k in accounts.NEVER_SHARED or key.startswith("hermes_"):
            raise ValueError(f"{k} cannot be set here")
        if not k.startswith("custom:") and k not in _SHAREABLE_SETTABLE:
            raise ValueError(f"unknown identity field {k!r}; known: {sorted(_SHAREABLE_SETTABLE)} or custom:<name>")
        data[k] = v
        if k in copied:
            copied.remove(k)
    if email and email_plus:
        raise ValueError("give --email or --email-plus, not both")
    if email_plus:
        data["email"] = plus_address(email_plus, name)
    elif email:
        data["email"] = email
    if kind == "self-variant" and not data.get("email"):
        raise ValueError("a version of Filip needs its own e-mail (--email or --email-plus)")

    ident = {bwk: data[k] for k, bwk in accounts.SHAREABLE.items() if data.get(k)}
    item = {
        "type": IDENTITY,
        "name": name,
        "folderId": folder_id,
        "favorite": False,
        "reprompt": 0,
        "notes": f"Created by {created_by} on {accounts._today().isoformat()}. Purpose: {purpose}",
        "identity": ident,
        "fields": [],
    }
    for k, v in data.items():
        if k.startswith("custom:"):
            set_field(item, k.removeprefix("custom:"), v)
    for key, value in (
        ("kind", kind),
        ("consent", consent),
        ("created_by", created_by),
        ("created_at", accounts._today().isoformat()),
        ("purpose", purpose),
    ):
        set_field(item, accounts.META[key], value)
    created = bw.create_item(item)
    return {
        "id": created.get("id"),
        "name": name,
        "kind": kind,
        "consent": consent,
        "copied_from_real": copied,  # names only: these values stay in Bitwarden
        "values": {k: v for k, v in data.items() if k not in copied},
    }


def list_identities(bw: Bw) -> list[dict]:
    """Every identity in the folder: name, kind, consent, field names. No values."""
    folder = bw.folders().get(accounts.IDENTITY_FOLDER)
    if not folder:
        return []
    out = []
    for item in bw.list_items(folder_id=folder):
        if item.get("type") != IDENTITY:
            continue
        kind, consent = accounts.classify(item)
        ident = item.get("identity") or {}
        out.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "kind": kind,
                "consent": consent,
                "fields": sorted(k for k, bwk in accounts.SHAREABLE.items() if ident.get(bwk)),
                "purpose": field_value(item, accounts.META["purpose"]),
                "created_by": field_value(item, accounts.META["created_by"]),
            }
        )
    return sorted(out, key=lambda r: (r["kind"] != "real", r["name"] or ""))
