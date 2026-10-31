#!/usr/bin/env python3
"""dom: Hermes home inventory (pantry, household chemicals, anything) + apartment map.

Standard library only. State: SQLite at ~/.hermes/autonomy/home-inventory/dom.db (inside ~/.hermes, so the
nightly backup carries it). Override with DOM_DB. Output for Filip is Polish; --json gives structured data.

Model:
  places  tree: mieszkanie > pokój > mebel > półka/szuflada > pojemnik. Shelves keep their order (pos 1 = top).
  items   catalogue: name, aliases, category, unit, the place where the item usually lives.
  stock   batches of an item: quantity, expiry date, place, sector on the shelf (side + depth), opened date.
  events  append-only log of what happened (added, used, thrown out, moved).

Exit codes: 0 ok, 1 error, 2 bad input (date, sector), 3 nothing found, 4 ambiguous (candidates printed),
5 unknown place, 6 batch: not every line succeeded.
"""
from __future__ import annotations

import argparse
import calendar
import contextlib
import difflib
import io
import json
import os
try:
    import pwd
except ImportError:  # Windows (benches on the laptop)
    pwd = None
import re
import shlex
import shutil
import sqlite3
import sys
import unicodedata
from datetime import date, datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS places (
  id INTEGER PRIMARY KEY,
  parent_id INTEGER REFERENCES places(id),
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'inne',
  pos INTEGER,
  aliases TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  aliases TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'inne',
  unit TEXT NOT NULL DEFAULT 'szt',
  home_place_id INTEGER REFERENCES places(id),
  home_side TEXT,
  home_depth TEXT
);
CREATE TABLE IF NOT EXISTS stock (
  id INTEGER PRIMARY KEY,
  item_id INTEGER NOT NULL REFERENCES items(id),
  qty REAL NOT NULL,
  place_id INTEGER REFERENCES places(id),
  side TEXT,
  depth TEXT,
  expires TEXT,
  opened TEXT,
  note TEXT NOT NULL DEFAULT '',
  added TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'jest'
);
CREATE TABLE IF NOT EXISTS photos (
  place_id INTEGER PRIMARY KEY REFERENCES places(id),
  file TEXT NOT NULL,
  boxes TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  kind TEXT NOT NULL,
  item_id INTEGER,
  stock_id INTEGER,
  qty REAL,
  detail TEXT NOT NULL DEFAULT ''
);
"""

CATEGORIES = ("spożywcze", "chemia", "ubrania", "inne")
FOOD = "spożywcze"

SIDES = {
    "lewo": ("lewo", "lewa", "lewej", "l", "left", "z lewej", "po lewej"),
    "środek": ("środek", "srodek", "środku", "srodku", "pośrodku", "posrodku", "c", "center", "middle", "na środku"),
    "prawo": ("prawo", "prawa", "prawej", "p", "r", "right", "z prawej", "po prawej"),
}
DEPTHS = {
    "przód": ("przód", "przod", "przodu", "z przodu", "front", "f"),
    "środek": ("środek", "srodek", "środku", "srodku", "pośrodku", "posrodku", "middle", "m"),
    "tył": ("tył", "tyl", "tyłu", "tylu", "z tyłu", "z tylu", "back", "b"),
}
SIDE_TXT = {"lewo": "po lewej", "środek": "pośrodku", "prawo": "po prawej"}
DEPTH_TXT = {"przód": "z przodu", "środek": "w środku głębokości", "tył": "z tyłu"}

KIND_WORDS = [
    ("półka", ("półka", "polka", "półki", "polki")),
    ("szuflada", ("szuflada", "szuflady")),
    ("pojemnik", ("pojemnik", "pudełko", "pudelko", "kosz", "koszyk", "skrzynka", "słoik", "sloik", "torba")),
    ("mebel", ("szafa", "szafka", "szafki", "lodówka", "lodowka", "zamrażarka", "zamrazarka", "komoda", "regał",
               "regal", "witryna", "kredens", "biurko", "spiżarka", "spizarka", "spiżarnia", "spizarnia", "pawlacz",
               "nadstawka", "stolik", "łóżko", "lozko", "garderoba", "zabudowa", "szafeczka")),
    ("pokój", ("pokój", "pokoj", "kuchnia", "łazienka", "lazienka", "salon", "sypialnia", "przedpokój",
               "przedpokoj", "korytarz", "balkon", "piwnica", "garaż", "garaz", "toaleta", "wc", "gabinet", "hol",
               "komórka", "komorka", "pralnia")),
]
ORDERED_KINDS = ("półka", "szuflada")

STOP = {"z", "ze", "w", "we", "na", "do", "i", "a", "o", "mam", "mamy", "gdzie", "jest", "są", "sa", "teraz",
        "moj", "moje", "moja", "mój", "ten", "ta", "to", "te", "od", "dla", "po", "the"}

MONTHS = {
    "sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paz": 10,
    "lis": 11, "gru": 12,
}


class DomError(Exception):
    def __init__(self, msg: str, code: int = 1, data=None):
        super().__init__(msg)
        self.code = code
        self.data = data


# ---------------------------------------------------------------- helpers

def today() -> date:  # local time on purpose: expiry dates are calendar days in Filip's home
    fixed = os.environ.get("DOM_TODAY")
    return date.fromisoformat(fixed) if fixed else date.today()  # noqa: DTZ011


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")  # noqa: DTZ005


def fold(text: str) -> str:
    text = text.lower().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", fold(text)) if t not in STOP]


def tok_match(q: str, t: str) -> bool:
    if q == t:
        return True
    if q.isdigit() or t.isdigit():
        return False
    if len(q) >= 4 and len(t) >= 4:
        stem = max(4, min(len(q), len(t)) - 2)
        if q[:stem] == t[:stem]:
            return True
        return difflib.SequenceMatcher(None, q, t).ratio() >= 0.8
    return False


def text_score(query: str, *texts: str) -> float:
    """Share of query tokens found in the texts (Polish inflection tolerant). 0 if any token is missing."""
    q = tokens(query)
    if not q:
        return 0.0
    hay = [t for text in texts for t in tokens(text)]
    hits = sum(1 for qt in q if any(tok_match(qt, t) for t in hay))
    if hits < len(q):
        return 0.0
    exact = sum(1 for qt in q if qt in hay)
    return 1.0 + exact / len(q) - len(hay) / 1000.0


def norm_choice(value: str | None, table: dict, what: str) -> str | None:
    if value is None or value == "":
        return None
    v = value.strip().lower()
    for canon, words in table.items():
        if v == canon or v in words or fold(v) in {fold(w) for w in words}:
            return canon
    raise DomError(f"Nie rozumiem {what}: „{value}”. Dozwolone: {', '.join(table)}.", 2)


def sector_words(text: str) -> tuple[str | None, str | None] | None:
    """'lewo', 'z lewej z przodu', 'prawa tył' -> (side, depth); None if the text is not only sector words."""
    words = fold(text).replace(",", " ").split()
    side = depth = None
    i = 0
    while i < len(words):
        for n in (2, 1):  # "z lewej", "po prawej", "z tyłu" first
            chunk = " ".join(words[i:i + n])
            hit_s = next((c for c, ws in SIDES.items() if chunk in {fold(w) for w in ws if len(w) > 1}), None)
            hit_d = next((c for c, ws in DEPTHS.items() if chunk in {fold(w) for w in ws if len(w) > 1}), None)
            if hit_d and not hit_s or hit_d and side and not depth:
                depth, i = hit_d, i + n
                break
            if hit_s:
                side, i = hit_s, i + n
                break
        else:
            if words[i] in ("strona", "strony", "stronie", "na"):
                i += 1
                continue
            return None
    return (side, depth) if side or depth else None


def split_sector(where: str | None) -> tuple[str | None, str | None, str | None]:
    """Small models write the sector into the path: "szafa 1 > półka 2 > lewo przód". Peel it off."""
    if not where:
        return where, None, None
    segs = split_path(where)
    side = depth = None
    while len(segs) > 1:
        sd = sector_words(segs[-1])
        if not sd:
            break
        side, depth = side or sd[0], depth or sd[1]
        segs.pop()
    return " > ".join(segs), side, depth


CLOTHES = ("body", "skarpet", "spodn", "bluz", "koszul", "sweter", "swetr", "kurtk", "czapk", "rękawicz", "rekawicz",
           "piżam", "pizam", "majt", "bielizn", "legginsy", "sukienk", "kombinezon", "śpiochy", "spiochy", "pajac",
           "rajstop", "szalik", "bucik", "buty", "kapcie", "t-shirt", "podkoszul")


def guess_cat(name: str, expires: str | None) -> str:
    n = fold(name)
    if any(n.startswith(fold(w)) or f" {fold(w)}" in f" {n}" for w in CLOTHES):
        return "ubrania"
    return FOOD if expires else "inne"


def infer_kind(name: str) -> str:
    first = fold(name).split()
    for kind, words in KIND_WORDS:
        if first and any(first[0] == fold(w) for w in words):
            return kind
    for kind, words in KIND_WORDS:
        if any(fold(w) in first for w in words):
            return kind
    return "inne"


def parse_date(text: str | None) -> str | None:
    """Expiry date in Polish or ISO form -> 'YYYY-MM-DD'. A month without a day means its last day."""
    if text is None or str(text).strip() == "":
        return None
    raw = str(text).strip()
    s = fold(raw).strip(" .")
    s = re.sub(r"^(?:wazn\w*|termin|przydatn\w*)\s+", "", s)
    s = re.sub(r"^(?:do|na|przez)\s+", "", s)  # "do jutra", "do 20.10", "na 5 dni"
    t = today()
    if s in ("brak", "bez", "-", "nie ma", "none"):
        return None
    if s in ("dzis", "dzisiaj", "dzisiaj wlacznie", "dzisiejszego"):
        return t.isoformat()
    if s in ("jutro", "jutra", "jutrzejszego"):
        return (t + timedelta(days=1)).isoformat()
    if s in ("pojutrze", "pojutrza"):
        return (t + timedelta(days=2)).isoformat()
    m = re.fullmatch(r"(?:za\s+)?(\d+|tydzien|miesiac|rok)\s*(dni|dzien|dnia|tydzien|tygodnie|tygodni|tyg|"
                     r"miesiac|miesiace|miesiecy|mies|rok|lata|lat)?", s)
    if m and (m.group(2) or not m.group(1).isdigit()):
        word = m.group(1)
        n = 1 if not word.isdigit() else int(word)
        unit = m.group(2) or word
        if unit.startswith(("dzie", "dni")):
            return (t + timedelta(days=n)).isoformat()
        if unit.startswith(("tyg", "tydz")):
            return (t + timedelta(weeks=n)).isoformat()
        if unit.startswith("mies"):
            return add_months(t, n).isoformat()
        return add_months(t, 12 * n).isoformat()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)), raw)
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), m.group(3)
        if y is not None:
            year = int(y) + (2000 if len(y) == 2 else 0)
            return safe_date(year, b, a, raw)
        return roll_year(a, b, raw)
    m = re.fullmatch(r"(\d{1,2})[./-](\d{4})", s)
    if m:
        year, month = int(m.group(2)), int(m.group(1))
        return safe_date(year, month, last_day(year, month), raw)
    m = re.fullmatch(r"(?:koniec\s+|do\s+konca\s+)?(\d{1,2})?\s*([a-z]+)\s*(\d{4})?", s)
    if m and m.group(2)[:3] in MONTHS:
        month = MONTHS[m.group(2)[:3]]
        day = int(m.group(1)) if m.group(1) else None
        if m.group(3):
            year = int(m.group(3))
            return safe_date(year, month, day or last_day(year, month), raw)
        return roll_year(day or last_day(t.year, month), month, raw)
    raise DomError(f"Nie rozumiem daty „{raw}”. Podaj np. 2026-10-20, 20.10, 20.10.2026, 10.2026, "
                   "„20 października”, „za 5 dni”, „jutro”.", 2)


def last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, last_day(year, month)))


def safe_date(y: int, m: int, d: int, raw: str) -> str:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        raise DomError(f"Nie ma takiej daty: „{raw}”.", 2) from None


def roll_year(day: int, month: int, raw: str) -> str:
    t = today()
    iso = safe_date(t.year, month, day, raw)
    if date.fromisoformat(iso) < t - timedelta(days=30):
        iso = safe_date(t.year + 1, month, day, raw)
    return iso


def fmt_qty(q: float) -> str:
    return str(int(q)) if float(q).is_integer() else f"{q:g}".replace(".", ",")


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "bez terminu"
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def days_left_txt(iso: str | None) -> str:
    if not iso:
        return ""
    n = (date.fromisoformat(iso) - today()).days
    if n < 0:
        return f"przeterminowane {-n} {'dzień' if n == -1 else 'dni'} temu"
    if n == 0:
        return "termin mija dziś"
    if n == 1:
        return "termin mija jutro"
    return f"zostało {n} dni"


# ---------------------------------------------------------------- storage

def db_path() -> str:
    env = os.environ.get("DOM_DB")
    if env:
        return env
    # workers run with a fake $HOME; use the real one from passwd
    home = pwd.getpwuid(os.getuid()).pw_dir if pwd else os.path.expanduser("~")
    return os.path.join(home, ".hermes", "autonomy", "home-inventory", "dom.db")


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or db_path()
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def log(con, kind: str, item_id=None, stock_id=None, qty=None, detail: str = "") -> None:
    con.execute("INSERT INTO events(at, kind, item_id, stock_id, qty, detail) VALUES (?,?,?,?,?,?)",
                (now_iso(), kind, item_id, stock_id, qty, detail))


# ---------------------------------------------------------------- places

def place_rows(con) -> dict[int, sqlite3.Row]:
    return {r["id"]: r for r in con.execute("SELECT * FROM places")}


def ancestry(places: dict, pid: int | None) -> list[sqlite3.Row]:
    chain = []
    while pid is not None and pid in places:
        chain.append(places[pid])
        pid = places[pid]["parent_id"]
    return list(reversed(chain))


def siblings(places: dict, row) -> list:
    return sorted((p for p in places.values() if p["parent_id"] == row["parent_id"] and p["kind"] == row["kind"]
                   and p["pos"] is not None), key=lambda p: p["pos"])


def place_label(places: dict, row) -> str:
    label = row["name"]
    if row["kind"] in ORDERED_KINDS and row["pos"] is not None:
        sib = siblings(places, row)
        n = len(sib)
        if n > 1 and not re.search(r"(od gory|od dolu)", fold(label)):
            from_bottom = n - row["pos"] + 1
            word = "półka" if row["kind"] == "półka" else "szuflada"
            label = f"{label} ({row['pos']}. {word} od góry, {from_bottom}. od dołu)"
    return label


def place_path(places: dict, pid: int | None, pretty: bool = True) -> str:
    if pid is None:
        return "nieznane miejsce"
    chain = ancestry(places, pid)
    if pretty and len(chain) > 1 and chain[0]["parent_id"] is None and chain[0]["kind"] == "mieszkanie":
        chain = chain[1:]
    parts = [place_label(places, r) if pretty else r["name"] for r in chain]
    return " → ".join(parts) if pretty else " > ".join(parts)


def split_path(path: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s*(?:>|/|→|\\)\s*", path) if p.strip()]


def seg_match(places: dict, row, seg: str) -> float:
    s = fold(seg)
    if fold(row["name"]) == s or s in [fold(a) for a in row["aliases"].split(",") if a.strip()]:
        return 3.0
    sc = text_score(seg, row["name"], row["aliases"])
    if sc == 0 and row["kind"] in ORDERED_KINDS and row["pos"] is not None:
        # "półka 2", "druga półka", "2 od góry" -> the shelf with that position
        nums = re.findall(r"\d+", s)
        if nums and infer_kind(seg) in (row["kind"], "inne") and int(nums[0]) == row["pos"] and "dol" not in s:
            return 1.5
        if nums and "dol" in s:
            sib = siblings(places, row)
            if len(sib) - row["pos"] + 1 == int(nums[0]):
                return 1.5
    if sc and len(tokens(seg)) < len(tokens(row["name"])) and re.search(r"\d", row["name"]) \
            and not re.search(r"\d", seg):
        sc *= 0.5  # "szafa" alone should not silently pick "Szafa 2"
    return sc


PCODE = re.compile(r"\[?\bP(\d+)\]?(?!\w)")


def place_code(text: str, places: dict) -> int | None:
    """A scanned label carries "[P12]": that is place 12, whatever the rest of the text says."""
    m = PCODE.search(text or "")
    if m and int(m.group(1)) in places:
        return int(m.group(1))
    return None


def resolve_place(con, path: str, places: dict | None = None) -> int:
    places = places or place_rows(con)
    code = place_code(path, places)
    if code is not None:
        return code
    segs = split_path(path)
    if not segs:
        raise DomError("Puste miejsce.", 5)
    # each candidate: a place whose ancestry contains the segments in order, the last one matching the place
    cands = []
    for row in places.values():
        chain = ancestry(places, row["id"])
        score, ci = 0.0, len(chain) - 1
        last = seg_match(places, row, segs[-1])
        if not last:
            continue
        score += last
        ok = True
        for seg in reversed(segs[:-1]):
            ci -= 1
            found = False
            while ci >= 0:
                sm = seg_match(places, chain[ci], seg)
                if sm:
                    score += sm
                    found = True
                    break
                ci -= 1
            if not found:
                ok = False
                break
        if ok:
            cands.append((score, row["id"]))
    if not cands:
        raise DomError(f"Nie znam miejsca „{path}”. NIC nie zapisano. Zapytaj Filipa, gdzie jest „{segs[-1]}” "
                       "(w którym pokoju, jaki to mebel), potem dodaj je przez map add i powtórz.", 5)
    cands.sort(reverse=True)
    best = [c for c in cands if c[0] == cands[0][0]]
    if len(best) > 1:
        opts = [place_path(places, pid) for _, pid in best]
        raise DomError("Kilka miejsc pasuje: " + "; ".join(opts) + ". Podaj dokładniej (np. pokój > mebel > półka).",
                       4, opts)
    return best[0][1]


def ensure_root(con) -> int:
    row = con.execute("SELECT id FROM places WHERE parent_id IS NULL AND kind='mieszkanie'").fetchone()
    if row:
        return row["id"]
    cur = con.execute("INSERT INTO places(parent_id, name, kind) VALUES (NULL, 'Mieszkanie', 'mieszkanie')")
    return cur.lastrowid


def add_place_path(con, path: str, kind: str | None = None, aliases: str = "", note: str = "",
                   pos: int | None = None) -> tuple[int, list[str]]:
    """Create every missing segment of 'Pokój > Mebel > Półka'. Returns (id, created names)."""
    parent = ensure_root(con)
    created = []
    segs = split_path(path)
    if segs and fold(segs[0]) in ("mieszkanie", "dom"):
        segs = segs[1:]
    for i, seg in enumerate(segs):
        last = i == len(segs) - 1
        row = None
        for r in con.execute("SELECT * FROM places WHERE parent_id=?", (parent,)):
            if fold(r["name"]) == fold(seg) or fold(seg) in [fold(a) for a in r["aliases"].split(",") if a.strip()]:
                row = r
                break
        if row is None:
            k = (kind if last and kind else None) or infer_kind(seg)
            p = pos if last and pos is not None else None
            if p is None and k in ORDERED_KINDS:
                m = re.search(r"(\d+)", seg)
                if m:
                    p = int(m.group(1))
                else:
                    mx = con.execute("SELECT MAX(pos) FROM places WHERE parent_id=? AND kind=?", (parent, k)).fetchone()[0]
                    p = (mx or 0) + 1
            cur = con.execute("INSERT INTO places(parent_id, name, kind, pos, aliases, note) VALUES (?,?,?,?,?,?)",
                              (parent, seg, k, p, aliases if last else "", note if last else ""))
            parent = cur.lastrowid
            created.append(seg)
        else:
            parent = row["id"]
            if last and (aliases or note or kind):
                con.execute("UPDATE places SET aliases=COALESCE(NULLIF(?,''),aliases), note=COALESCE(NULLIF(?,''),note),"
                            " kind=COALESCE(?,kind) WHERE id=?", (aliases, note, kind, parent))
    return parent, created


def import_outline(con, text: str) -> int:
    """Indented outline -> places. Line: 'Name [| aliases, ...] [# note]'. Indent with spaces or tabs.
    Shelves and drawers are numbered top to bottom in the order they are listed."""
    root = ensure_root(con)
    stack: list[tuple[int, int]] = [(-1, root)]
    created = 0
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith(("#", "//")):
            continue
        line = raw.replace("\t", "    ")
        indent = len(line) - len(line.lstrip(" -*"))
        body = line.strip().lstrip("-* ").strip()
        note = ""
        if " #" in body:
            body, note = body.split(" #", 1)
        aliases = ""
        if "|" in body:
            body, aliases = body.split("|", 1)
        name = body.strip()
        if fold(name) in ("mieszkanie", "dom") and len(stack) == 1:
            stack.append((indent, root))
            continue
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        existing = con.execute("SELECT id FROM places WHERE parent_id=? AND name=?", (parent, name)).fetchone()
        if existing:
            pid = existing["id"]
            if aliases.strip() or note.strip():
                con.execute("UPDATE places SET aliases=?, note=? WHERE id=?",
                            (",".join(a.strip() for a in aliases.split(",") if a.strip()), note.strip(), pid))
        else:
            kind = infer_kind(name)
            pos = None
            if kind in ORDERED_KINDS:
                mx = con.execute("SELECT MAX(pos) FROM places WHERE parent_id=? AND kind=?", (parent, kind)).fetchone()[0]
                pos = (mx or 0) + 1
            pid = con.execute("INSERT INTO places(parent_id, name, kind, pos, aliases, note) VALUES (?,?,?,?,?,?)",
                              (parent, name, kind, pos, ",".join(a.strip() for a in aliases.split(",") if a.strip()),
                               note.strip())).lastrowid
            created += 1
        stack.append((indent, pid))
    return created


def subtree_ids(places: dict, pid: int) -> set[int]:
    out, todo = set(), [pid]
    while todo:
        cur = todo.pop()
        out.add(cur)
        todo.extend(p["id"] for p in places.values() if p["parent_id"] == cur)
    return out


# ---------------------------------------------------------------- items and stock

def find_item(con, name: str) -> sqlite3.Row | None:
    for r in con.execute("SELECT * FROM items"):
        if fold(r["name"]) == fold(name) or fold(name) in [fold(a) for a in r["aliases"].split(",") if a.strip()]:
            return r
    return None


def get_or_create_item(con, name: str, category: str | None, unit: str | None, aliases: str = "") -> sqlite3.Row:
    row = find_item(con, name)
    if row is None:
        con.execute("INSERT INTO items(name, aliases, category, unit) VALUES (?,?,?,?)",
                    (name.strip(), aliases, category or "inne", unit or "szt"))
        row = find_item(con, name)
    else:
        if category and category != row["category"]:
            con.execute("UPDATE items SET category=? WHERE id=?", (category, row["id"]))
        if aliases:
            merged = sorted({a.strip() for a in (row["aliases"] + "," + aliases).split(",") if a.strip()})
            con.execute("UPDATE items SET aliases=? WHERE id=?", (",".join(merged), row["id"]))
        row = find_item(con, name)
    return row


STOCK_SQL = """SELECT s.*, i.name, i.aliases, i.category, i.unit
               FROM stock s JOIN items i ON i.id = s.item_id WHERE s.status = 'jest'"""


def batch_dict(places: dict, r) -> dict:
    return {
        "id": r["id"], "item": r["name"], "category": r["category"], "qty": r["qty"], "unit": r["unit"],
        "expires": r["expires"], "days_left": (date.fromisoformat(r["expires"]) - today()).days if r["expires"] else None,
        "opened": r["opened"], "place": place_path(places, r["place_id"]), "side": r["side"], "depth": r["depth"],
        "note": r["note"],
    }


def batch_line(places: dict, r, with_place: bool = True) -> str:
    out = f"{r['name']}: {fmt_qty(r['qty'])} {r['unit']}"
    if r["expires"]:
        out += f", ważne do {fmt_date(r['expires'])} ({days_left_txt(r['expires'])})"
    if r["opened"]:
        out += f", otwarte {fmt_date(r['opened'])}"
    if with_place:
        out += f" — {where_txt(places, r)}"
    if r["note"]:
        out += f" [{r['note']}]"
    return out + f"  #{r['id']}"


def where_txt(places: dict, r) -> str:
    parts = [place_path(places, r["place_id"])]
    sector = ", ".join(x for x in (SIDE_TXT.get(r["side"] or ""), DEPTH_TXT.get(r["depth"] or "")) if x)
    if sector:
        parts.append(sector)
    return ", ".join(parts)


def search_stock(con, query: str) -> list:
    if query.startswith("#") and query[1:].isdigit():
        rows = con.execute(STOCK_SQL + " AND s.id=?", (int(query[1:]),)).fetchall()
        return rows
    scored = []
    for r in con.execute(STOCK_SQL):
        sc = text_score(query, r["name"], r["aliases"], r["note"])
        if sc:
            scored.append((sc, r))
    if not scored:
        return []
    top = max(s for s, _ in scored)
    rows = [r for s, r in scored if s >= top - 0.34]
    rows.sort(key=lambda r: (r["name"], r["expires"] or "9999", r["id"]))
    return rows


def pick_batches(rows: list, query: str) -> list:
    """For use/throw/move: all rows must be the same item; earliest expiry first (FEFO)."""
    names = sorted({r["name"] for r in rows})
    if len(names) > 1:
        exact = [r for r in rows if fold(r["name"]) == fold(query)]
        if exact:
            rows = exact
        else:
            raise DomError("Kilka rzeczy pasuje: " + ", ".join(names) + ". Powiedz, o którą chodzi (albo podaj #id).",
                           4, names)
    return sorted(rows, key=lambda r: (r["expires"] or "9999-12-31", r["added"]))


# ---------------------------------------------------------------- commands

COUNT_SEG = re.compile(r"^(?:z\s+)?(\d+)?\s*(półk\w*|polk\w*|szuflad\w*)(?:\s+(\d+))?$")


def peel_count(a) -> str:
    """"Szafa > 3 półki" / "Komoda > szuflady" as the last segment means --shelves/--drawers, not a place."""
    segs = split_path(a.path)
    inline = re.match(r"^(.+?)\s+(?:z|ze|na)\s+(\d+\s*(?:półk|polk|szuflad)\w*)$", segs[-1], re.I)
    if inline:  # "Szafa z 3 półkami"
        segs[-1:] = [inline.group(1), inline.group(2)]
    m = COUNT_SEG.match(segs[-1].strip().lower()) if len(segs) > 1 else None
    if not m:
        return a.path
    kind = fold(m.group(2))
    if m.group(3) and kind in ("polka", "szuflada"):  # "Półka 3" is one shelf, "półki 3" means three
        return a.path
    num = m.group(1) or m.group(3)
    n = int(num) if num else None
    if kind.startswith("polk"):
        a.shelves = a.shelves or n
        if not a.shelves:
            raise DomError("Ile półek? Użyj --shelves N.", 2)
    else:
        a.drawers = a.drawers or n
        if not a.drawers:
            raise DomError("Ile szuflad? Użyj --drawers N.", 2)
    return " > ".join(segs[:-1])


def cmd_map(con, a) -> tuple[str, object]:
    places = place_rows(con)
    if a.map_cmd == "add":
        a.path = peel_count(a)
        pid, created = add_place_path(con, a.path, a.kind, a.alias or "", a.note or "", a.pos)
        # "szafa z 5 półkami" in one call: small models stop half way through long call sequences
        for word, n in (("Półka", a.shelves), ("Szuflada", a.drawers)):
            for i in range(1, (n or 0) + 1):
                _, sub = add_place_path(con, f"{place_path(place_rows(con), pid, pretty=False)} > {word} {i}")
                created += sub
        places = place_rows(con)
        inside = [place_label(places, r) for r in sorted(
            (r for r in places.values() if r["parent_id"] == pid),
            key=lambda r: (r["pos"] if r["pos"] is not None else 10**6, r["name"]))]
        msg = (f"Dodałem: {', '.join(created)}. " if created else "To miejsce już było. ") + \
              f"Ścieżka: {place_path(places, pid)}" + (f". W środku ({len(inside)}): {'; '.join(inside)}" if inside else "")
        return msg, {"id": pid, "created": created, "path": place_path(places, pid), "inside": inside}
    if a.map_cmd == "import":
        if a.file == "-":
            text = sys.stdin.read()
        else:
            with open(a.file, encoding="utf-8") as fh:
                text = fh.read()
        n = import_outline(con, text)
        return f"Zaimportowałem mapę: {n} nowych miejsc.", {"created": n}
    if a.map_cmd == "show":
        root = resolve_place(con, a.path, places) if a.path else None
        counts: dict[int, int] = {}
        for r in con.execute("SELECT place_id, COUNT(*) c FROM stock WHERE status='jest' GROUP BY place_id"):
            counts[r["place_id"]] = r["c"]
        lines, data = [], []

        def walk(pid, depth):
            row = places[pid]
            sub = [p for p in places.values() if p["parent_id"] == pid]
            sub.sort(key=lambda p: (p["pos"] if p["pos"] is not None else 10**6, p["name"]))
            extra = []
            if row["aliases"]:
                extra.append("aka " + row["aliases"])
            if counts.get(pid):
                extra.append(f"{counts[pid]} poz.")
            if row["note"]:
                extra.append(row["note"])
            label = place_label(places, row) if row["kind"] in ORDERED_KINDS else row["name"]
            lines.append("  " * depth + label + (f"  ({'; '.join(extra)})" if extra else ""))
            data.append({"id": pid, "depth": depth, "name": row["name"], "kind": row["kind"], "pos": row["pos"],
                         "items": counts.get(pid, 0)})
            for s in sub:
                walk(s["id"], depth + 1)

        starts = [root] if root else sorted(p["id"] for p in places.values() if p["parent_id"] is None)
        for s in starts:
            walk(s, 0)
        if not lines:
            return ("Mapa mieszkania jest pusta. Dodaj pokoje: dom map add \"Kuchnia > Lodówka > Półka 1\" "
                    "albo dom map import mapa.txt"), []
        return "\n".join(lines), data
    if a.map_cmd == "rm":
        pid = resolve_place(con, a.path, places)
        ids = subtree_ids(places, pid)
        used = con.execute(f"SELECT COUNT(*) FROM stock WHERE status='jest' AND place_id IN ({','.join('?' * len(ids))})",
                           tuple(ids)).fetchone()[0]
        if used:
            raise DomError(f"W tym miejscu leżą jeszcze rzeczy ({used} poz.). Najpierw je przenieś: dom move.", 1)
        label = place_path(places, pid)
        con.execute(f"UPDATE items SET home_place_id=NULL WHERE home_place_id IN ({','.join('?' * len(ids))})", tuple(ids))
        con.execute(f"DELETE FROM places WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
        return f"Usunąłem z mapy: {label}.", {"removed": len(ids)}
    if a.map_cmd == "rename":
        pid = resolve_place(con, a.path, places)
        con.execute("UPDATE places SET name=? WHERE id=?", (a.new_name, pid))
        return f"Zmieniłem nazwę na: {place_path(place_rows(con), pid)}", {"id": pid}
    raise DomError("Nieznane polecenie map.")


def cmd_add(con, a) -> tuple[str, object]:
    cat = a.cat
    if cat:
        cat = {"spozywcze": "spożywcze", "jedzenie": "spożywcze", "chemia": "chemia", "ubrania": "ubrania"}.get(fold(cat), cat)
        if cat not in CATEGORIES:
            raise DomError(f"Kategoria: {', '.join(CATEGORIES)}.", 2)
    expires = parse_date(a.exp)
    if cat is None and find_item(con, a.name) is None:
        cat = guess_cat(a.name, expires)
    item = get_or_create_item(con, a.name, cat, a.unit, a.alias or "")
    a.where, w_side, w_depth = split_sector(a.where)
    side = norm_choice(a.side, SIDES, "strony") or w_side
    depth = norm_choice(a.depth, DEPTHS, "głębokości") or w_depth
    places = place_rows(con)
    if a.where:
        pid = resolve_place(con, a.where, places)
    else:
        pid = item["home_place_id"]
        side = side or item["home_side"]
        depth = depth or item["home_depth"]
    cur = con.execute("INSERT INTO stock(item_id, qty, place_id, side, depth, expires, note, added) VALUES (?,?,?,?,?,?,?,?)",
                      (item["id"], a.qty, pid, side, depth, expires, a.note or "", now_iso()))
    if pid is not None and (a.where or item["home_place_id"] is None):
        con.execute("UPDATE items SET home_place_id=?, home_side=?, home_depth=? WHERE id=?",
                    (pid, side, depth, item["id"]))
    log(con, "dodano", item["id"], cur.lastrowid, a.qty, a.note or "")
    row = con.execute(STOCK_SQL + " AND s.id=?", (cur.lastrowid,)).fetchone()
    msg = "Zapisałem. " + batch_line(places, row)
    if pid is None:
        msg += "\nNie wiem, gdzie to leży: dopytaj Filipa i zapisz przez dom move."
    return msg, batch_dict(places, row)


def cmd_where(con, a) -> tuple[str, object]:
    places = place_rows(con)
    if place_code(a.query, places) is not None:  # a scanned label: what is in this box / on this shelf
        a.where, a.cat = a.query, None
        return cmd_list(con, a)
    rows = search_stock(con, a.query)
    if not rows:
        try:  # "co jest na półce 2 w lodówce": the query names a place, not a thing
            resolve_place(con, a.query, places)
        except DomError:
            pass
        else:
            a.where, a.cat = a.query, None
            return cmd_list(con, a)
        item = None
        for r in con.execute("SELECT * FROM items"):
            if text_score(a.query, r["name"], r["aliases"]):
                item = r
                break
        if item is not None:
            home = place_path(places, item["home_place_id"]) if item["home_place_id"] else None
            msg = f"„{item['name']}” — w domu nie ma (wszystko zużyte)."
            if home:
                msg += f" Zwykle leży: {home}."
            raise DomError(msg, 3, {"item": item["name"], "home": home})
        raise DomError(f"Nie mam w spisie niczego pasującego do „{a.query}”.", 3)
    return "\n".join(batch_line(places, r) for r in rows), [batch_dict(places, r) for r in rows]


def cmd_list(con, a) -> tuple[str, object]:
    places = place_rows(con)
    sql, params = STOCK_SQL, []
    if a.cat:
        sql += " AND i.category=?"
        params.append({"spozywcze": "spożywcze"}.get(fold(a.cat), a.cat))
    rows = con.execute(sql, params).fetchall()
    if a.where:
        ids = subtree_ids(places, resolve_place(con, a.where, places))
        rows = [r for r in rows if r["place_id"] in ids]
    if not rows:
        return "Nic tu nie ma w spisie.", []
    rows.sort(key=lambda r: (place_path(places, r["place_id"]), r["name"]))
    if a.where:
        lines, cur = [], None
        for r in rows:
            p = where_txt(places, r)
            if p != cur:
                lines.append(p + ":")
                cur = p
            lines.append("  " + batch_line(places, r, with_place=False))
        return "\n".join(lines), [batch_dict(places, r) for r in rows]
    return "\n".join(batch_line(places, r) for r in rows), [batch_dict(places, r) for r in rows]


def consume(con, a, status: str) -> tuple[str, object]:
    rows = search_stock(con, a.query)
    if not rows:
        raise DomError(f"Nie mam w spisie niczego pasującego do „{a.query}”.", 3)
    rows = pick_batches(rows, a.query)
    if status == "wyrzucone" and a.expired_only:
        rows = [r for r in rows if r["expires"] and r["expires"] < today().isoformat()]
        if not rows:
            raise DomError("Nic z tego nie jest przeterminowane.", 3)
    left = None if a.all else (a.qty if a.qty is not None else 1.0)
    done = []
    for r in rows:
        if left is not None and left <= 0:
            break
        take = r["qty"] if left is None else min(left, r["qty"])
        rest = r["qty"] - take
        if rest <= 1e-9:
            con.execute("UPDATE stock SET qty=0, status=? WHERE id=?", (status, r["id"]))
        else:
            con.execute("UPDATE stock SET qty=? WHERE id=?", (rest, r["id"]))
        log(con, "zużyto" if status == "zużyte" else "wyrzucono", r["item_id"], r["id"], take)
        done.append((r, take))
        if left is not None:
            left -= take
    name, unit = rows[0]["name"], rows[0]["unit"]
    total = sum(t for _, t in done)
    remaining = con.execute("SELECT COALESCE(SUM(qty),0) FROM stock WHERE status='jest' AND item_id=?",
                            (rows[0]["item_id"],)).fetchone()[0]
    verb = "Zużyte" if status == "zużyte" else "Wyrzucone"
    msg = f"{verb}: {name} {fmt_qty(total)} {unit}."
    if left and left > 1e-9:
        msg += f" (W spisie było tylko {fmt_qty(total)}.)"
    if remaining > 0:
        msg += f" Zostało {fmt_qty(remaining)} {unit}."
    else:
        msg += " To była ostatnia sztuka — dopisać do listy zakupów?"
    return msg, {"item": name, "taken": total, "remaining": remaining, "last": remaining <= 0}


def cmd_move(con, a) -> tuple[str, object]:
    places = place_rows(con)
    rows = search_stock(con, a.query)
    if not rows:
        raise DomError(f"Nie mam w spisie niczego pasującego do „{a.query}”.", 3)
    rows = pick_batches(rows, a.query)
    a.where, w_side, w_depth = split_sector(a.where)
    pid = resolve_place(con, a.where, places) if a.where else None
    side = norm_choice(a.side, SIDES, "strony") or w_side
    depth = norm_choice(a.depth, DEPTHS, "głębokości") or w_depth
    if pid is None and side is None and depth is None:
        raise DomError("Podaj --where i/lub --side/--depth.", 2)
    for r in rows:
        con.execute("UPDATE stock SET place_id=COALESCE(?,place_id), side=COALESCE(?,side), depth=COALESCE(?,depth) "
                    "WHERE id=?", (pid, side, depth, r["id"]))
        log(con, "przeniesiono", r["item_id"], r["id"], None, a.where or "")
    r0 = con.execute(STOCK_SQL + " AND s.id=?", (rows[0]["id"],)).fetchone()
    if not a.keep_home:
        con.execute("UPDATE items SET home_place_id=?, home_side=?, home_depth=? WHERE id=?",
                    (r0["place_id"], r0["side"], r0["depth"], r0["item_id"]))
    return f"Przeniosłem {r0['name']} (partii: {len(rows)}): {where_txt(place_rows(con), r0)}.", batch_dict(places, r0)


def merge_tags(note: str, tags: list[str]) -> str:
    """Set `klucz:wartość` attributes in a note (clothes: "typ:płaszcz ciepło:4 stan:czyste"), keep other text."""
    words = note.split()
    for tag in tags:
        for t in tag.split():
            key, sep, _ = t.partition(":")
            if not sep or not key:
                raise DomError(f"--tag wymaga klucz:wartość, np. stan:pranie (dostałem „{t}”).", 2)
            idx = [i for i, w in enumerate(words) if w.split(":", 1)[0] == key and ":" in w]
            if idx:
                words[idx[0]] = t
            else:
                words.append(t)
    return " ".join(words)


def cmd_set(con, a) -> tuple[str, object]:
    places = place_rows(con)
    rows = search_stock(con, a.query)
    if not rows:
        raise DomError(f"Nie mam w spisie niczego pasującego do „{a.query}”.", 3)
    rows = pick_batches(rows, a.query)
    r = rows[0]
    if a.exp is not None:
        con.execute("UPDATE stock SET expires=? WHERE id=?", (parse_date(a.exp), r["id"]))
    if a.qty is not None:
        con.execute("UPDATE stock SET qty=? WHERE id=?", (a.qty, r["id"]))
    if a.note is not None:
        con.execute("UPDATE stock SET note=? WHERE id=?", (a.note, r["id"]))
    if a.tag:
        note = con.execute("SELECT note FROM stock WHERE id=?", (r["id"],)).fetchone()["note"] or ""
        con.execute("UPDATE stock SET note=? WHERE id=?", (merge_tags(note, a.tag), r["id"]))
    if a.opened is not None:
        opened = parse_date(a.opened) if a.opened else today().isoformat()
        con.execute("UPDATE stock SET opened=? WHERE id=?", (opened, r["id"]))
        if a.days_after_opening:
            limit = (date.fromisoformat(opened) + timedelta(days=a.days_after_opening)).isoformat()
            cur = con.execute("SELECT expires FROM stock WHERE id=?", (r["id"],)).fetchone()["expires"]
            if not cur or limit < cur:
                con.execute("UPDATE stock SET expires=? WHERE id=?", (limit, r["id"]))
    if a.alias:
        get_or_create_item(con, r["name"], None, None, a.alias)
    log(con, "zmieniono", r["item_id"], r["id"])
    r = con.execute(STOCK_SQL + " AND s.id=?", (r["id"],)).fetchone()
    return "Zmienione. " + batch_line(places, r), batch_dict(places, r)


def expiring_rows(con, days: int, cat: str | None):
    limit = (today() + timedelta(days=days)).isoformat()
    sql = STOCK_SQL + " AND s.expires IS NOT NULL AND s.expires <= ?"
    params: list = [limit]
    if cat:
        sql += " AND i.category=?"
        params.append(cat)
    return sorted(con.execute(sql, params).fetchall(), key=lambda r: (r["expires"], r["name"]))


def cmd_expiring(con, a) -> tuple[str, object]:
    places = place_rows(con)
    rows = expiring_rows(con, a.days, a.cat)
    if not rows:
        return f"Nic nie traci terminu w ciągu {a.days} dni.", []
    return "\n".join(batch_line(places, r) for r in rows), [batch_dict(places, r) for r in rows]


def cmd_plan(con, a) -> tuple[str, object]:
    """Meal-planning hints: food to use first, with where it is."""
    places = place_rows(con)
    rows = expiring_rows(con, a.days, FOOD)
    t = today().isoformat()
    expired = [r for r in rows if r["expires"] < t]
    soon = [r for r in rows if r["expires"] >= t]
    opened = con.execute(STOCK_SQL + " AND i.category=? AND s.opened IS NOT NULL", (FOOD,)).fetchall()
    opened = [r for r in opened if r["id"] not in {x["id"] for x in rows}]
    lines = []
    if soon:
        lines.append(f"Warto uwzględnić w posiłkach (termin w ciągu {a.days} dni):")
        lines += ["  " + batch_line(places, r) for r in soon]
    if opened:
        lines.append("Otwarte, zużyć w pierwszej kolejności:")
        lines += ["  " + batch_line(places, r) for r in opened]
    if expired:
        lines.append("Już po terminie (sprawdź, czy nadaje się do zjedzenia, albo wyrzuć):")
        lines += ["  " + batch_line(places, r) for r in expired]
    if not lines:
        lines.append(f"Nic spożywczego nie traci terminu w ciągu {a.days} dni.")
    data = {"soon": [batch_dict(places, r) for r in soon], "opened": [batch_dict(places, r) for r in opened],
            "expired": [batch_dict(places, r) for r in expired]}
    return "\n".join(lines), data


def cmd_remind(con, a) -> tuple[str, object]:
    """For a no-agent cron job: prints nothing when there is nothing to say."""
    places = place_rows(con)
    rows = expiring_rows(con, a.days, None)
    if not rows:
        return "", []
    head = "🧺 Spiżarnia: kończy się termin" if any(r["expires"] >= today().isoformat() for r in rows) \
        else "🧺 Spiżarnia: po terminie"
    return head + "\n" + "\n".join("• " + batch_line(places, r) for r in rows), [batch_dict(places, r) for r in rows]


def cmd_history(con, a) -> tuple[str, object]:
    sql = "SELECT e.*, i.name FROM events e LEFT JOIN items i ON i.id=e.item_id ORDER BY e.id DESC LIMIT ?"
    rows = con.execute(sql, (a.limit * 5 if a.query else a.limit,)).fetchall()
    if a.query:
        rows = [r for r in rows if r["name"] and text_score(a.query, r["name"])][: a.limit]
    if not rows:
        return "Brak historii.", []
    lines = [f"{r['at'][:16].replace('T', ' ')}  {r['kind']}  {r['name'] or ''}"
             + (f" {fmt_qty(r['qty'])}" if r["qty"] else "") + (f"  ({r['detail']})" if r["detail"] else "")
             for r in rows]
    return "\n".join(lines), [dict(r) for r in rows]


def verify(con, a, data) -> str | None:
    """Read back what a write claims to have done. Returns a problem or None."""
    if a.cmd == "add" and isinstance(data, dict):
        row = con.execute(STOCK_SQL + " AND s.id=?", (data.get("id"),)).fetchone()
        if row is None:
            return "partii nie ma w bazie"
        if abs(row["qty"] - a.qty) > 1e-9:
            return f"ilość {row['qty']} zamiast {a.qty}"
        if a.exp and row["expires"] != parse_date(a.exp):
            return f"termin {row['expires']} zamiast {parse_date(a.exp)}"
    if a.cmd == "map" and a.map_cmd == "add" and isinstance(data, dict):
        want = (a.shelves or 0) + (a.drawers or 0)
        if want and len(data.get("inside", [])) < want:
            return f"w środku {len(data.get('inside', []))} zamiast {want}"
    return None


def cmd_batch(con, a) -> tuple[str, object]:
    """Several operations, one per line; each is run and verified on its own (the loop is code, not the model)."""
    lines = list(a.lines)
    if not lines:
        lines = sys.stdin.read().splitlines() if a.file == "-" else open(a.file, encoding="utf-8").read().splitlines()
    ops = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            argv = shlex.split(line)
        except ValueError as e:
            ops.append((line, None, f"zły cudzysłów: {e}"))
            continue
        while argv and (argv[0] in ("dom", "python3", "python") or argv[0].endswith("dom.py")):
            argv = argv[1:]
        if not argv or argv[0] in ("batch", "--db") or argv[0] not in HANDLERS:
            ops.append((line, None, "nieznane polecenie"))
            continue
        ops.append((line, argv, None))
    if not ops:
        raise DomError("Pusta lista. Jedna operacja na linię, np.: add masło --exp 30.10 --where \"lodówka > półka 3\"", 2)
    out, results, ok = [], [], 0
    for i, (line, argv, err) in enumerate(ops, 1):
        text = ""
        if err is None:
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    args = parse(argv)
            except SystemExit:
                err = "złe argumenty (sprawdź dom <polecenie> --help)"
        if err is None:
            try:
                with con:
                    text, data = HANDLERS[args.cmd](con, args)
                err = verify(con, args, data)
            except DomError as e:
                err = str(e)
        if err is None:
            ok += 1
            out.append(f"✅ {i}/{len(ops)} {text.splitlines()[0] if text else line}")
        else:
            out.append(f"❌ {i}/{len(ops)} {line} → {err}")
        results.append({"line": line, "ok": err is None, "error": err, "text": text})
    summary = f"Wykonano {ok} z {len(ops)}."
    if ok < len(ops):
        summary += " Nie wszystko się udało: powiedz Filipowi, czego NIE zapisano."
    out.append(summary)
    if ok < len(ops):
        raise DomError("\n".join(out), 6, results)
    return "\n".join(out), results


# ---------------------------------------------------------------- photos, "show me where", labels with QR

def media_dir(con) -> str:
    row = con.execute("PRAGMA database_list").fetchone()
    base = os.path.dirname(os.path.abspath(row["file"])) if row and row["file"] else os.getcwd()
    d = os.path.join(base, "photos")
    os.makedirs(d, exist_ok=True)
    return d


def parse_box(text: str) -> list[float]:
    """"10,20,60,45" (percent of the photo: left, top, right, bottom) -> fractions."""
    try:
        v = [float(x) for x in re.split(r"[ ,;]+", text.strip()) if x]
    except ValueError:
        v = []
    if len(v) != 4 or not (0 <= v[0] < v[2] <= 100 and 0 <= v[1] < v[3] <= 100):
        raise DomError("--box: lewo,góra,prawo,dół w procentach zdjęcia, np. 5,10,95,40.", 2)
    return [x / 100 for x in v]


def photo_of(con, pid: int):
    return con.execute("SELECT * FROM photos WHERE place_id=?", (pid,)).fetchone()


def auto_box(places: dict, child) -> list[float] | None:
    """Shelves/drawers without a marked box: equal horizontal bands, 1 = top."""
    if child["kind"] not in ORDERED_KINDS or child["pos"] is None:
        return None
    sib = siblings(places, child)
    if not sib:
        return None
    i = [r["id"] for r in sib].index(child["id"])
    n = len(sib)
    return [0.03, i / n, 0.97, (i + 1) / n]


def locate_on_photo(con, places: dict, pid: int, side: str | None):
    """Deepest ancestor of `pid` with a photo, and the box (fractions) to circle on it."""
    chain = ancestry(places, pid)
    for depth in range(len(chain) - 1, -1, -1):
        ph = photo_of(con, chain[depth]["id"])
        if ph is None:
            continue
        boxes = json.loads(ph["boxes"] or "{}")
        box = [0.03, 0.03, 0.97, 0.97]
        if depth + 1 < len(chain):
            child = chain[depth + 1]
            box = boxes.get(str(child["id"])) or auto_box(places, child) or box
            # a deeper marked box (a container on that shelf) wins
            for deeper in chain[depth + 2:]:
                if str(deeper["id"]) in boxes:
                    box = boxes[str(deeper["id"])]
        if side in ("lewo", "środek", "prawo"):
            third = (box[2] - box[0]) / 3
            k = ("lewo", "środek", "prawo").index(side)
            box = [box[0] + k * third, box[1], box[0] + (k + 1) * third, box[3]]
        return ph, chain[depth], box
    return None, None, None


def route_steps(places: dict, r) -> list[str]:
    chain = ancestry(places, r["place_id"])
    if chain and chain[0]["parent_id"] is None and chain[0]["kind"] == "mieszkanie" and len(chain) > 1:
        chain = chain[1:]
    steps = []
    for i, row in enumerate(chain):
        label = place_label(places, row)
        if i == 0:
            steps.append(f"Idź do: {label}.")
        elif row["kind"] in ("półka", "szuflada"):
            steps.append(f"{'Otwórz' if row['kind'] == 'szuflada' else 'Spójrz na'}: {label}.")
        else:
            steps.append(f"{'Podejdź do' if i == 1 else 'Znajdź'}: {label}.")
    sector = ", ".join(x for x in (SIDE_TXT.get(r["side"] or ""), DEPTH_TXT.get(r["depth"] or "")) if x)
    steps.append(f"{r['name']}" + (f" leży {sector}." if sector else " tam leży."))
    return steps


def draw_circle(src: str, box: list[float], out: str, caption: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError as e:
        raise DomError("Do zdjęć z kółkiem potrzebny jest Pillow (python3 -m pip install pillow).", 1) from e
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    img.thumbnail((1600, 1600))
    w, h = img.size
    x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    pad = 0.08 * max(x1 - x0, y1 - y0)
    x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
    shade = Image.new("L", img.size, 110)
    ImageDraw.Draw(shade).ellipse((x0, y0, x1, y1), fill=0)
    img = Image.composite(Image.new("RGB", img.size, (0, 0, 0)), img, shade.point(lambda v: v))
    d = ImageDraw.Draw(img)
    lw = max(4, w // 150)
    d.ellipse((x0, y0, x1, y1), outline=(230, 30, 30), width=lw)
    bar = max(28, h // 22)
    d.rectangle((0, h - bar, w, h), fill=(0, 0, 0))
    font = None
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
              "C:/Windows/Fonts/arial.ttf"):
        if os.path.exists(f):
            font = ImageFont.truetype(f, int(bar * 0.55))
            break
    if font is None:
        try:
            font = ImageFont.load_default(size=int(bar * 0.55))
        except TypeError:  # Pillow < 10.1
            font = ImageFont.load_default()
    d.text((lw * 2, h - bar + bar // 5), caption.replace("→", ">"), fill=(255, 255, 255), font=font)
    img.save(out, "JPEG", quality=85)


def cmd_photo(con, a) -> tuple[str, object]:
    places = place_rows(con)
    pid = resolve_place(con, a.path, places)
    if a.photo_cmd == "add":
        if not os.path.isfile(a.file):
            raise DomError(f"Nie ma pliku {a.file}.", 2)
        ext = os.path.splitext(a.file)[1].lower() or ".jpg"
        dest = os.path.join(media_dir(con), f"p{pid}{ext}")
        if os.path.abspath(a.file) != os.path.abspath(dest):
            shutil.copyfile(a.file, dest)
        old = photo_of(con, pid)
        con.execute("INSERT INTO photos(place_id, file, boxes) VALUES (?,?,?) ON CONFLICT(place_id) DO UPDATE SET file=?",
                    (pid, dest, old["boxes"] if old else "{}", dest))
        kids = [r for r in places.values() if r["parent_id"] == pid]
        hint = (f" Półki/szuflady ({len(kids)}) zaznaczę automatycznie pasami od góry; popraw przez photo mark."
                if kids else "")
        return f"Zdjęcie zapisane dla: {place_path(places, pid)}.{hint}", {"place_id": pid, "file": dest}
    # mark: the box of `path` on the nearest ancestor's photo
    chain = ancestry(places, pid)
    owner = next((r for r in reversed(chain[:-1]) if photo_of(con, r["id"])), None)
    if owner is None:
        raise DomError(f"Żaden mebel nad „{place_path(places, pid)}” nie ma zdjęcia. Najpierw photo add.", 3)
    ph = photo_of(con, owner["id"])
    boxes = json.loads(ph["boxes"] or "{}")
    boxes[str(pid)] = parse_box(a.box)
    con.execute("UPDATE photos SET boxes=? WHERE place_id=?", (json.dumps(boxes), owner["id"]))
    return f"Zaznaczone: {place_path(places, pid)} na zdjęciu {place_path(places, owner['id'])}.", \
        {"place_id": pid, "photo_of": owner["id"], "box": boxes[str(pid)]}


def cmd_show(con, a) -> tuple[str, object]:
    """Where is it, as a photo with a red circle plus step-by-step directions (for voice)."""
    places = place_rows(con)
    if place_code(a.query, places) is not None:
        pid = place_code(a.query, places)
        r = {"name": places[pid]["name"], "place_id": pid, "side": None, "depth": None, "id": f"p{pid}"}
    else:
        rows = search_stock(con, a.query)
        if not rows:
            raise DomError(f"Nie mam w spisie niczego pasującego do „{a.query}”.", 3)
        names = sorted({x["name"] for x in rows})
        if len(names) > 1:
            raise DomError("Kilka rzeczy pasuje: " + ", ".join(names) + ". Powiedz, o którą chodzi.", 4, names)
        r = rows[0]
    steps = route_steps(places, r)
    data = {"item": r["name"], "place": place_path(places, r["place_id"]), "steps": steps, "image": None}
    ph, owner, box = locate_on_photo(con, places, r["place_id"], r["side"])
    if ph is None:
        return " ".join(steps) + "\n(Brak zdjęcia tego mebla: zrób zdjęcie i dodaj je przez photo add.)", data
    out = os.path.abspath(a.out or os.path.join(media_dir(con), "pokaz.jpg"))
    short = " > ".join(place_path(places, r["place_id"], pretty=False).split(" > ")[-2:])
    draw_circle(ph["file"], box, out, f"{r['name']}: {short}")
    data["image"] = out
    return " ".join(steps) + f"\nMEDIA:{out}", data


LABEL_SIZES = {"pojemnik": (60, 30), "wizytowka": (85, 55)}  # mm


def short_path(places: dict, pid: int | None) -> str:
    """"Kuchnia > Szafka pod zlewem > Pojemnik 3" (no flat root, no shelf-position notes)."""
    chain = ancestry(places, pid)
    if len(chain) > 1 and chain[0]["parent_id"] is None and chain[0]["kind"] == "mieszkanie":
        chain = chain[1:]
    return " > ".join(r["name"] for r in chain)


def label_payload(places: dict, pid: int) -> str:
    tpl = os.environ.get("DOM_QR_TEMPLATE", "Hermes, co jest w: {path} [P{id}]")
    return tpl.format(id=pid, path=short_path(places, pid), name=places[pid]["name"])


def svg_escape(t: str) -> str:
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def fit(text: str, width_mm: float, font_mm: float) -> list[str]:
    """Wrap into at most 2 lines that fit (average sans-serif glyph ≈ 0.55 em), ellipsis if longer."""
    per_line = max(4, int(width_mm / (font_mm * 0.55)))
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= per_line:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lines = [ln for ln in lines if ln]
    if len(lines) > 2:
        lines = [lines[0], lines[1][:per_line - 1] + "…"]
    return [ln if len(ln) <= per_line else ln[:per_line - 1] + "…" for ln in lines]


def clip_text(text: str, width_mm: float, font_mm: float) -> str:
    n = max(4, int(width_mm / (font_mm * 0.55)))
    return text if len(text) <= n else text[:n - 1] + "…"


def label_svg(con, places: dict, pids: list[int], fmt: str) -> list[str]:
    import dom_qr
    lw, lh = LABEL_SIZES[fmt]
    gap = 4
    cols, rows_per = max(1, int((190 + gap) // (lw + gap))), max(1, int((277 + gap) // (lh + gap)))
    per_page = cols * rows_per
    stock = list(con.execute(STOCK_SQL))
    pages = []
    for start in range(0, len(pids), per_page):
        parts = []
        for k, pid in enumerate(pids[start:start + per_page]):
            x, y = 10 + (k % cols) * (lw + gap), 10 + (k // cols) * (lh + gap)
            q = dom_qr.encode(label_payload(places, pid), "M")
            qsize = (lh - 6) if fmt == "pojemnik" else 34
            cell = qsize / len(q)
            tx = x + 5 + qsize
            tw = x + lw - 2 - tx
            parts.append(f'<g clip-path="url(#c{start + k})"><clipPath id="c{start + k}"><rect x="{x}" y="{y}" '
                         f'width="{lw}" height="{lh}"/></clipPath>')
            parts.append(f'<rect x="{x}" y="{y}" width="{lw}" height="{lh}" fill="none" stroke="#999" '
                         'stroke-width="0.3" stroke-dasharray="1,1"/>')
            parts.append(dom_qr.svg_path(q, x + 3, y + 3, cell))
            fs = 3.6 if fmt == "pojemnik" else 4.6
            ty = y + 3 + fs
            for line in fit(places[pid]["name"], tw, fs):
                parts.append(f'<text x="{tx}" y="{ty}" font-family="sans-serif" font-size="{fs}" '
                             f'font-weight="bold">{svg_escape(line)}</text>')
                ty += fs * 1.15
            parent = short_path(places, places[pid]["parent_id"]) if places[pid]["parent_id"] else ""
            for line in fit(parent, tw, fs * 0.62):
                parts.append(f'<text x="{tx}" y="{ty + 0.5}" font-family="sans-serif" font-size="{fs * 0.62}" '
                             f'fill="#444">{svg_escape(line)}</text>')
                ty += fs * 0.75
            if fmt == "wizytowka":
                ids = subtree_ids(places, pid)
                things = sorted({r["name"] for r in stock if r["place_id"] in ids})
                ty += 2
                for t in things[:max(0, int((y + lh - 7 - ty) // 3.6))]:
                    parts.append(f'<text x="{tx}" y="{ty}" font-family="sans-serif" font-size="2.9">'
                                 f'• {svg_escape(clip_text(t, tw - 3, 2.9))}</text>')
                    ty += 3.6
            parts.append(f'<text x="{tx}" y="{y + lh - 3}" font-family="monospace" font-size="2.8" '
                         f'fill="#666">P{pid}</text></g>')
        pages.append('<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">'
                     '<rect width="210" height="297" fill="#fff"/>' + "".join(parts) + "</svg>")
    return pages


def cmd_label(con, a) -> tuple[str, object]:
    places = place_rows(con)
    if a.paths:
        pids = []
        for p in a.paths:
            pid = resolve_place(con, p, places)
            pids += sorted(subtree_ids(places, pid), key=lambda i: place_path(places, i, pretty=False)) \
                if a.with_children else [pid]
    else:
        pids = sorted((pid for pid, r in places.items() if r["kind"] == "pojemnik"),
                      key=lambda i: place_path(places, i, pretty=False))
    if not pids:
        raise DomError("Nie ma czego drukować: podaj miejsca albo dodaj pojemniki (map add … --kind pojemnik).", 3)
    pages = label_svg(con, places, pids, a.format)
    out = os.path.abspath(a.out or os.path.join(media_dir(con), f"etykiety-{a.format}.html"))
    if out.endswith(".svg"):
        content = pages[0]
    else:
        content = ("<!doctype html><meta charset='utf-8'><title>Etykiety</title><style>@page{size:A4;margin:0}"
                   "body{margin:0}svg{display:block;page-break-after:always}</style>" + "".join(pages))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(content)
    return (f"Etykiety ({len(pids)}, format {a.format}, stron: {len(pages)}) zapisane: {out}. "
            f"Wydrukuj w skali 100%.\nMEDIA:{out}"), {"file": out, "places": pids}


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dom", description="Spis rzeczy w domu (spiżarnia, chemia) i mapa mieszkania.")
    p.add_argument("--json", action="store_true", help="structured output")
    p.add_argument("--db", help="SQLite path (default ~/.hermes/autonomy/home-inventory/dom.db or $DOM_DB)")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("map", help="mapa mieszkania")
    ms = m.add_subparsers(dest="map_cmd", required=True)
    x = ms.add_parser("add", help='dodaj miejsce: "Pokój Teosia > Szafa 2 > Półka 3"')
    x.add_argument("path", nargs="+")
    x.add_argument("--kind", choices=("pokój", "mebel", "półka", "szuflada", "pojemnik", "inne"))
    x.add_argument("--alias", nargs="+", help="aliasy po przecinku")
    x.add_argument("--note", nargs="+")
    x.add_argument("--pos", type=int, help="numer półki/szuflady od góry")
    x.add_argument("--shelves", type=int, help="utwórz od razu N półek (Półka 1..N, od góry)")
    x.add_argument("--drawers", type=int, help="utwórz od razu N szuflad (Szuflada 1..N, od góry)")
    x = ms.add_parser("import", help="zaimportuj mapę z konspektu z wcięciami (plik albo - dla stdin)")
    x.add_argument("file")
    x = ms.add_parser("show", help="pokaż mapę (całą albo od miejsca)")
    x.add_argument("path", nargs="*")
    x = ms.add_parser("rm", help="usuń puste miejsce (z podmiejscami)")
    x.add_argument("path", nargs="+")
    x = ms.add_parser("rename", help="zmień nazwę miejsca")
    x.add_argument("path")
    x.add_argument("new_name")

    ph = sub.add_parser("photo", help="zdjęcia mebli/pokoi do pokazywania, gdzie co leży")
    ps = ph.add_subparsers(dest="photo_cmd", required=True)
    x = ps.add_parser("add", help="dodaj/zmień zdjęcie miejsca")
    x.add_argument("path", nargs="+")
    x.add_argument("--file", required=True, help="ścieżka do zdjęcia (jpg/png)")
    x = ps.add_parser("mark", help="zaznacz półkę/szufladę/pojemnik na zdjęciu mebla")
    x.add_argument("path", nargs="+")
    x.add_argument("--box", required=True, help="lewo,góra,prawo,dół w %% zdjęcia, np. 5,10,95,40")
    x = sub.add_parser("show", help="pokaż na zdjęciu z kółkiem, gdzie leży rzecz, i jak tam dojść")
    x.add_argument("query", nargs="+")
    x.add_argument("--out", help="plik wyjściowy .jpg")
    x = sub.add_parser("label", help="etykiety z kodem QR do druku (pojemniki, wizytówki mebli)")
    x.add_argument("paths", nargs="*", help="miejsca; bez tego: wszystkie pojemniki")
    x.add_argument("--format", choices=tuple(LABEL_SIZES), default="pojemnik")
    x.add_argument("--with-children", action="store_true", help="też półki/szuflady/pojemniki w środku")
    x.add_argument("--out", help=".html (domyślnie, kilka stron A4) albo .svg")

    x = sub.add_parser("add", help="dodaj rzecz (np. po zakupach)")
    x.add_argument("name", nargs="+")
    x.add_argument("--qty", type=float, default=1.0)
    x.add_argument("--unit")
    x.add_argument("--exp", nargs="+", help="termin: 2026-10-20, 20.10, 10.2026, „20 października”, „za 5 dni”")
    x.add_argument("--where", nargs="+", help='miejsce: "Kuchnia > Lodówka > Półka 2"; bez tego: zwykłe miejsce tej rzeczy')
    x.add_argument("--side", help="lewo | środek | prawo")
    x.add_argument("--depth", help="przód | środek | tył")
    x.add_argument("--cat", help="spożywcze | chemia | ubrania | inne")
    x.add_argument("--alias", nargs="+", help="inne nazwy po przecinku")
    x.add_argument("--note", nargs="+")

    x = sub.add_parser("where", help="gdzie jest rzecz")
    x.add_argument("query", nargs="+")
    x = sub.add_parser("list", help="co jest (w miejscu / w kategorii)")
    x.add_argument("--where", nargs="+")
    x.add_argument("--cat")
    for name, hlp in (("use", "zużyłem"), ("throw", "wyrzuciłem")):
        x = sub.add_parser(name, help=hlp)
        x.add_argument("query", nargs="+")
        x.add_argument("--qty", type=float)
        x.add_argument("--all", action="store_true")
        if name == "throw":
            x.add_argument("--expired-only", action="store_true", help="tylko przeterminowane partie")
    x = sub.add_parser("move", help="przenieś rzecz")
    x.add_argument("query", nargs="+")
    x.add_argument("--where", nargs="+")
    x.add_argument("--side")
    x.add_argument("--depth")
    x.add_argument("--keep-home", action="store_true", help="nie zmieniaj zwykłego miejsca tej rzeczy")
    x = sub.add_parser("set", help="popraw partię (termin, ilość, otwarcie)")
    x.add_argument("query", nargs="+")
    x.add_argument("--exp", nargs="+")
    x.add_argument("--qty", type=float)
    x.add_argument("--note", nargs="+")
    x.add_argument("--alias", nargs="+")
    x.add_argument("--opened", nargs="?", const="", help="data otwarcia (bez wartości: dziś)")
    x.add_argument("--days-after-opening", type=int, help="ile dni ważne po otwarciu")
    x.add_argument("--tag", action="append", help="ustaw atrybut w notatce bez kasowania reszty, np. stan:pranie")
    x = sub.add_parser("expiring", help="co traci termin")
    x.add_argument("--days", type=int, default=7)
    x.add_argument("--cat")
    x = sub.add_parser("plan", help="podpowiedzi do planowania posiłków")
    x.add_argument("--days", type=int, default=5)
    x = sub.add_parser("remind", help="przypomnienie do crona (puste, gdy nic)")
    x.add_argument("--days", type=int, default=2)
    x = sub.add_parser("batch", help="kilka operacji naraz, jedna na linię; każda wykonana i sprawdzona osobno")
    x.add_argument("lines", nargs="*", help='np. \'add masło --exp 30.10 --where "lodówka > półka 3"\'')
    x.add_argument("--file", default="-", help="plik z liniami (domyślnie stdin, gdy brak linii w argumentach)")
    x = sub.add_parser("history", help="historia zmian")
    x.add_argument("query", nargs="?")
    x.add_argument("--limit", type=int, default=20)
    return p


HANDLERS = {
    "map": cmd_map, "add": cmd_add, "where": cmd_where, "list": cmd_list,
    "use": lambda c, a: consume(c, a, "zużyte"), "throw": lambda c, a: consume(c, a, "wyrzucone"),
    "move": cmd_move, "set": cmd_set, "expiring": cmd_expiring, "plan": cmd_plan, "remind": cmd_remind,
    "history": cmd_history, "batch": cmd_batch, "photo": cmd_photo, "show": cmd_show, "label": cmd_label,
}


MULTIWORD = ("path", "name", "query", "where", "exp", "note", "alias")


def parse(argv: list[str]) -> argparse.Namespace:
    """Unquoted multi-word names (`add ser żółty`, `--where lodówka > półka 2`) are joined back into one."""
    args = build_parser().parse_args(argv)
    for k in MULTIWORD:
        v = getattr(args, k, None)
        if isinstance(v, list):
            setattr(args, k, " ".join(v) if v else None)
    return args


def run(argv: list[str], con: sqlite3.Connection | None = None) -> tuple[int, str]:
    args = parse(argv)
    own = con is None
    con = con or connect(args.db)
    try:
        with con:
            text, data = HANDLERS[args.cmd](con, args)
        out = json.dumps({"ok": True, "text": text, "data": data}, ensure_ascii=False, indent=1) if args.json else text
        return 0, out
    except DomError as e:
        out = json.dumps({"ok": False, "error": str(e), "data": e.data}, ensure_ascii=False) if args.json else str(e)
        return e.code, out
    finally:
        if own:
            con.close()


def main() -> int:
    code, out = run(sys.argv[1:])
    if out:
        print(out, file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
