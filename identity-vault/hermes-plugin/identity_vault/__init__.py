"""Hermes plugin ``identity_vault``: consent-gated account creation and logins as Filip.

What it adds to Hermes (which already fills Bitwarden passwords model-blind through
``browser_vault_fill``):

Tools
  identity_coverage()                      what the vault knows about Filip (field names only)
  identity_list()                          identities in the vault: name, kind, consent (no values)
  identity_create_persona(...)             a generated persona (no consent) or a formal/private
                                           version of Filip (ASKS FILIP, copies his data model-blind)
  identity_share(site, purpose, fields)    returns identity values for a form; ASKS FILIP for
                                           "Prawdziwy Ja" and his versions, not for personas
  identity_create_account(...)             ASKS FILIP (unless the identity's consent is "none", which
                                           only Filip sets), then Bitwarden generates + stores the password,
                                           adds the account to the Notion map, tells Filip to rotate
  identity_request_login(handle, site, purpose)
                                           ASKS FILIP ("Hermes wants to log in to X because Y"), then
                                           grants ``browser_vault_fill`` for that handle for a few minutes

Gate (``pre_tool_call``)
  * ``browser_vault_fill`` is blocked unless ``identity_request_login`` was approved for that handle
    (or the item is on the no-ask allowlist in config).
  * terminal commands that would reach secrets or bypass consent (``bw get password|totp|item``,
    ``bw list items``, ``hidentity create|share``) are blocked with a pointer to the tools above.

Consent uses ``tools.approval_prompt.request_elicitation_consent``: a per-call question in the surface
Filip is using (chat buttons or the CLI panel). It is NOT subject to YOLO / ``approvals.mode: off``
and it fails closed in cron, ``-q`` and other headless runs, so an unattended Hermes can never create
an account or log in as Filip.

Config (``config.yaml``)::

    plugins:
      entries:
        identity_vault:
          hidentity_path: /home/ubuntu/.hermes/scripts/identity-vault   # where the hidentity package lives
          grant_minutes: 10
          no_ask_handles: []        # vault handles Filip allowed permanently (e.g. "bw:<id>")
          created_by: Hermes
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

_cfg: dict[str, Any] = {}
_grants: dict[str, float] = {}  # vault handle -> expiry (epoch seconds)

_BLOCKED_TERMINAL = re.compile(
    r"(^|[;&|]\s*)(?:\S*/)?(?:bw\s+(?:get\s+(?:password|totp|item|username|notes)|list\s+items|export)"
    r"|hidentity\s+(?:create|share|persona)|bws\s+secret\s+get)\b"
)


# -- consent -----------------------------------------------------------------------------------


def _ask(title: str, message: str, description: str) -> bool:
    try:
        from tools.approval_prompt import request_elicitation_consent
    except Exception:  # pragma: no cover - only outside Hermes
        logger.error("identity_vault: Hermes consent prompt unavailable; refusing")
        return False
    return request_elicitation_consent(message, description, surface="identity-vault", title=title) == "accept"


def _refused(what: str) -> str:
    return json.dumps(
        {
            "success": False,
            "error_type": "consent_refused",
            "error": f"Filip did not approve {what}. Do not retry; tell him what you wanted to do and why.",
        }
    )


# -- hidentity access ------------------------------------------------------------------------


def _hidentity():
    path = _cfg.get("hidentity_path") or os.environ.get("HIDENTITY_PATH")
    if path and path not in sys.path:
        sys.path.insert(0, path)
    from hidentity import accountmap, accounts  # noqa: WPS433
    from hidentity.bw import Bw

    return accounts, accountmap, Bw


def _whose(ident) -> str:
    if ident.is_real:
        return f"Twoje PRAWDZIWE dane (tożsamość „{ident.name}”)"
    if ident.kind == "self-variant":
        return f"Twoje dane z wersji „{ident.name}”"
    return f"dane persony „{ident.name}”"


def _bw_session() -> str | None:
    """Reuse the session token Hermes' own Bitwarden backend minted after Filip unlocked it."""
    try:
        from agent.vault_backends import unlock as _unlock

        return _unlock.get_session_token("bitwarden")
    except Exception:
        return os.environ.get("BW_SESSION")


def _bw():
    accounts, accountmap, Bw = _hidentity()
    session = _bw_session()
    if not session:
        raise RuntimeError(
            "Bitwarden is locked. Call browser_vault_unlock('bitwarden') first (Filip types the master password)."
        )
    return Bw(session=session), accounts, accountmap


# -- tools -------------------------------------------------------------------------------------


def identity_coverage(identity: str = "") -> str:
    try:
        bw, accounts, _ = _bw()
        ident = accounts.load_identity(bw, identity or None)
        return json.dumps({"success": True, "identity": ident.name, **ident.coverage()})
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def identity_share(site: str, purpose: str, fields: list[str], identity: str = "") -> str:
    if not purpose.strip() or not site.strip():
        return json.dumps({"success": False, "error": "site and purpose are required"})
    try:
        bw, accounts, _ = _bw()
        ident = accounts.load_identity(bw, identity or None)
        values = ident.pick(fields)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
    if accounts.needs_consent(ident, "share"):
        ok = _ask(
            "Udostępnić dane osobowe?",
            f"Hermes chce wpisać na {site} {_whose(ident)}: {', '.join(sorted(values))}.",
            f"Po co: {purpose}\nŹródło: Bitwarden → „{ident.name}”. Wartości nie trafią do logów.",
        )
        if not ok:
            return _refused(f"sharing {', '.join(sorted(values))} with {site}")
    return json.dumps(
        {
            "success": True,
            "site": site,
            "values": values,
            "note": "Type these into the form yourself; never paste them elsewhere.",
        }
    )


def identity_create_account(
    site_url: str,
    username: str,
    purpose: str,
    name: str = "",
    shared_fields: list[str] | None = None,
    login_via: str = "password",
    identity: str = "",
) -> str:
    shared_fields = shared_fields or []
    try:
        bw, accounts, accountmap = _bw()
        origin = accounts.origin_of(site_url)
        ident = accounts.load_identity(bw, identity or None)
        identity = ident.name
        existing = accounts.find_existing(bw, origin, username)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
    if existing:
        return json.dumps(
            {
                "success": False,
                "error_type": "exists",
                "error": f"Filip already has a login for {origin} as {username}; use identity_request_login.",
                "items": [{"handle": f"bw:{e['id']}", "name": e["name"]} for e in existing],
            }
        )
    if accounts.needs_consent(ident, "account"):
        ok = _ask(
            "Założyć nowe konto?",
            f"Hermes chce założyć konto na {origin} (login: {username}) jako „{ident.name}”.",
            f"Po co: {purpose}\nWpisze {_whose(ident)}: {', '.join(shared_fields) or 'tylko login'}.\n"
            f"Hasło wygeneruje Bitwarden i zapisze w folderze „{accounts.ACCOUNTS_FOLDER}”; "
            "poproszę Cię o jego zmianę.",
        )
        if not ok:
            return _refused(f"creating an account on {origin}")
    try:
        meta = accounts.create_login(
            bw,
            name=name or origin.split("//", 1)[1],
            url=origin,
            username=username,
            purpose=purpose,
            created_by=str(_cfg.get("created_by") or "Hermes"),
            identity=identity,
            shared=shared_fields,
            login_via=login_via,
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
    handle = f"bw:{meta['id']}"
    _grants[handle] = time.time() + 60 * float(_cfg.get("grant_minutes") or 10)
    map_url = None
    try:
        from hidentity.cli import _kinds, _map_row_from_meta

        n = accountmap.Notion()
        ds = n.ensure_database(None)
        map_url = n.upsert(ds["id"], _map_row_from_meta(meta, _kinds(bw))).get("url")
    except Exception as exc:
        map_url = f"not added: {exc}"
    rotate_by = meta["fields"].get(accounts.META["rotate_by"])
    return json.dumps(
        {
            "success": True,
            "handle": handle,
            "item": meta,
            "map": map_url,
            "next": (
                f"Fill the sign-up form: type the username yourself, then call browser_vault_fill('{handle}') "
                f"for the password field (the grant lasts {_cfg.get('grant_minutes') or 10} min). "
                f"Afterwards tell Filip, in Polish, to change this password in Bitwarden by {rotate_by}."
            ),
        }
    )


def identity_list() -> str:
    try:
        bw, _, _ = _bw()
        from hidentity import personas

        return json.dumps({"success": True, "identities": personas.list_identities(bw)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})


def identity_create_persona(
    name: str,
    kind: str,
    purpose: str,
    email: str = "",
    email_plus: str = "",
    copy_fields: list[str] | None = None,
    values: dict | None = None,
) -> str:
    try:
        bw, accounts, _ = _bw()
        from hidentity import personas
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
    if kind == "self-variant":
        fields = copy_fields or ["first_name", "last_name", "country"]
        ok = _ask(
            "Utworzyć nową wersję Ciebie?",
            f"Hermes chce utworzyć tożsamość „{name}” z Twoimi prawdziwymi danymi: {', '.join(fields)}.",
            f"Po co: {purpose}\nE-mail: {email or email_plus or '(brak)'}. "
            "Dane skopiuje Bitwarden, model ich nie zobaczy.",
        )
        if not ok:
            return _refused(f"creating the identity {name!r} from your real data")
    try:
        res = personas.create(
            bw,
            name=name,
            kind=kind,
            purpose=purpose,
            created_by=str(_cfg.get("created_by") or "Hermes"),
            email=email,
            email_plus=email_plus,
            copy_fields=copy_fields or [],
            values={str(k): str(v) for k, v in (values or {}).items()},
        )
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc)})
    return json.dumps({"success": True, "identity": res}, ensure_ascii=False)


def identity_request_login(handle: str, site: str, purpose: str) -> str:
    if not handle.startswith(("bw:", "op:", "local:")) and ":" not in handle:
        return json.dumps({"success": False, "error": "handle must be a vault handle from browser_vault_list"})
    if not purpose.strip():
        return json.dumps({"success": False, "error": "purpose is required: say why you log in"})
    if handle in (_cfg.get("no_ask_handles") or []):
        _grants[handle] = time.time() + 60 * float(_cfg.get("grant_minutes") or 10)
        return json.dumps({"success": True, "handle": handle, "note": "allowed permanently by Filip"})
    ok = _ask(
        "Zalogować się jako Ty?",
        f"Hermes chce zalogować się na {site}.",
        f"Po co: {purpose}\nHasło wypełni Bitwarden bez pokazywania go modelowi.",
    )
    if not ok:
        return _refused(f"logging in to {site}")
    _grants[handle] = time.time() + 60 * float(_cfg.get("grant_minutes") or 10)
    return json.dumps(
        {
            "success": True,
            "handle": handle,
            "next": f"Navigate to the login page, type the username, then browser_vault_fill('{handle}').",
        }
    )


# -- gate --------------------------------------------------------------------------------------


def _grant_ok(handle: str) -> bool:
    if handle in (_cfg.get("no_ask_handles") or []):
        return True
    exp = _grants.get(handle)
    if exp and exp > time.time():
        return True
    _grants.pop(handle, None)
    return False


def _on_pre_tool_call(tool_name: str = "", args: dict | None = None, **kwargs) -> dict | None:
    args = args or {}
    if tool_name == "browser_vault_fill":
        handle = str(args.get("handle") or "")
        if not _grant_ok(handle):
            return {
                "action": "block",
                "message": (
                    "BLOCKED by identity_vault: Filip must approve each login. Call "
                    f"identity_request_login(handle={handle!r}, site=<where>, purpose=<why>) first."
                ),
            }
        return None
    if tool_name == "terminal":
        cmd = str(args.get("command") or "")
        if _BLOCKED_TERMINAL.search(cmd):
            return {
                "action": "block",
                "message": (
                    "BLOCKED by identity_vault: secrets never pass through the terminal. Use "
                    "identity_create_account / identity_share / identity_request_login + browser_vault_fill."
                ),
            }
    return None


def _on_post_tool_call(tool_name: str = "", args: dict | None = None, **kwargs) -> None:
    # A grant is for one fill: consume it as soon as the fill ran.
    if tool_name == "browser_vault_fill":
        _grants.pop(str((args or {}).get("handle") or ""), None)


# -- registration ------------------------------------------------------------------------------


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }


def register(ctx) -> None:
    global _cfg
    try:
        _cfg = dict(ctx.get_config() or {})
    except Exception:
        _cfg = {}
    ctx.register_hook("pre_tool_call", _on_pre_tool_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ts = "identity_vault"
    ctx.register_tool(
        "identity_coverage",
        ts,
        _tool(
            "identity_coverage",
            "Which personal-data fields Filip's Bitwarden identity holds (names only, no values). "
            "Use before a sign-up to know what you can offer to fill.",
            {"identity": {"type": "string", "description": "Identity item name (default: first)"}},
            [],
        ),
        handler=lambda args, **kw: identity_coverage(**args),
    )
    ctx.register_tool(
        "identity_list",
        ts,
        _tool(
            "identity_list",
            "Identities in Filip's vault folder: 'Prawdziwy Ja' (his real data, always asks), his formal/private "
            "versions and generated personas, with how much consent each needs. No values.",
            {},
            [],
        ),
        handler=lambda args, **kw: identity_list(),
    )
    ctx.register_tool(
        "identity_create_persona",
        ts,
        _tool(
            "identity_create_persona",
            "Create a new identity in Bitwarden. kind=persona: generated, made-up data (for sign-ups where Filip "
            "does not want to give his real data, or browsing over Tor); no consent needed, but accounts and logins "
            "with it still ask. kind=self-variant: a formal or private version of Filip with its own e-mail; ASKS "
            "FILIP, copies chosen fields from his real identity without showing them to you.",
            {
                "name": {"type": "string", "description": "Item name, e.g. 'Filip formalny' or 'Tor 1'"},
                "kind": {"type": "string", "enum": ["persona", "self-variant"]},
                "purpose": {"type": "string"},
                "email": {"type": "string"},
                "email_plus": {"type": "string", "description": "Inbox to derive base+<name>@domain from"},
                "copy_fields": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "object", "description": "Fields to set or override, e.g. {city: Gdańsk}"},
            },
            ["name", "kind", "purpose"],
        ),
        handler=lambda args, **kw: identity_create_persona(**args),
    )
    ctx.register_tool(
        "identity_share",
        ts,
        _tool(
            "identity_share",
            "Returns identity values (name, email, phone, address...) to type into a form on `site`. ASKS FILIP "
            "for his real identity and his versions; a persona's data is free. Always give the real reason.",
            {
                "site": {"type": "string"},
                "purpose": {"type": "string"},
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g. first_name,last_name,email,phone,city,postal_code,country,custom:birth_date",
                },
                "identity": {"type": "string"},
            },
            ["site", "purpose", "fields"],
        ),
        handler=lambda args, **kw: identity_share(**args),
    )
    ctx.register_tool(
        "identity_create_account",
        ts,
        _tool(
            "identity_create_account",
            "ASKS FILIP, then creates a Bitwarden login with a generated password for a new "
            "account on `site_url`, records why, adds it to the Notion account map and schedules a rotation reminder. "
            "Returns the vault handle to use with browser_vault_fill on the sign-up form. "
            "Never type a password yourself.",
            {
                "site_url": {"type": "string"},
                "username": {"type": "string", "description": "Email or username for the account"},
                "purpose": {"type": "string"},
                "name": {"type": "string"},
                "shared_fields": {"type": "array", "items": {"type": "string"}},
                "login_via": {
                    "type": "string",
                    "enum": [
                        "password",
                        "google",
                        "apple",
                        "microsoft",
                        "github",
                        "facebook",
                        "passkey",
                        "magic-link",
                        "other",
                    ],
                },
                "identity": {"type": "string"},
            },
            ["site_url", "username", "purpose"],
        ),
        handler=lambda args, **kw: identity_create_account(**args),
    )
    ctx.register_tool(
        "identity_request_login",
        ts,
        _tool(
            "identity_request_login",
            "ASKS FILIP for permission to log in as him with a saved vault handle (from "
            "browser_vault_list). Say where (`site`) and why (`purpose`). "
            "On approval browser_vault_fill works for that handle "
            "for a few minutes.",
            {"handle": {"type": "string"}, "site": {"type": "string"}, "purpose": {"type": "string"}},
            ["handle", "site", "purpose"],
        ),
        handler=lambda args, **kw: identity_request_login(**args),
    )
