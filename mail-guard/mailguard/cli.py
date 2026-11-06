"""mailguard CLI.

  mailguard analyze FILE.eml [--json]            verdict for a saved message (``-`` = stdin)
  mailguard card FILE.eml                        LLM-safe card (what Hermes should read)
  mailguard gmail ACCOUNT [--query Q | --id ID] [--limit N] [--format summary|card|json]
  mailguard url URL [URL...]                     link triage without opening it
  mailguard save-attachments FILE.eml --out DIR  quarantine copy: images re-encoded, risky files withheld
  mailguard image IN OUT                         re-encode one image to a clean PNG

Exit code = worst label: 0 ok, 1 uwaga, 2 podejrzany, 3 niebezpieczny (not an error!); gmail: 4 = fetch errors
only. In cron jobs use ``gmail --exit-zero`` so a phishing mail is not reported as a failed job.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .analyze import LABEL_PL, analyse, card, parse
from .attachments import analyse_attachment, sanitize_image
from .domains import protected_domains
from .links import analyse_link
from .sanitize import Link

_EXIT = {"ok": 0, "uwaga": 1, "podejrzany": 2, "niebezpieczny": 3}


def _read(path: str) -> bytes:
    return sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()


def _summary(rep) -> str:
    s = rep.sender
    head = f"{rep.label.upper():13} {rep.score:3}/100  {s['address']}  {rep.subject[:70]}"
    reasons = "".join(f"\n    - {r['text']}" for r in rep.reasons[:5])
    return head + reasons


def cmd_analyze(a) -> int:
    rep = analyse(_read(a.file), protected_domains(a.protected))
    print(json.dumps(rep.to_dict(), ensure_ascii=False, indent=2) if a.json else _summary(rep))
    return _EXIT[rep.label]


def cmd_card(a) -> int:
    rep = analyse(_read(a.file), protected_domains(a.protected))
    print(card(rep))
    return _EXIT[rep.label]


def cmd_gmail(a) -> int:
    from concurrent.futures import ThreadPoolExecutor

    from . import gmail

    token = gmail.access_token(a.account)
    ids = [a.id] if a.id else gmail.list_ids(token, a.query, a.limit)
    worst = 0
    errors = 0
    prot = protected_domains(a.protected)

    def fetch(mid):
        try:
            return mid, analyse(gmail.raw_message(token, mid), prot), None
        except Exception as e:  # noqa: BLE001 - one bad message must not stop the run
            return mid, None, e

    # a few parallel GETs: Gmail allows ~250 quota units/s per user, messages.get costs 5
    with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
        results = list(pool.map(fetch, ids))
    for mid, rep, err in results:
        if err is not None:
            errors += 1
            print(json.dumps({"gmail_id": mid, "error": f"{type(err).__name__}: {err}"}) if a.format == "json"
                  else f"{mid}  BŁĄD {type(err).__name__}: {err}", file=sys.stderr)
            continue
        worst = max(worst, _EXIT[rep.label])
        if a.format == "json":
            print(json.dumps({"gmail_id": mid, **rep.to_dict()}, ensure_ascii=False))
        elif a.format == "card":
            print(f"=== gmail_id {mid}\n{card(rep)}\n")
        else:
            print(f"{mid}  {_summary(rep)}")
    if errors:
        print(f"błędy pobierania: {errors}/{len(ids)}", file=sys.stderr)
    return 0 if a.exit_zero else (4 if errors and worst == 0 else worst)


def cmd_url(a) -> int:
    worst = 0
    for i, u in enumerate(a.urls, 1):
        rep = analyse_link(Link(u, ""), i, protected_domains(a.protected))
        label = "niebezpieczny" if rep.score >= 50 else "podejrzany" if rep.score >= 25 else \
            "uwaga" if rep.score >= 10 else "ok"
        worst = max(worst, _EXIT[label])
        print(f"{label.upper():13} {rep.score:3}  {rep.defanged}")
        for _, _, t in rep.flags:
            print(f"    - {t}")
    return worst


def cmd_save(a) -> int:
    msg = parse(_read(a.file))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, part in enumerate((p for p in msg.iter_attachments() if not p.is_multipart()), 1):
        data = part.get_payload(decode=True) or b""
        rep = analyse_attachment(part.get_filename() or "", part.get_content_type(), data, i)
        entry = {"id": rep.id, "filename": rep.filename, "sha256": rep.sha256, "kind": rep.kind,
                 "score": rep.score, "flags": [c for _, c, _ in rep.flags], "saved": None}
        if rep.kind in ("png", "jpeg", "gif", "riff") and rep.score < 50:
            try:
                clean = sanitize_image(data)
                dest = out / f"{rep.sha256[:16]}.png"
                dest.write_bytes(clean)
                entry["saved"], entry["note"] = dest.name, "obraz przekodowany do czystego PNG"
            except ValueError as e:
                entry["note"] = f"obraz odrzucony: {e}"
        elif rep.score >= 50 and not a.include_dangerous:
            entry["note"] = "wstrzymany: wysokie ryzyko (użyj --include-dangerous, tylko do analizy w sandboksie)"
        else:
            # Neutral name, no extension the OS would act on, read-only. Documents go to CDR before opening.
            dest = out / f"{rep.sha256[:16]}.quarantine"
            dest.write_bytes(data)
            os.chmod(dest, 0o400)
            entry["saved"] = dest.name
            entry["note"] = "do konwersji Dangerzone przed otwarciem" if rep.needs_cdr else "zapisany w kwarantannie"
        manifest.append(entry)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for e in manifest:
        print(f"{e['id']} {e['filename'][:60]:60} ryzyko={e['score']:3} -> {e['saved'] or '-'} ({e.get('note', '')})")
    return 0


def cmd_image(a) -> int:
    try:
        Path(a.out).write_bytes(sanitize_image(Path(a.inp).read_bytes()))
    except ValueError as e:
        print(f"odrzucony: {e}", file=sys.stderr)
        return 3
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mailguard", description="Bezpieczne czytanie maili dla Hermesa")
    p.add_argument("--protected", help="dodatkowa lista chronionych domen (jedna na linię)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("analyze")
    s.add_argument("file")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_analyze)
    s = sub.add_parser("card")
    s.add_argument("file")
    s.set_defaults(fn=cmd_card)
    s = sub.add_parser("gmail")
    s.add_argument("account")
    s.add_argument("--query", default="in:inbox newer_than:1d")
    s.add_argument("--id")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--format", choices=["summary", "card", "json"], default="summary")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--exit-zero", action="store_true", help="zawsze kod 0 (dla cronów)")
    s.set_defaults(fn=cmd_gmail)
    s = sub.add_parser("url")
    s.add_argument("urls", nargs="+")
    s.set_defaults(fn=cmd_url)
    s = sub.add_parser("save-attachments")
    s.add_argument("file")
    s.add_argument("--out", required=True)
    s.add_argument("--include-dangerous", action="store_true")
    s.set_defaults(fn=cmd_save)
    s = sub.add_parser("image")
    s.add_argument("inp")
    s.add_argument("out")
    s.set_defaults(fn=cmd_image)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

__all__ = ["main", "LABEL_PL"]
