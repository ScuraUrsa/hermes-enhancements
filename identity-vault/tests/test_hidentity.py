"""Offline tests: a fake ``bw`` runner and a fake Notion opener. No network, no real vault."""

from __future__ import annotations

import base64
import io
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hermes-plugin"))

from hidentity import accountmap, accounts, cli
from hidentity.bw import Bw, BwError, BwLocked, item_metadata

# -- fake bw -----------------------------------------------------------------------------------


class FakeBw:
    """Enough of ``bw`` to exercise the code paths. Secrets stay inside this object."""

    def __init__(self):
        self.folders = [{"id": "f-id", "name": "Identity"}]
        self.items = [
            {
                "id": "i-1",
                "type": 4,
                "name": "Filip",
                "folderId": "f-id",
                "identity": {
                    "firstName": "Filip",
                    "lastName": "K.",
                    "email": "f@example.com",
                    "phone": "+48 600 000 000",
                    "city": "Kraków",
                    "country": "PL",
                    "passportNumber": "SECRET-PASSPORT",
                },
                "fields": [
                    {"name": "birth_date", "value": "1990-01-01", "type": 0},
                    {"name": "pesel", "value": "SECRET-PESEL", "type": 1},
                ],
            }
        ]
        self.calls: list[list[str]] = []

    def __call__(self, argv, input=None, capture_output=True, text=True, env=None, timeout=None):
        assert all("SECRET" not in a and "pw-" not in a for a in argv), "secret in argv"
        assert env.get("BW_SESSION") == "sess" or argv[1] in ("generate", "status")
        self.calls.append(argv[1:])
        cmd = argv[1:]
        out = ""
        if cmd[0] == "status":
            out = json.dumps({"status": "unlocked", "userEmail": "f@example.com"})
        elif cmd[0] == "generate":
            out = "pw-" + "x" * 30
        elif cmd[:2] == ["list", "folders"]:
            out = json.dumps(self.folders)
        elif cmd[:2] == ["list", "items"]:
            items = self.items
            if "--folderid" in cmd:
                fid = cmd[cmd.index("--folderid") + 1]
                items = [i for i in items if i.get("folderId") == fid]
            if "--search" in cmd:
                s = cmd[cmd.index("--search") + 1]
                items = [i for i in items if s in json.dumps(i)]
            out = json.dumps(items)
        elif cmd[:2] == ["get", "item"]:
            out = json.dumps(next(i for i in self.items if i["id"] == cmd[2]))
        elif cmd[:2] == ["create", "folder"]:
            f = json.loads(base64.b64decode(input))
            f["id"] = f"f-{len(self.folders)}"
            self.folders.append(f)
            out = json.dumps(f)
        elif cmd[:2] == ["create", "item"]:
            it = json.loads(base64.b64decode(input))
            it["id"] = f"i-{len(self.items) + 1}"
            it["creationDate"] = "2026-10-12T10:00:00Z"
            self.items.append(it)
            out = json.dumps(it)
        elif cmd[:2] == ["edit", "item"]:
            it = json.loads(base64.b64decode(input))
            it["id"] = cmd[2]
            self.items = [it if i["id"] == cmd[2] else i for i in self.items]
            out = json.dumps(it)
        else:
            return subprocess.CompletedProcess(argv, 1, "", "unknown command")
        return subprocess.CompletedProcess(argv, 0, out, "")


def _today() -> date:
    return datetime.now(timezone.utc).date()


@pytest.fixture
def fake():
    return FakeBw()


@pytest.fixture
def bw(fake):
    return Bw(session="sess", binary="/fake/bw", runner=fake)


def test_locked_without_session(fake):
    with pytest.raises(BwLocked):
        Bw(session=None, binary="/fake/bw", runner=fake).list_items()
    assert Bw(session=None, binary="/fake/bw", runner=fake).status()["status"] == "unlocked"


def test_identity_coverage_and_pick_never_leak_private(bw):
    ident = accounts.load_identity(bw)
    cov = ident.coverage()
    assert "email" in cov["known"] and "custom:birth_date" in cov["known"]
    assert "passport_number" in cov["stored_never_shared"]
    assert "address1" in cov["missing"]
    assert ident.pick(["first_name", "email", "custom:birth_date"]) == {
        "first_name": "Filip",
        "email": "f@example.com",
        "custom:birth_date": "1990-01-01",
    }
    with pytest.raises(ValueError):
        ident.pick(["passport_number"])
    with pytest.raises(ValueError):
        ident.pick(["nonsense"])
    assert "SECRET" not in json.dumps(ident.pick(["custom:pesel"]) if "custom:pesel" in ident.custom else {})
    assert "pesel" not in ident.custom  # hidden field never loaded


def test_create_login_generates_and_records(bw, fake):
    meta = accounts.create_login(
        bw,
        name="Shop",
        url="https://shop.example.com/signup?x=1",
        username="f@example.com",
        purpose="buy a lamp",
        created_by="Hermes",
        identity="Filip",
        shared=["first_name", "email"],
        rotate_days=3,
    )
    assert "pw-" not in json.dumps(meta) and "password" not in (
        json.dumps(meta).replace("passwordRevisionDate", "").replace('"password"', "")
    )
    assert meta["uris"] == ["https://shop.example.com"]
    f = meta["fields"]
    assert f["hermes_purpose"] == "buy a lamp" and f["hermes_shared"] == "first_name,email"
    assert f["hermes_rotated"] == "no" and date.fromisoformat(f["hermes_rotate_by"]) > _today()
    stored = next(i for i in fake.items if i["id"] == meta["id"])
    assert stored["login"]["password"].startswith("pw-") and stored["folderId"] == "f-1"
    assert ["generate", "-ulns", "--length", "24", "--nointeraction"] in fake.calls
    # duplicate guard
    with pytest.raises(BwError):
        accounts.create_login(
            bw, name="Shop", url="shop.example.com", username="f@example.com", purpose="again", created_by="Hermes"
        )
    assert accounts.find_existing(bw, "https://shop.example.com", None)[0]["name"] == "Shop"


def test_rotation_due_and_mark(bw):
    meta = accounts.create_login(
        bw, name="Shop", url="https://shop.example.com", username="u", purpose="p", created_by="Claude", rotate_days=3
    )
    assert accounts.rotation_due(bw, today=_today()) == []
    due = accounts.rotation_due(bw, today=date.fromisoformat(meta["fields"]["hermes_rotate_by"]))
    assert [d["id"] for d in due] == [meta["id"]]
    accounts.mark_rotated(bw, meta["id"])
    assert accounts.rotation_due(bw, today=date(2030, 1, 1)) == []


def test_purpose_required(bw):
    with pytest.raises(ValueError):
        accounts.create_login(bw, name="x", url="https://x.example", username="u", purpose="  ", created_by="Claude")


def test_item_metadata_strips_secrets():
    item = {
        "id": "1",
        "type": 1,
        "name": "n",
        "login": {"username": "u", "password": "SECRET", "totp": "SEED", "uris": [{"uri": "https://a.example"}]},
        "fields": [{"name": "h", "value": "SECRET", "type": 1}, {"name": "t", "value": "ok", "type": 0}],
    }
    meta = item_metadata(item)
    assert "SECRET" not in json.dumps(meta) and "SEED" not in json.dumps(meta)
    assert meta["has_totp"] is True and meta["fields"] == {"t": "ok"}


# -- fake Notion -------------------------------------------------------------------------------


class FakeNotion:
    def __init__(self):
        self.pages: dict[str, dict] = {}
        self.ds = {"id": "ds-1", "title": [{"plain_text": accountmap.DB_TITLE}]}
        self.patches: list[dict] = []

    def __call__(self, req, timeout=30):
        path = req.full_url.replace(accountmap.API, "")
        body = json.loads(req.data) if req.data else {}
        if path == "/search":
            res = {"results": [self.ds] if self.ds else []}
        elif path == "/databases":
            self.ds = {"id": "ds-1", "title": body["title"]}
            res = {"data_sources": [{"id": "ds-1"}]}
        elif path.startswith("/data_sources/ds-1/query"):
            res = {"results": list(self.pages.values()), "has_more": False}
        elif path.startswith("/data_sources/ds-1"):
            if req.get_method() == "PATCH":
                self.patches.append(body)
            res = self.ds
        elif path == "/pages":
            pid = f"p-{len(self.pages) + 1}"
            self.pages[pid] = {
                "id": pid,
                "url": f"https://notion.so/{pid}",
                "properties": _materialize(body["properties"]),
            }
            res = self.pages[pid]
        elif path.startswith("/pages/"):
            pid = path.split("/")[2]
            self.pages[pid]["properties"].update(_materialize(body["properties"]))
            res = self.pages[pid]
        else:
            raise AssertionError(path)
        return io.BytesIO(json.dumps(res).encode())


def _materialize(props: dict) -> dict:
    """Turn write-shaped properties into read-shaped ones (what the API returns)."""
    out = {}
    for k, v in props.items():
        kind = next(iter(v))
        val = v[kind]
        if kind in ("title", "rich_text"):
            out[k] = {"type": kind, kind: [{"plain_text": x["text"]["content"]} for x in val]}
        else:
            out[k] = {"type": kind, kind: val}
    return out


def test_map_init_upsert_link_mermaid():
    fake = FakeNotion()
    fake.ds = None
    n = accountmap.Notion(token="t", opener=fake)
    ds = n.ensure_database("parent-1")
    assert ds["id"] == "ds-1" and len(fake.patches) == 2  # two self-relations added
    n.upsert(
        "ds-1", {"Name": "Google (fjk)", "URL": "https://accounts.google.com", "Login via": "password", "Has 2FA": True}
    )
    n.upsert(
        "ds-1",
        {
            "Name": "Claude",
            "URL": "https://claude.ai",
            "Login via": "google",
            "Bitwarden item": "bw-9",
            "Data shared": ["email"],
        },
    )
    n.upsert("ds-1", {"Name": "Claude renamed", "Bitwarden item": "bw-9"})  # same item → update, not a new row
    assert len(fake.pages) == 2
    n.link("ds-1", "Claude renamed", "Logs in via", "Google (fjk)")
    rows = n.rows("ds-1")
    claude = next(r for r in rows if r["Name"] == "Claude renamed")
    assert claude["Logs in via"] == ["p-1"] and claude["Data shared"] == ["email"]
    graph = accountmap.mermaid(rows)
    assert "logs in via" in graph and "Google (fjk)" in graph
    with pytest.raises(RuntimeError):
        n.link("ds-1", "nope", "Connected to", "Claude renamed")


# -- CLI ---------------------------------------------------------------------------------------


def test_cli_create_adds_to_map(bw, capsys):
    fake_n = FakeNotion()
    n = accountmap.Notion(token="t", opener=fake_n)
    rc = cli.main(
        [
            "create",
            "--url",
            "https://portal.example.org",
            "--username",
            "f@example.com",
            "--purpose",
            "e-urząd",
            "--shared",
            "first_name,last_name",
        ],
        bw=bw,
        notion=n,
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["created"]["name"] == "portal.example.org" and out["map"].startswith("https://notion.so/")
    assert "pw-" not in json.dumps(out)
    row = accountmap.row_to_dict(next(iter(fake_n.pages.values())))
    assert (
        row["Status"] == "to-rotate"
        and row["Created by"] == "Claude"
        and row["Data shared"] == ["first_name", "last_name"]
    )
    rc = cli.main(["share", "email", "city"], bw=bw)
    assert rc == 0 and json.loads(capsys.readouterr().out) == {"email": "f@example.com", "city": "Kraków"}
    rc = cli.main(["share", "passport_number"], bw=bw)
    assert rc == 1 and "never shared" in capsys.readouterr().out


# -- Hermes plugin -----------------------------------------------------------------------------


def test_plugin_gate_blocks_fill_without_grant_and_secret_terminal():
    import identity_vault as plug

    plug._grants.clear()
    plug._cfg.clear()
    assert plug._on_pre_tool_call(tool_name="browser_vault_fill", args={"handle": "bw:1"})["action"] == "block"
    for cmd in (
        "bw get password abc",
        "cd x && bw list items",
        "hidentity create --url u",
        "/usr/bin/bw get totp 1",
        "bws secret get X",
    ):
        assert plug._on_pre_tool_call(tool_name="terminal", args={"command": cmd})["action"] == "block", cmd
    for cmd in ("bw status", "hidentity coverage", "hidentity rotation-due", "hidentity map list", "echo bw"):
        assert plug._on_pre_tool_call(tool_name="terminal", args={"command": cmd}) is None, cmd
    plug._grants["bw:1"] = 1e12
    assert plug._on_pre_tool_call(tool_name="browser_vault_fill", args={"handle": "bw:1"}) is None
    plug._on_post_tool_call(tool_name="browser_vault_fill", args={"handle": "bw:1"})
    assert plug._on_pre_tool_call(tool_name="browser_vault_fill", args={"handle": "bw:1"})["action"] == "block"


def test_plugin_login_consent(monkeypatch):
    import identity_vault as plug

    plug._grants.clear()
    plug._cfg.clear()
    monkeypatch.setattr(plug, "_ask", lambda *a, **k: False)
    res = json.loads(plug.identity_request_login("bw:7", "instagram.com", "read DMs"))
    assert res["error_type"] == "consent_refused" and "bw:7" not in plug._grants
    monkeypatch.setattr(plug, "_ask", lambda *a, **k: True)
    assert json.loads(plug.identity_request_login("bw:7", "instagram.com", "read DMs"))["success"]
    assert plug._grant_ok("bw:7")
    assert json.loads(plug.identity_request_login("bw:7", "instagram.com", ""))["success"] is False


def test_plugin_create_account_consent(monkeypatch, bw):
    import identity_vault as plug

    plug._grants.clear()
    plug._cfg.clear()
    asked: list[tuple] = []

    def ask(title, message, description):
        asked.append((title, message, description))
        return True

    monkeypatch.setattr(plug, "_ask", ask)
    monkeypatch.setattr(plug, "_bw", lambda: (bw, accounts, accountmap))
    monkeypatch.setattr(accountmap, "Notion", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no notion")))
    res = json.loads(
        plug.identity_create_account(
            "https://shop.example.com/x", "f@example.com", "kup lampę", shared_fields=["first_name", "email"]
        )
    )
    assert res["success"] and res["handle"].startswith("bw:") and plug._grant_ok(res["handle"])
    assert "shop.example.com" in asked[0][1] and "kup lampę" in asked[0][2]
    assert "pw-" not in json.dumps(res) and res["map"].startswith("not added")
    again = json.loads(plug.identity_create_account("https://shop.example.com", "f@example.com", "again"))
    assert again["error_type"] == "exists"
    share = json.loads(plug.identity_share("shop.example.com", "formularz", ["first_name", "email"]))
    assert share["values"] == {"first_name": "Filip", "email": "f@example.com"}
