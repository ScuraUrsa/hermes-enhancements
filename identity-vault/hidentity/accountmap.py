"""Account and connection map in Notion.

One Notion database ("Konta i połączenia") holds a row per account. Two self-relations draw the
graph: ``Logs in via`` (this account authenticates through that one, e.g. Claude → Google account)
and ``Connected to`` (integrations/OAuth grants, e.g. Claude Code → Notion). Credentials are never
stored here; a row only carries the Bitwarden item id.

Why Notion and not a dedicated tool: see docs/decision_log.md. Everything is stdlib so it runs on
the VM and on Filip's PC with only the Notion token (``NOTION_API_KEY`` from env or ``bws``).
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

API = "https://api.notion.com/v1"
API_VERSION = "2025-09-03"
DB_TITLE = "Konta i połączenia"

LOGIN_VIA = ["password", "google", "apple", "microsoft", "github", "facebook", "passkey", "magic-link", "other"]
STATUS = ["active", "to-rotate", "to-verify", "closed"]
KINDS = ["real", "self-variant", "persona"]
# Filip 2026-10-30: map what each account knows about which identity, then migrate towards anonymity.
# Identity fields (accounts.SHAREABLE) plus what sites learn without a form field.
DATA_EXTRA = [
    "username",
    "birth_date",
    "payment_card",
    "id_document",
    "photo",
    "voice",
    "location",
    "ip",
    "device",
    "contacts",
]
PLAN = ["keep", "move-to-persona", "reduce-data", "close", "done"]
# A login through one of these hands the provider's identity to the site (see exposure()).
FEDERATED = {"google", "apple", "microsoft", "github", "facebook"}

SCHEMA: dict[str, dict] = {
    "Name": {"title": {}},
    "URL": {"url": {}},
    "Username": {"rich_text": {}},
    "Identity": {"select": {"options": []}},
    "Identity kind": {"select": {"options": [{"name": n} for n in KINDS]}},
    "Login via": {"select": {"options": [{"name": n} for n in LOGIN_VIA]}},
    "Status": {"select": {"options": [{"name": n} for n in STATUS]}},
    "Created by": {"select": {"options": [{"name": n} for n in ("Filip", "Hermes", "Claude")]}},
    "Purpose": {"rich_text": {}},
    "Data shared": {"multi_select": {"options": [{"name": n} for n in DATA_EXTRA]}},
    "Exposes real me": {"checkbox": {}},
    "Anonymity plan": {"select": {"options": [{"name": n} for n in PLAN]}},
    "Migrate to": {"rich_text": {}},
    "Bitwarden item": {"rich_text": {}},
    "Rotate by": {"date": {}},
    "Has 2FA": {"checkbox": {}},
    "Notes": {"rich_text": {}},
}
# Self-relations are added after the database exists (they need the data source id).
RELATIONS = {"Logs in via": "Used to log in to", "Connected to": "Connected from"}


def notion_token() -> str:
    tok = os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN")
    if tok:
        return tok
    try:
        out = subprocess.run(
            ["bws", "secret", "list", "--output", "json"], capture_output=True, text=True, timeout=30, check=True
        ).stdout
        for s in json.loads(out):
            if s.get("key") == "NOTION_API_KEY":
                return s["value"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    raise RuntimeError("No Notion token: set NOTION_API_KEY or store it in Bitwarden Secrets Manager.")


class Notion:
    def __init__(self, token: str | None = None, opener: Callable[..., Any] | None = None):
        self._token = token
        self._open = opener or urllib.request.urlopen

    def _req(self, method: str, path: str, body: dict | None = None) -> dict:
        tok = self._token or notion_token()
        req = urllib.request.Request(
            f"{API}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": f"Bearer {tok}",
                "Notion-Version": API_VERSION,
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with self._open(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"Notion {method} {path}: HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
            ) from e

    # -- database ---------------------------------------------------------------------------

    def find_database(self, title: str = DB_TITLE) -> dict | None:
        res = self._req("POST", "/search", {"query": title, "filter": {"property": "object", "value": "data_source"}})
        for r in res.get("results", []):
            t = "".join(x.get("plain_text", "") for x in r.get("title", []))
            if t == title:
                return r
        return None

    def create_database(self, parent_page_id: str, title: str = DB_TITLE) -> dict:
        db = self._req(
            "POST",
            "/databases",
            {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                "title": [{"type": "text", "text": {"content": title}}],
                "initial_data_source": {"properties": SCHEMA},
            },
        )
        ds_id = db["data_sources"][0]["id"]
        for name, synced in RELATIONS.items():
            self._req(
                "PATCH",
                f"/data_sources/{ds_id}",
                {
                    "properties": {
                        name: {"relation": {"data_source_id": ds_id, "dual_property": {"synced_property_name": synced}}}
                    }
                },
            )
        return self._req("GET", f"/data_sources/{ds_id}")

    def upgrade(self, ds: dict, real_identity: str, legacy: str = "Filip") -> dict:
        """Add the columns this version knows and the database lacks; move rows of the old default
        identity ("Filip") to ``real_identity``. Never removes or renames a column."""
        have = set((ds.get("properties") or {}).keys())
        missing = {k: v for k, v in SCHEMA.items() if k not in have}
        if missing:
            self._req("PATCH", f"/data_sources/{ds['id']}", {"properties": missing})
        moved = 0
        for r in self.rows(ds["id"]):
            if r.get("Identity") in (None, "", legacy):
                props = dict_to_props({"Identity": real_identity, "Identity kind": "real", "Exposes real me": True})
                self._req("PATCH", f"/pages/{r['id']}", {"properties": props})
                moved += 1
        return {"added_columns": sorted(missing), "rows_moved_to_real": moved}

    def ensure_database(self, parent_page_id: str | None) -> dict:
        found = self.find_database()
        if found:
            return found
        if not parent_page_id:
            raise RuntimeError(f"Database {DB_TITLE!r} not found; pass --parent <page id> to create it.")
        return self.create_database(parent_page_id)

    # -- rows -------------------------------------------------------------------------------

    def rows(self, ds_id: str) -> list[dict]:
        out, cursor = [], None
        while True:
            body = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            res = self._req("POST", f"/data_sources/{ds_id}/query", body)
            out += [row_to_dict(p) for p in res.get("results", [])]
            if not res.get("has_more"):
                return out
            cursor = res.get("next_cursor")

    def upsert(self, ds_id: str, row: dict, by: str = "Bitwarden item") -> dict:
        existing = None
        key = row.get(by) or row.get("Name")
        for r in self.rows(ds_id):
            if key and r.get(by if row.get(by) else "Name") == key:
                existing = r
                break
        props = dict_to_props(row)
        if existing:
            return self._req("PATCH", f"/pages/{existing['id']}", {"properties": props})
        return self._req(
            "POST", "/pages", {"parent": {"type": "data_source_id", "data_source_id": ds_id}, "properties": props}
        )

    def link(self, ds_id: str, from_name: str, relation: str, to_name: str) -> None:
        rows = {r["Name"]: r for r in self.rows(ds_id)}
        if from_name not in rows or to_name not in rows:
            raise RuntimeError(f"Both accounts must exist in the map: {from_name!r}, {to_name!r}")
        ids = set(rows[from_name].get(relation) or []) | {rows[to_name]["id"]}
        self._req(
            "PATCH",
            f"/pages/{rows[from_name]['id']}",
            {"properties": {relation: {"relation": [{"id": i} for i in sorted(ids)]}}},
        )


# -- (de)serialisation ------------------------------------------------------------------------


def _text(s: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": s[:2000]}}]}


def dict_to_props(row: dict) -> dict:
    props: dict[str, Any] = {}
    for k, v in row.items():
        if v in (None, "", []):
            continue
        kind = next(iter(SCHEMA.get(k, {"relation": {}}).keys()))
        if kind == "title":
            props[k] = {"title": [{"type": "text", "text": {"content": str(v)}}]}
        elif kind == "url":
            props[k] = {"url": str(v)}
        elif kind == "rich_text":
            props[k] = _text(str(v))
        elif kind == "select":
            props[k] = {"select": {"name": str(v)}}
        elif kind == "multi_select":
            props[k] = {
                "multi_select": [
                    {"name": str(x)} for x in (v if isinstance(v, list) else str(v).split(",")) if str(x).strip()
                ]
            }
        elif kind == "date":
            props[k] = {"date": {"start": str(v)[:10]}}
        elif kind == "checkbox":
            props[k] = {"checkbox": bool(v)}
        elif kind == "relation":
            props[k] = {"relation": [{"id": i} for i in v]}
    return props


def row_to_dict(page: dict) -> dict:
    out: dict[str, Any] = {"id": page.get("id"), "url": page.get("url")}
    for k, p in (page.get("properties") or {}).items():
        t = p.get("type")
        if t == "title":
            out[k] = "".join(x.get("plain_text", "") for x in p.get("title", []))
        elif t == "rich_text":
            out[k] = "".join(x.get("plain_text", "") for x in p.get("rich_text", []))
        elif t in ("url",):
            out[k] = p.get("url")
        elif t == "select":
            out[k] = (p.get("select") or {}).get("name")
        elif t == "multi_select":
            out[k] = [o.get("name") for o in p.get("multi_select", [])]
        elif t == "date":
            out[k] = (p.get("date") or {}).get("start")
        elif t == "checkbox":
            out[k] = p.get("checkbox")
        elif t == "relation":
            out[k] = [r.get("id") for r in p.get("relation", [])]
    return out


def mermaid(rows: list[dict]) -> str:
    """Render the map as a Mermaid graph (for the README / Notion code block)."""
    by_id = {r["id"]: r for r in rows if r.get("id")}
    lines = ["graph LR"]
    for r in rows:
        label = r.get("Name") or r["id"][:6]
        lines.append(f'  {_mid(r["id"])}["{label}"]')
    for r in rows:
        for rel, arrow, text in (("Logs in via", "-->", "logs in via"), ("Connected to", "-.->", "connected")):
            for tid in r.get(rel) or []:
                if tid in by_id:
                    lines.append(f"  {_mid(r['id'])} {arrow}|{text}| {_mid(tid)}")
    return "\n".join(lines)


def _mid(page_id: str) -> str:
    return "n" + page_id.replace("-", "")[:8]


def exposure(rows: list[dict], real_identity: str) -> dict:
    """What the accounts know about each identity, and where identities leak into each other.

    ``links`` lists what ties a non-real identity back to another one: a shared username or a login
    through an account of a different identity (a Google login gives the site that Google account).
    Rows marked ``Exposes real me`` (or under the real identity) are the migration backlog.
    """
    by_id = {r["id"]: r for r in rows if r.get("id")}
    ident: dict[str, dict] = {}
    for r in rows:
        if r.get("Status") == "closed":
            continue
        name = r.get("Identity") or real_identity
        e = ident.setdefault(name, {"kind": r.get("Identity kind"), "accounts": [], "data": set()})
        e["kind"] = e["kind"] or r.get("Identity kind")
        e["accounts"].append(r.get("Name"))
        e["data"].update(r.get("Data shared") or [])
    links = []
    users: dict[str, set[str]] = {}
    for r in rows:
        if r.get("Status") == "closed":
            continue
        name = r.get("Identity") or real_identity
        if r.get("Username"):
            users.setdefault(r["Username"].strip().lower(), set()).add(name)
        if r.get("Login via") in FEDERATED and not r.get("Logs in via"):
            links.append(
                {
                    "account": r.get("Name"),
                    "identity": name,
                    "via": r.get("Login via"),
                    "leaks_to": "unknown",
                    "how": "federated login, provider account not linked in the map",
                }
            )
        for tid in r.get("Logs in via") or []:
            t = by_id.get(tid)
            if t and (t.get("Identity") or real_identity) != name:
                links.append(
                    {
                        "account": r.get("Name"),
                        "identity": name,
                        "via": t.get("Name"),
                        "leaks_to": t.get("Identity") or real_identity,
                        "how": "logs in via",
                    }
                )
    for u, names in sorted(users.items()):
        if len(names) > 1:
            links.append({"username": u, "identities": sorted(names), "how": "same username"})
    backlog = [
        {
            "account": r.get("Name"),
            "identity": r.get("Identity") or real_identity,
            "data": r.get("Data shared") or [],
            "plan": r.get("Anonymity plan"),
            "migrate_to": r.get("Migrate to"),
        }
        for r in rows
        if r.get("Status") != "closed"
        and r.get("Anonymity plan") != "done"
        and (r.get("Exposes real me") or (r.get("Identity") or real_identity) == real_identity)
    ]
    return {
        "identities": {
            k: {**v, "data": sorted(v["data"]), "accounts": sorted(filter(None, v["accounts"]))}
            for k, v in sorted(ident.items())
        },
        "links": links,
        "real_data_backlog": backlog,
    }
