#!/usr/bin/env python3
"""Bench: can a local model (llama.cpp llama-server, OpenAI-compatible) drive the home-inventory skill?

Each case is one Polish request from Filip (sometimes with a follow-up). The model gets SKILL.md as its system
prompt and one `terminal` tool, exactly like Hermes. Commands are NOT run in a shell: only `dom.py` invocations
are accepted (also `echo/printf ... |` and heredocs feeding `dom map import -`, and `&&` chains); anything else
is refused. dom.py runs in-process against a fresh temporary database per run, then the database (and for
read-only questions the final answer) is checked.

  python bench.py --oracle                      # validate cases/checks with the golden commands (no model)
  python bench.py --url http://127.0.0.1:8081 --runs 3 --out results   # bench a running llama-server

Standard library only. Date is fixed to 2026-10-15 (DOM_TODAY).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import shlex
import sqlite3
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import dom  # noqa: E402

TODAY = "2026-10-15"

ROOMS = """\
Mieszkanie
  Salon
  Gabinet
  Sypialnia
  Łazienka
  Korytarz | przedpokój  # tu stoi stacja dokująca Roborocka
  Pomieszczenie gospodarcze | gospodarcze, schowek
  Pokój Teosia | pokój syna
"""

FURNISHED = ROOMS + """\
  Kuchnia
    Lodówka
      Półka 1
      Półka 2
      Półka 3
      Szuflada na warzywa
    Szafka pod zlewem
"""

TEOS = """\
Mieszkanie
  Pokój Teosia
    Szafa 1
      Półka 1
      Półka 2
      Półka 3
    Komoda
      Szuflada 1
      Szuflada 2
      Szuflada 3
"""


# ---------------------------------------------------------------- db helpers for checks

def q(db, sql, *p):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return con.execute(sql, p).fetchall()
    finally:
        con.close()


def paths(db) -> dict[int, str]:
    con = dom.connect(db)
    try:
        places = dom.place_rows(con)
        return {pid: dom.place_path(places, pid, pretty=False) for pid in places}
    finally:
        con.close()


def stock(db, name_like: str):
    """Batches still at home whose item name contains name_like (folded)."""
    pp = paths(db)
    rows = q(db, "SELECT s.*, i.name, i.category FROM stock s JOIN items i ON i.id=s.item_id WHERE s.status='jest'")
    out = []
    for r in rows:
        if dom.fold(name_like) in dom.fold(r["name"]):
            d = dict(r)
            d["path"] = pp.get(r["place_id"], "")
            out.append(d)
    return out


def children(db, parent_path_tail: str) -> list[dict]:
    pp = paths(db)
    parents = [pid for pid, p in pp.items() if dom.fold(p).endswith(dom.fold(parent_path_tail))]
    if len(parents) != 1:
        return []
    return [dict(r) for r in q(db, "SELECT * FROM places WHERE parent_id=?", parents[0])]


def find_place(db, contains: list[str]) -> list[str]:
    """Paths containing all fragments (folded)."""
    return [p for p in paths(db).values() if all(dom.fold(c) in dom.fold(p) for c in contains)]


def ok(cond: bool, why: str):
    return (bool(cond), "" if cond else why)


def has(text: str, *words) -> bool:
    t = dom.fold(text)
    return all(dom.fold(w) in t for w in words)


# ---------------------------------------------------------------- cases

def c_p1(db, text):
    s = stock(db, "mleko")
    return ok(len(s) == 1 and s[0]["qty"] == 2 and s[0]["expires"] == "2026-10-20"
              and s[0]["path"].endswith("Lodówka > Półka 1"), f"mleko: {s}")


def c_p2(db, text):
    s = stock(db, "płyn")
    return ok(len(s) == 1 and s[0]["category"] == "chemia" and s[0]["path"].endswith("Szafka pod zlewem")
              and s[0]["expires"] is None, f"płyn: {s}")


def c_p3(db, text):
    s = stock(db, "jogurt")
    return ok(len(s) == 1 and s[0]["expires"] == "2026-10-16" and s[0]["path"].endswith("Lodówka > Półka 2")
              and s[0]["side"] == "prawo", f"jogurt: {s}")


def c_p4(db, text):
    s = stock(db, "mleko")
    items = q(db, "SELECT name FROM items")
    new = [b for b in s if b["expires"] == "2026-10-25"]
    return ok(len(s) == 2 and len(items) == 1 and new and new[0]["path"].endswith("Lodówka > Półka 1"),
              f"mleko: {s}; items: {[r['name'] for r in items]}")


def c_p5(db, text):
    s = stock(db, "body")
    return ok(len(s) == 1 and s[0]["qty"] == 3 and s[0]["path"].endswith("Szafa 1 > Półka 2")
              and s[0]["side"] == "lewo" and s[0]["depth"] == "przód" and s[0]["category"] == "ubrania", f"body: {s}")


def c_p6(db, text):
    m, se, k = stock(db, "masło"), stock(db, "ser"), stock(db, "kefir")
    good = (len(m) == 1 and m[0]["expires"] == "2026-10-30" and len(se) == 1 and se[0]["expires"] == "2026-10-25"
            and len(k) == 1 and k[0]["qty"] == 2 and k[0]["expires"] == "2026-10-19"
            and all(b["path"].endswith("Lodówka > Półka 3") for b in m + se + k))
    return ok(good, f"masło {m}; ser {se}; kefir {k}")


def c_p7(db, text):
    s = stock(db, "mleko")
    return ok(len(s) == 1 and s[0]["qty"] == 1, f"mleko: {s}")


def c_p8(db, text):
    s = stock(db, "ser")
    return ok(len(s) == 1 and s[0]["expires"] == "2026-10-30", f"ser: {s}")


def c_p9(db, text):
    return ok(has(text, "zlew"), f"answer: {text[:200]}")


def c_p10(db, text):
    return ok(has(text, "kurczak") and has(text, "jogurt") and not has(text, "ryż"), f"answer: {text[:300]}")


def c_p11(db, text):
    return ok(has(text, "kurczak"), f"answer: {text[:300]}")


def c_p12(db, text):
    s = stock(db, "jogurt")
    return ok(len(s) == 1 and s[0]["expires"] == "2026-10-22" and s[0]["path"].endswith("Lodówka > Półka 1"),
              f"jogurt: {s}")


def c_p13(db, text):
    s = stock(db, "ryż")
    if not s:
        return ok("?" in text, f"no ryż and no question: {text[:200]}")
    return ok(all("spiżar" in b["path"].lower() or "spizar" in dom.fold(b["path"]) for b in s), f"ryż: {s}")


def c_m1(db, text):
    k = find_place(db, ["Kuchnia", "Lodówka"])
    if not k:
        return ok(False, f"no Kuchnia > Lodówka: {list(paths(db).values())}")
    ch = children(db, min(k, key=len))
    shelves = [c for c in ch if c["kind"] == "półka"]
    drawers = [c for c in ch if c["kind"] == "szuflada"]
    return ok(len(shelves) == 3 and len(drawers) == 1, f"lodówka children: {[c['name'] for c in ch]}")


def _furniture_with(db, room, word, kind, n):
    f = [p for p in find_place(db, [room, word]) if dom.fold(p.split(" > ")[-1]).startswith(dom.fold(word)[:4])]
    if not f:
        return ok(False, f"no {room} > {word}: {list(paths(db).values())}")
    ch = children(db, min(f, key=len))
    got = [c for c in ch if c["kind"] == kind]
    return ok(len(got) == n, f"{min(f, key=len)} children: {[c['name'] for c in ch]}")


def c_m2(db, text):
    return _furniture_with(db, "Pokój Teosia", "komoda", "szuflada", 4)


def c_m3(db, text):
    return _furniture_with(db, "Sypialnia", "szafa", "półka", 5)


def c_m4(db, text):
    return _furniture_with(db, "Łazienka", "szafka", "półka", 2)


def c_m5(db, text):
    return ok(any("drzwi" in p.split(" > ")[-1].lower() for p in find_place(db, ["Lodówka"])),
              f"places: {find_place(db, ['Lodówka'])}")


def c_m6(db, text):
    pp = list(paths(db).values())
    return ok(any(p.endswith("Pokój Teosia > Szafa biała") for p in pp)
              and not any(p.endswith("Pokój Teosia > Szafa 1") for p in pp)
              and any(p.endswith("Szafa biała > Półka 3") for p in pp), f"places: {pp}")


def c_m7(db, text):
    s = stock(db, "body")
    return ok(len(s) == 1 and s[0]["path"].endswith("Komoda > Szuflada 2"), f"body: {s}")


def c_m8(db, text):
    pp = list(paths(db).values())
    return ok(not any("Komoda" in p for p in pp) and any(p.endswith("Szafa 1 > Półka 3") for p in pp), f"places: {pp}")


def c_m9(db, text):
    return ok(has(text, "mlek") and has(text, "jogurt"), f"answer: {text[:300]}")


def c_m10(db, text):
    return ok(has(text, "szaf") and has(text, "komod"), f"answer: {text[:300]}")


M = "~/.hermes/scripts/dom.py"
CASES = [
    dict(id="P1 add+place+exp", base=FURNISHED, setup=[],
         say=["Przywiozłem mleko, 2 litry, ważne do 20.10. Wstawiłem do lodówki na górną półkę."],
         check=c_p1, golden=[f'{M} add mleko --qty 2 --unit l --exp 20.10 --where "lodówka > półka 1"']),
    dict(id="P2 chemia", base=FURNISHED, setup=[],
         say=["Kupiłem płyn do naczyń, schowałem go do szafki pod zlewem."],
         check=c_p2, golden=[f'{M} add "płyn do naczyń" --cat chemia --where "szafka pod zlewem"']),
    dict(id="P3 sector", base=FURNISHED, setup=[],
         say=["Jogurt naturalny, ważny do jutra, postawiłem w lodówce na drugiej półce po prawej."],
         check=c_p3, golden=[f'{M} add "jogurt naturalny" --exp jutro --where "lodówka > półka 2" --side prawo']),
    dict(id="P4 usual place", base=FURNISHED, setup=[["add", "mleko", "--exp", "18.10", "--where", "lodówka > półka 1"]],
         say=["Przywiozłem jeszcze jedno mleko, ważne do 25 października."],
         check=c_p4, golden=[f'{M} add mleko --exp "25 października"']),
    dict(id="P5 clothes from bottom", base=TEOS, setup=[],
         say=["Body Teosia z długim rękawem leżą w jego szafie na drugiej półce od dołu, z lewej z przodu. Są trzy sztuki."],
         check=c_p5, golden=[f'{M} add "body Teosia z długim rękawem" --qty 3 --cat ubrania '
                             '--where "pokój Teosia > szafa 1 > półka 2 od dołu" --side lewo --depth przód']),
    dict(id="P6 several products", base=FURNISHED, setup=[],
         say=["Przywiozłem z zakupów: masło ważne do 30.10, ser żółty do 25.10 i dwa kefiry do 19.10. "
              "Wszystko poszło do lodówki na trzecią półkę."],
         check=c_p6, golden=[f'{M} add masło --exp 30.10 --where "lodówka > półka 3"',
                             f'{M} add "ser żółty" --exp 25.10 --where "lodówka > półka 3"',
                             f'{M} add kefir --qty 2 --exp 19.10 --where "lodówka > półka 3"']),
    dict(id="P7 use", base=FURNISHED, setup=[["add", "mleko", "--qty", "2", "--unit", "l", "--exp", "20.10",
                                               "--where", "lodówka > półka 1"]],
         say=["Zużyłem litr mleka."], check=c_p7, golden=[f"{M} use mleko --qty 1"]),
    dict(id="P8 throw expired", base=FURNISHED,
         setup=[["add", "ser żółty", "--exp", "2026-10-12", "--where", "lodówka > półka 2"],
                ["add", "ser żółty", "--exp", "2026-10-30", "--where", "lodówka > półka 2"]],
         say=["Wyrzuciłem przeterminowany ser."], check=c_p8, golden=[f'{M} throw "ser żółty" --expired-only --all']),
    dict(id="P9 where", base=FURNISHED, setup=[["add", "płyn do naczyń", "--cat", "chemia", "--where", "szafka pod zlewem"]],
         say=["Gdzie jest płyn do naczyń?"], check=c_p9, golden=[f'{M} where "płyn do naczyń"']),
    dict(id="P10 expiring", base=FURNISHED,
         setup=[["add", "kurczak", "--exp", "17.10", "--where", "lodówka > półka 1"],
                ["add", "jogurt", "--exp", "19.10", "--where", "lodówka > półka 2"],
                ["add", "ryż", "--exp", "2027-03-01", "--where", "kuchnia"]],
         say=["Co mi się przeterminuje w tym tygodniu?"], check=c_p10, golden=[f"{M} expiring --days 7"]),
    dict(id="P11 meal plan", base=FURNISHED,
         setup=[["add", "kurczak", "--exp", "17.10", "--where", "lodówka > półka 1"],
                ["add", "ryż", "--exp", "2027-03-01", "--where", "kuchnia"]],
         say=["Co zrobić jutro na obiad? Chcę wykorzystać to, co się kończy."], check=c_p11, golden=[f"{M} plan"]),
    dict(id="P12 ask for expiry", base=FURNISHED, setup=[],
         say=["Przywiozłem jogurt grecki i postawiłem w lodówce na pierwszej półce.", "Ważny do 22.10."],
         check=c_p12, golden=[f'{M} add "jogurt grecki" --exp 22.10 --where "lodówka > półka 1"']),
    dict(id="P13 unknown place", base=FURNISHED, setup=[],
         say=["Włożyłem ryż do spiżarki."], check=c_p13, golden=[]),
    dict(id="M1 fridge shelves", base=ROOMS, setup=[],
         say=["W kuchni stoi lodówka z trzema półkami i szufladą na warzywa."], check=c_m1,
         golden=[f'{M} map add "Kuchnia > Lodówka > Półka 1"', f'{M} map add "Kuchnia > Lodówka > Półka 2"',
                 f'{M} map add "Kuchnia > Lodówka > Półka 3"', f'{M} map add "Kuchnia > Lodówka > Szuflada na warzywa"']),
    dict(id="M2 dresser", base=ROOMS, setup=[],
         say=["W pokoju Teosia stoi komoda z czterema szufladami."], check=c_m2,
         golden=[f'{M} map add "Pokój Teosia > Komoda > Szuflada {i}"' for i in range(1, 5)]),
    dict(id="M3 wardrobe", base=ROOMS, setup=[],
         say=["W sypialni jest szafa, ma pięć półek."], check=c_m3,
         golden=[f'{M} map add "Sypialnia > Szafa > Półka {i}"' for i in range(1, 6)]),
    dict(id="M4 import outline", base=ROOMS, setup=[],
         say=["W łazience jest szafka pod umywalką z dwiema półkami."], check=c_m4,
         golden=[f"{M} map import - <<'EOF'\nŁazienka\n  Szafka pod umywalką\n    Półka 1\n    Półka 2\nEOF"]),
    dict(id="M5 extend furniture", base=FURNISHED, setup=[],
         say=["Lodówka ma jeszcze półki na drzwiach, dopisz je do mapy."], check=c_m5,
         golden=[f'{M} map add "Kuchnia > Lodówka > Drzwi lodówki"']),
    dict(id="M6 rename", base=TEOS, setup=[],
         say=["Zmień nazwę szafy w pokoju Teosia na Szafa biała."], check=c_m6,
         golden=[f'{M} map rename "pokój Teosia > szafa 1" "Szafa biała"']),
    dict(id="M7 move item", base=TEOS, setup=[["add", "body Teosia", "--cat", "ubrania",
                                                "--where", "pokój Teosia > szafa 1 > półka 2"]],
         say=["Przełożyłem body Teosia do komody, do drugiej szuflady."], check=c_m7,
         golden=[f'{M} move "body Teosia" --where "pokój Teosia > komoda > szuflada 2"']),
    dict(id="M8 remove furniture", base=TEOS, setup=[],
         say=["Wynieśliśmy komodę z pokoju Teosia, usuń ją z mapy."], check=c_m8,
         golden=[f'{M} map rm "pokój Teosia > komoda"']),
    dict(id="M9 list place", base=FURNISHED,
         setup=[["add", "mleko", "--where", "lodówka > półka 1"], ["add", "jogurt", "--where", "lodówka > półka 2"]],
         say=["Co jest w lodówce?"], check=c_m9, golden=[f'{M} list --where lodówka']),
    dict(id="M10 show map", base=TEOS, setup=[],
         say=["Pokaż mapę pokoju Teosia."], check=c_m10, golden=[f'{M} map show "pokój Teosia"']),
]


# ---------------------------------------------------------------- the only "terminal" the model gets

ALLOWED_FEEDERS = {"echo", "printf", "cat"}


def run_dom(argv: list[str], stdin_text: str | None, db: str) -> tuple[int, str]:
    old_stdin = sys.stdin
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return dom.run(["--db", db] + argv)
    except SystemExit as e:  # argparse error
        return 2, f"bad arguments ({e.code}); see `dom --help`"
    finally:
        sys.stdin = old_stdin


def execute(command: str, db: str) -> str:
    """Run one terminal command if it only calls dom.py. Returns what the model sees."""
    command = command.strip()
    heredoc = None
    m = re.search(r"<<-?\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\s*\1\s*$", command, re.S)
    if m:
        heredoc = m.group(2)
        command = command[: m.start()].strip()
    outs = []
    for part in re.split(r"\s*&&\s*|\s*;\s*|\n+", command):
        if not part.strip():
            continue
        stdin_text = heredoc
        segs = [s.strip() for s in re.split(r"(?<![|])\|(?![|])", part)]
        if len(segs) == 2:
            try:
                feed = shlex.split(segs[0])
            except ValueError as e:
                return f"exit=2\nshell parse error: {e}"
            if not feed or feed[0] not in ALLOWED_FEEDERS:
                return "exit=126\nOnly dom.py may be run here."
            stdin_text = " ".join(feed[1:])
            if feed[0] == "printf":
                stdin_text = stdin_text.encode().decode("unicode_escape").encode("latin-1").decode("utf-8", "replace")
            segs = segs[1:]
        if len(segs) != 1:
            return "exit=126\nOnly dom.py may be run here."
        try:
            toks = shlex.split(segs[0])
        except ValueError as e:
            return f"exit=2\nshell parse error: {e}"
        while toks and (toks[0] in ("python3", "python", "-I") or "=" in toks[0] and not toks[0].startswith("-")):
            toks = toks[1:]
        if not toks or not (toks[0].endswith("dom.py") or toks[0] == "dom"):
            return "exit=126\nOnly dom.py may be run here."
        code, out = run_dom(toks[1:], stdin_text, db)
        outs.append(f"exit={code}\n{out}")
        if code != 0:
            break
    return "\n".join(outs) if outs else "exit=0"


TOOL = {"type": "function", "function": {
    "name": "terminal",
    "description": "Run a shell command on Filip's Hermes VM and return its output.",
    "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The command"}},
                   "required": ["command"]}}}


def system_prompt() -> str:
    with open(os.path.join(os.path.dirname(HERE), "SKILL.md"), encoding="utf-8") as fh:
        skill = fh.read()
    return (f"Jesteś Hermes, asystent Filipa. Dziś jest czwartek {TODAY}. Odpowiadaj po polsku, krótko. "
            "Masz narzędzie `terminal`. Załadowany skill:\n\n" + skill)


def chat(url: str, model: str, messages: list, key: str | None, timeout: int) -> dict:
    body = json.dumps({"model": model, "messages": messages, "tools": [TOOL], "tool_choice": "auto",
                       "temperature": 0.7, "top_p": 0.8, "max_tokens": 1024}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {key}"} if key else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def prepare(case, workdir) -> str:
    db = os.path.join(workdir, "dom.db")
    if os.path.exists(db):
        os.remove(db)
    con = dom.connect(db)
    with con:
        dom.import_outline(con, case["base"])
    con.close()
    for argv in case["setup"]:
        code, out = run_dom(argv, None, db)
        assert code == 0, (argv, out)
    return db


def run_case_model(case, args, workdir) -> dict:
    db = prepare(case, workdir)
    messages = [{"role": "system", "content": system_prompt()}]
    calls, final, t0, err = [], "", time.time(), None
    try:
        for user in case["say"]:
            messages.append({"role": "user", "content": user})
            for _ in range(args.max_steps):
                resp = chat(args.url, args.model, messages, args.key, args.timeout)
                msg = resp["choices"][0]["message"]
                tcs = msg.get("tool_calls") or []
                messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
                if not tcs:
                    final = msg.get("content") or ""
                    break
                for tc in tcs:
                    try:
                        cmd = json.loads(tc["function"]["arguments"]).get("command", "")
                    except (json.JSONDecodeError, AttributeError):
                        cmd = ""
                    out = execute(cmd, db)
                    calls.append({"command": cmd, "result": out[:400]})
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": out})
    except Exception as e:  # network/timeouts count as failures
        err = f"{type(e).__name__}: {e}"
    passed, why = case["check"](db, final) if err is None else (False, err)
    return {"case": case["id"], "pass": passed, "why": why, "final": final, "calls": calls,
            "seconds": round(time.time() - t0, 1)}


def run_case_oracle(case, workdir) -> dict:
    db = prepare(case, workdir)
    outs = [execute(cmd, db) for cmd in case["golden"]]
    text = "\n".join(outs)
    if case["id"].startswith("P13"):
        text = "Nie znam spiżarki. Gdzie ona jest?"
    passed, why = case["check"](db, text)
    return {"case": case["id"], "pass": passed, "why": why, "outs": outs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--url", default="http://127.0.0.1:8081")
    ap.add_argument("--model", default="local")
    ap.add_argument("--key", default=os.environ.get("LLAMA_API_KEY"))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--max-steps", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--only", help="comma-separated case id prefixes")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()
    os.environ["DOM_TODAY"] = TODAY
    cases = [c for c in CASES if not args.only or any(c["id"].startswith(p) for p in args.only.split(","))]
    with tempfile.TemporaryDirectory() as wd:
        if args.oracle:
            bad = 0
            for c in cases:
                r = run_case_oracle(c, wd)
                bad += not r["pass"]
                print(("ok  " if r["pass"] else "FAIL") + f" {c['id']}  {r['why']}")
            return 1 if bad else 0
        os.makedirs(args.out, exist_ok=True)
        raw = os.path.join(args.out, "raw.jsonl")
        summary: dict[str, list] = {}
        with open(raw, "a", encoding="utf-8") as fh:
            for run in range(args.runs):
                for c in cases:
                    r = run_case_model(c, args, wd)
                    r["run"] = run
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                    fh.flush()
                    summary.setdefault(c["id"], []).append(r)
                    print(f"run {run} {'ok  ' if r['pass'] else 'FAIL'} {c['id']} {r['seconds']}s  {r['why'][:160]}",
                          flush=True)
    lines = ["| Case | Pass | Avg s | Tool calls (avg) |", "|---|---|---|---|"]
    tot = n = 0
    for cid, rs in summary.items():
        p = sum(r["pass"] for r in rs)
        tot += p
        n += len(rs)
        lines.append(f"| {cid} | {p}/{len(rs)} | {sum(r['seconds'] for r in rs) / len(rs):.1f} | "
                     f"{sum(len(r['calls']) for r in rs) / len(rs):.1f} |")
    lines.append(f"| **Total** | **{tot}/{n}** | | |")
    md = "\n".join(lines)
    with open(os.path.join(args.out, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# home-inventory bench: {args.model} @ {args.url}\n\n{md}\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
