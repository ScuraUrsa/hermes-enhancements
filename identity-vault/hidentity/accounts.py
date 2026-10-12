"""Identity profile, account creation and password-rotation bookkeeping on top of Bitwarden.

Vault layout (folder names are configurable through env, defaults below):

- ``Identity``  Bitwarden *Identity* items with Filip's personal data. The first one (or the one
                named with ``--identity``) is what agents may share on sign-up forms, field by field,
                after Filip agrees.
- ``Accounts``  one *Login* item per account an agent created. Text custom fields prefixed
                ``hermes_`` record who created it, why, what personal data was shared and when the
                password must be rotated.

Nothing here returns a password, a TOTP seed or a hidden field.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from .bw import FIELD_HIDDEN, IDENTITY, LOGIN, Bw, BwError, field_value, item_metadata, set_field

IDENTITY_FOLDER = os.environ.get("HIDENTITY_IDENTITY_FOLDER", "Identity")
ACCOUNTS_FOLDER = os.environ.get("HIDENTITY_ACCOUNTS_FOLDER", "Accounts")
DEFAULT_ROTATE_DAYS = int(os.environ.get("HIDENTITY_ROTATE_DAYS", "3"))

# Bitwarden identity fields an agent may put on a sign-up form (after consent).
SHAREABLE = {
    "title": "title",
    "first_name": "firstName",
    "middle_name": "middleName",
    "last_name": "lastName",
    "email": "email",
    "phone": "phone",
    "username": "username",
    "company": "company",
    "address1": "address1",
    "address2": "address2",
    "address3": "address3",
    "city": "city",
    "state": "state",
    "postal_code": "postalCode",
    "country": "country",
}
# Stored in the identity item but never handed to an agent by this tool.
NEVER_SHARED = {"ssn": "ssn", "passport_number": "passportNumber", "license_number": "licenseNumber"}

META = {
    "created_by": "hermes_created_by",
    "created_at": "hermes_created_at",
    "purpose": "hermes_purpose",
    "identity": "hermes_identity",
    "shared": "hermes_shared",
    "login_via": "hermes_login_via",
    "rotate_by": "hermes_rotate_by",
    "rotated": "hermes_rotated",
}


def _today() -> date:
    return datetime.now(timezone.utc).date()


def origin_of(url: str) -> str:
    p = urlparse(url if "://" in url else f"https://{url}")
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError(f"not a web URL: {url!r}")
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    return f"{p.scheme}://{p.hostname.lower()}{port}"


# -- identity --------------------------------------------------------------------------------


@dataclass
class Identity:
    item_id: str
    name: str
    values: dict[str, str]  # shareable key -> value (only non-empty)
    custom: dict[str, str]  # visible custom fields on the identity item (e.g. birth_date)
    stored_private: list[str]  # NEVER_SHARED keys that are filled (names only)

    def coverage(self) -> dict[str, list[str]]:
        """What the vault knows about Filip and what not (field names only)."""
        known = sorted(set(self.values) | {f"custom:{k}" for k in self.custom})
        missing = sorted(k for k in SHAREABLE if k not in self.values)
        return {"known": known, "missing": missing, "stored_never_shared": sorted(self.stored_private)}

    def pick(self, fields: Iterable[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for f in fields:
            if f in NEVER_SHARED:
                raise ValueError(f"{f} is never shared by this tool; Filip types it himself")
            key = f.removeprefix("custom:")
            if f.startswith("custom:") or key in self.custom and key not in SHAREABLE:
                if key in self.custom:
                    out[f"custom:{key}"] = self.custom[key]
            elif f in self.values:
                out[f] = self.values[f]
            elif f not in SHAREABLE:
                raise ValueError(f"unknown identity field {f!r}; known: {sorted(SHAREABLE)} or custom:<name>")
        return out


def load_identity(bw: Bw, name: str | None = None) -> Identity:
    folder = bw.folders().get(IDENTITY_FOLDER)
    if not folder:
        raise BwError(f"No Bitwarden folder {IDENTITY_FOLDER!r}. Create it and put an Identity item in it.")
    items = [i for i in bw.list_items(folder_id=folder) if i.get("type") == IDENTITY]
    if name:
        items = [i for i in items if i.get("name") == name]
    if not items:
        raise BwError(f"No Identity item{' named ' + repr(name) if name else ''} in folder {IDENTITY_FOLDER!r}.")
    item = min(items, key=lambda i: i.get("name") or "")
    ident = item.get("identity") or {}
    values = {k: str(ident[bwk]).strip() for k, bwk in SHAREABLE.items() if ident.get(bwk)}
    custom = {
        f["name"]: str(f.get("value") or "")
        for f in item.get("fields") or []
        if f.get("name") and f.get("type") != FIELD_HIDDEN and f.get("value")
    }
    private = [k for k, bwk in NEVER_SHARED.items() if ident.get(bwk)]
    return Identity(
        item_id=item["id"], name=item.get("name") or "", values=values, custom=custom, stored_private=private
    )


# -- accounts --------------------------------------------------------------------------------


def find_existing(bw: Bw, url: str, username: str | None) -> list[dict]:
    origin = origin_of(url)
    host = urlparse(origin).hostname or ""
    out = []
    for item in bw.list_items(search=host):
        if item.get("type") != LOGIN:
            continue
        uris = [u.get("uri") or "" for u in (item.get("login") or {}).get("uris") or []]
        same_site = any(_safe_origin(u) == origin for u in uris)
        same_user = not username or (item.get("login") or {}).get("username") == username
        if same_site and same_user:
            out.append(item_metadata(item))
    return out


def _safe_origin(u: str) -> str | None:
    try:
        return origin_of(u)
    except ValueError:
        return None


def create_login(
    bw: Bw,
    *,
    name: str,
    url: str,
    username: str,
    purpose: str,
    created_by: str,
    identity: str = "",
    shared: Iterable[str] = (),
    login_via: str = "password",
    rotate_days: int = DEFAULT_ROTATE_DAYS,
    passphrase: bool = False,
    extra_urls: Iterable[str] = (),
) -> dict:
    """Generate a password with Bitwarden and store a new login item. Returns metadata only."""
    if not purpose.strip():
        raise ValueError("purpose is required: say why this account is created")
    origin = origin_of(url)
    if find_existing(bw, url, username):
        raise BwError(f"A login for {origin} and {username!r} already exists in Bitwarden; log in instead.")
    folder_id = bw.ensure_folder(ACCOUNTS_FOLDER)
    password = bw.generate_password(passphrase=passphrase)
    today = _today()
    item = {
        "type": LOGIN,
        "name": name,
        "folderId": folder_id,
        "favorite": False,
        "reprompt": 0,
        "notes": f"Created by {created_by} on {today.isoformat()}. Purpose: {purpose}",
        "login": {
            "username": username,
            "password": password,
            "totp": None,
            "uris": [{"match": None, "uri": origin}] + [{"match": None, "uri": origin_of(u)} for u in extra_urls],
        },
        "fields": [],
    }
    for key, value in (
        ("created_by", created_by),
        ("created_at", today.isoformat()),
        ("purpose", purpose),
        ("identity", identity),
        ("shared", ",".join(shared)),
        ("login_via", login_via),
        ("rotate_by", (today + timedelta(days=rotate_days)).isoformat()),
        ("rotated", "no"),
    ):
        set_field(item, META[key], value)
    created = bw.create_item(item)
    del password, item
    return item_metadata(created)


def accounts(bw: Bw) -> list[dict]:
    """Every login in the Accounts folder, metadata only."""
    folder = bw.folders().get(ACCOUNTS_FOLDER)
    if not folder:
        return []
    return [item_metadata(i) for i in bw.list_items(folder_id=folder) if i.get("type") == LOGIN]


def _rotated(meta: dict) -> bool:
    f = meta.get("fields") or {}
    if f.get(META["rotated"]) == "yes":
        return True
    created, changed = f.get(META["created_at"]), meta.get("passwordRevisionDate")
    # Bitwarden sets passwordRevisionDate when the password of an item changes after creation.
    return bool(created and changed and changed[:10] >= created)


def rotation_due(bw: Bw, today: date | None = None) -> list[dict]:
    today = today or _today()
    due = []
    for meta in accounts(bw):
        f = meta.get("fields") or {}
        rotate_by = f.get(META["rotate_by"])
        if not rotate_by or _rotated(meta):
            continue
        if date.fromisoformat(rotate_by[:10]) <= today:
            due.append(
                {
                    "id": meta["id"],
                    "name": meta["name"],
                    "uris": meta.get("uris"),
                    "username": meta.get("username"),
                    "rotate_by": rotate_by,
                }
            )
    return due


def mark_rotated(bw: Bw, item_id: str) -> dict:
    item = bw.get_item(item_id)
    if field_value(item, META["created_by"]) is None:
        raise BwError("This item was not created by hidentity; nothing to mark.")
    set_field(item, META["rotated"], "yes")
    return item_metadata(bw.edit_item(item_id, item))
