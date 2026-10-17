"""Thin, secret-safe wrapper around the Bitwarden Password Manager CLI (``bw``).

Rules this module keeps so a password never reaches a model, a log or argv:

- Secrets travel only through stdin (``bw create/edit item`` read the encoded JSON from stdin)
  and the child's environment (``BW_SESSION``). Nothing secret is ever put in argv.
- ``generate_password`` returns the value to Python only; callers store it with ``create_login``
  and never print it.
- ``item_metadata`` strips passwords, TOTP seeds, hidden custom fields and card/identity numbers
  before anything leaves this module.

``bw`` needs a session token (``BW_SESSION``) for every vault command. On a Hermes VM the token
comes from Hermes' own vault unlock (``browser_vault_unlock``, Filip types the master password in a
masked prompt); on Filip's PC from ``bw unlock`` in his terminal.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Bitwarden item types.
LOGIN, SECURE_NOTE, CARD, IDENTITY = 1, 2, 3, 4
# Custom field types.
FIELD_TEXT, FIELD_HIDDEN, FIELD_BOOLEAN = 0, 1, 2

_ENV_KEEP = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "SystemRoot",
    "TMPDIR",
    "TMP",
    "TEMP",
    "XDG_CONFIG_HOME",
    "BITWARDENCLI_APPDATA_DIR",
)

Runner = Callable[..., subprocess.CompletedProcess]


class BwError(RuntimeError):
    """``bw`` failed. The message never contains secret values."""


class BwLocked(BwError):
    """The vault is locked or no session token is available."""


@dataclass
class Bw:
    """Run ``bw`` with a session token. ``runner`` is injectable for offline tests."""

    session: str | None = None
    binary: str | None = None
    runner: Runner = subprocess.run
    timeout: float = 60.0

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = os.environ.get("BW_SESSION") or None

    # -- plumbing -----------------------------------------------------------------------------

    def _bin(self) -> str:
        found = self.binary or shutil.which("bw")
        if not found:
            raise BwError("Bitwarden CLI (bw) not found. Install it (see identity-vault/README.md).")
        return found

    def _env(self) -> dict[str, str]:
        env = {k: os.environ[k] for k in _ENV_KEEP if k in os.environ}
        env["NO_COLOR"] = "1"
        if self.session:
            env["BW_SESSION"] = self.session
        return env

    def run(self, *args: str, stdin: str | None = None, needs_session: bool = True) -> str:
        if needs_session and not self.session:
            raise BwLocked(
                "Bitwarden is locked: no BW_SESSION. Unlock first (Hermes: browser_vault_unlock; "
                "PC: `bw unlock` and export BW_SESSION)."
            )
        proc = self.runner(
            [self._bin(), *args, "--nointeraction"],
            input=stdin,
            capture_output=True,
            text=True,
            env=self._env(),
            timeout=self.timeout,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:300]
            low = err.lower()
            if "locked" in low or "not logged in" in low or "session" in low:
                raise BwLocked(f"Bitwarden is locked or not logged in ({err})")
            raise BwError(f"bw {args[0]} failed: {err}")
        return proc.stdout or ""

    def run_json(self, *args: str, stdin: str | None = None) -> Any:
        out = self.run(*args, stdin=stdin)
        try:
            return json.loads(out or "null")
        except json.JSONDecodeError as exc:
            raise BwError(f"bw {args[0]} returned non-JSON output") from exc

    @staticmethod
    def encode(obj: Any) -> str:
        """Same as ``bw encode``: base64 of the JSON text."""
        return base64.b64encode(json.dumps(obj).encode("utf-8")).decode("ascii")

    # -- vault operations ---------------------------------------------------------------------

    def status(self) -> dict:
        out = self.run("status", needs_session=False)
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return {"status": "unknown"}
        # Keep only non-identifying fields plus the account email (Filip's own, not a secret).
        return {k: data.get(k) for k in ("status", "userEmail", "lastSync", "serverUrl")}

    def sync(self) -> None:
        self.run("sync")

    def generate_password(self, length: int = 24, passphrase: bool = False) -> str:
        """Generate a password with Bitwarden's generator. The value stays in Python."""
        if passphrase:
            args = ["generate", "--passphrase", "--words", "5", "--separator", "-", "--capitalize", "--includeNumber"]
        else:
            args = ["generate", "-ulns", "--length", str(max(14, min(length, 128)))]
        value = self.run(*args, needs_session=False).strip()
        if len(value) < 14:
            raise BwError("bw generate returned an unexpectedly short value")
        return value

    def folders(self) -> dict[str, str]:
        """Folder name -> id."""
        return {f["name"]: f["id"] for f in self.run_json("list", "folders") or [] if f.get("id")}

    def ensure_folder(self, name: str) -> str:
        existing = self.folders()
        if name in existing:
            return existing[name]
        created = self.run_json("create", "folder", stdin=self.encode({"name": name}))
        return created["id"]

    def list_items(self, folder_id: str | None = None, search: str | None = None) -> list[dict]:
        args = ["list", "items"]
        if folder_id:
            args += ["--folderid", folder_id]
        if search:
            args += ["--search", search]
        return self.run_json(*args) or []

    def get_item(self, item_id: str) -> dict:
        return self.run_json("get", "item", item_id)

    def create_item(self, item: dict) -> dict:
        return self.run_json("create", "item", stdin=self.encode(item))

    def edit_item(self, item_id: str, item: dict) -> dict:
        return self.run_json("edit", "item", item_id, stdin=self.encode(item))


# -- metadata helpers (never return secrets) ---------------------------------------------------


def field_value(item: dict, name: str) -> str | None:
    for f in item.get("fields") or []:
        if f.get("name") == name and f.get("type") != FIELD_HIDDEN:
            return f.get("value")
    return None


def set_field(item: dict, name: str, value: str, ftype: int = FIELD_TEXT) -> None:
    fields = item.setdefault("fields", []) or []
    item["fields"] = fields
    for f in fields:
        if f.get("name") == name:
            f["value"], f["type"] = value, ftype
            return
    fields.append({"name": name, "value": value, "type": ftype})


def item_metadata(item: dict) -> dict:
    """Model-safe view of a vault item: no passwords, TOTP seeds, hidden fields, card numbers."""
    login = item.get("login") or {}
    out = {
        "id": item.get("id"),
        "name": item.get("name"),
        "type": {LOGIN: "login", SECURE_NOTE: "note", CARD: "card", IDENTITY: "identity"}.get(
            item.get("type"), "other"
        ),
        "folderId": item.get("folderId"),
        "revisionDate": item.get("revisionDate"),
        "creationDate": item.get("creationDate"),
        "fields": {
            f.get("name"): f.get("value")
            for f in item.get("fields") or []
            if f.get("type") in (FIELD_TEXT, FIELD_BOOLEAN) and f.get("name")
        },
    }
    if item.get("type") == LOGIN:
        out["username"] = login.get("username")
        out["uris"] = [u.get("uri") for u in login.get("uris") or [] if u.get("uri")]
        out["has_totp"] = bool(login.get("totp"))
        out["passwordRevisionDate"] = login.get("passwordRevisionDate")
    return out
