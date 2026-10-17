"""``hidentity`` command line.

Everything prints JSON (metadata only, never a password). The agent-facing consent happens outside
this CLI: in Hermes through the ``identity_vault`` plugin, in Claude Code by asking Filip in chat
before ``create``/``share`` and letting Claude Code's own permission prompt show the command.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import accountmap, accounts
from .bw import Bw, BwError


def _out(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hidentity", description="Identity, accounts and account map on Bitwarden + Notion."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Bitwarden status (logged in? locked?)")

    c = sub.add_parser("coverage", help="Which identity fields the vault knows about Filip (names only)")
    c.add_argument("--identity")

    s = sub.add_parser("share", help="Print identity field VALUES for a sign-up form (ask Filip first!)")
    s.add_argument("fields", nargs="+", help="e.g. first_name last_name email phone city custom:birth_date")
    s.add_argument("--identity")

    f = sub.add_parser("find", help="Existing logins for a site")
    f.add_argument("url")
    f.add_argument("--username")

    cr = sub.add_parser("create", help="Generate a password with Bitwarden and store a new login (ask Filip first!)")
    cr.add_argument("--url", required=True)
    cr.add_argument("--username", required=True)
    cr.add_argument("--name", help="Item name (default: host)")
    cr.add_argument("--purpose", required=True, help="Why the account is created")
    cr.add_argument("--created-by", default="Claude", choices=["Claude", "Hermes", "Filip"])
    cr.add_argument("--identity", default="")
    cr.add_argument("--shared", default="", help="Comma list of identity fields typed into the form")
    cr.add_argument("--login-via", default="password", choices=accountmap.LOGIN_VIA)
    cr.add_argument("--rotate-days", type=int, default=accounts.DEFAULT_ROTATE_DAYS)
    cr.add_argument("--passphrase", action="store_true")
    cr.add_argument("--no-map", action="store_true", help="Do not add the account to the Notion map")

    sub.add_parser("accounts", help="Logins created by agents (metadata)")
    rd = sub.add_parser("rotation-due", help="Accounts whose initial password should have been rotated by now")
    rd.add_argument("--today")
    mr = sub.add_parser("mark-rotated", help="Filip rotated the password: stop reminding")
    mr.add_argument("item_id")

    m = sub.add_parser("map", help="Account map in Notion")
    msub = m.add_subparsers(dest="mapcmd", required=True)
    mi = msub.add_parser("init", help="Create the Notion database under a page")
    mi.add_argument("--parent", required=True, help="Notion page id to hold the database")
    msub.add_parser("list")
    ma = msub.add_parser("add", help="Add or update an account row")
    ma.add_argument("--name", required=True)
    ma.add_argument("--url")
    ma.add_argument("--username")
    ma.add_argument("--identity", default="Filip")
    ma.add_argument("--login-via", choices=accountmap.LOGIN_VIA)
    ma.add_argument("--status", choices=accountmap.STATUS)
    ma.add_argument("--created-by", choices=["Filip", "Hermes", "Claude"])
    ma.add_argument("--purpose")
    ma.add_argument("--shared", help="Comma list")
    ma.add_argument("--bitwarden-item")
    ma.add_argument("--rotate-by")
    ma.add_argument("--has-2fa", action="store_true")
    ma.add_argument("--notes")
    ml = msub.add_parser("link", help="Draw an edge: FROM --via TO (login) or FROM --connected TO")
    ml.add_argument("from_name")
    ml.add_argument("to_name")
    g = ml.add_mutually_exclusive_group(required=True)
    g.add_argument("--via", action="store_true", help="FROM logs in via TO")
    g.add_argument("--connected", action="store_true", help="FROM is connected to TO (integration/OAuth)")
    msub.add_parser("sync", help="Push agent-created Bitwarden accounts into the map")
    msub.add_parser("mermaid", help="Print the map as a Mermaid graph")
    return p


def _map_row_from_meta(meta: dict) -> dict:
    f = meta.get("fields") or {}
    M = accounts.META
    return {
        "Name": meta["name"],
        "URL": (meta.get("uris") or [None])[0],
        "Username": meta.get("username"),
        "Identity": f.get(M["identity"]) or "Filip",
        "Login via": f.get(M["login_via"]) or "password",
        "Status": "active" if f.get(M["rotated"]) == "yes" else "to-rotate",
        "Created by": f.get(M["created_by"]),
        "Purpose": f.get(M["purpose"]),
        "Data shared": [x for x in (f.get(M["shared"]) or "").split(",") if x],
        "Bitwarden item": meta["id"],
        "Rotate by": f.get(M["rotate_by"]),
        "Has 2FA": bool(meta.get("has_totp")),
    }


def main(argv: list[str] | None = None, bw: Bw | None = None, notion: accountmap.Notion | None = None) -> int:
    args = build_parser().parse_args(argv)
    bw = bw or Bw()
    try:
        if args.cmd == "status":
            _out(bw.status())
        elif args.cmd == "coverage":
            ident = accounts.load_identity(bw, args.identity)
            _out({"identity": ident.name, **ident.coverage()})
        elif args.cmd == "share":
            ident = accounts.load_identity(bw, args.identity)
            _out(ident.pick(args.fields))
        elif args.cmd == "find":
            _out(accounts.find_existing(bw, args.url, args.username))
        elif args.cmd == "create":
            from urllib.parse import urlparse

            name = args.name or urlparse(accounts.origin_of(args.url)).hostname
            shared = [x.strip() for x in args.shared.split(",") if x.strip()]
            meta = accounts.create_login(
                bw,
                name=name,
                url=args.url,
                username=args.username,
                purpose=args.purpose,
                created_by=args.created_by,
                identity=args.identity,
                shared=shared,
                login_via=args.login_via,
                rotate_days=args.rotate_days,
                passphrase=args.passphrase,
            )
            result = {
                "created": meta,
                "map": None,
                "next": f"Tell Filip to rotate the generated password by {meta['fields'][accounts.META['rotate_by']]} "
                "(hidentity rotation-due reminds him).",
            }
            if not args.no_map:
                try:
                    n = notion or accountmap.Notion()
                    ds = n.ensure_database(None)
                    page = n.upsert(ds["id"], _map_row_from_meta(meta))
                    result["map"] = page.get("url")
                except Exception as exc:  # the account exists; the map is best effort
                    result["map"] = f"not added: {exc}"
            _out(result)
        elif args.cmd == "accounts":
            _out(accounts.accounts(bw))
        elif args.cmd == "rotation-due":
            from datetime import date

            _out(accounts.rotation_due(bw, date.fromisoformat(args.today) if args.today else None))
        elif args.cmd == "mark-rotated":
            _out(accounts.mark_rotated(bw, args.item_id))
        elif args.cmd == "map":
            n = notion or accountmap.Notion()
            if args.mapcmd == "init":
                ds = n.ensure_database(args.parent)
                _out({"data_source_id": ds["id"], "title": accountmap.DB_TITLE})
                return 0
            ds = n.ensure_database(None)
            if args.mapcmd == "list":
                _out(n.rows(ds["id"]))
            elif args.mapcmd == "add":
                row = {
                    "Name": args.name,
                    "URL": args.url,
                    "Username": args.username,
                    "Identity": args.identity,
                    "Login via": args.login_via,
                    "Status": args.status,
                    "Created by": args.created_by,
                    "Purpose": args.purpose,
                    "Data shared": args.shared,
                    "Bitwarden item": args.bitwarden_item,
                    "Rotate by": args.rotate_by,
                    "Has 2FA": args.has_2fa,
                    "Notes": args.notes,
                }
                page = n.upsert(ds["id"], row, by="Bitwarden item" if args.bitwarden_item else "Name")
                _out({"url": page.get("url")})
            elif args.mapcmd == "link":
                n.link(ds["id"], args.from_name, "Logs in via" if args.via else "Connected to", args.to_name)
                _out({"linked": [args.from_name, "via" if args.via else "connected", args.to_name]})
            elif args.mapcmd == "sync":
                urls = [n.upsert(ds["id"], _map_row_from_meta(m)).get("url") for m in accounts.accounts(bw)]
                _out({"synced": len(urls)})
            elif args.mapcmd == "mermaid":
                print(accountmap.mermaid(n.rows(ds["id"])))
        return 0
    except (BwError, RuntimeError, ValueError) as exc:
        _out({"error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
