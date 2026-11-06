#!/usr/bin/env python3
"""Przygotowanie do wyjścia z domu: pogoda w oknie wyjścia, strój z garderoby, lista do spakowania.

    wyjscie.py plan --od "2026-10-31 18:00" --do "2026-10-31 23:00" --okazja randka --miejsce restauracja,teatr \
        --transport taxi [--gdzie Gdańsk] [--z-dzieckiem] [--wyjazd 17:35 | --trasa-json trasa.json]
        [--dodaj "bilety do teatru"] [--json]
    wyjscie.py lista ...      to samo, ale tylko lista do spakowania (bez stroju)
    wyjscie.py slownik        znane okazje, miejsca, środki transportu, flagi pogody

Pogoda: weather.py z tego samego katalogu (Open-Meteo, bez klucza), godzina po godzinie w oknie od–do.
Garderoba: `dom.py --json list --cat ubrania` (home-inventory); atrybuty w notatce rzeczy, np.
`typ:kurtka ciepło:4 styl:casual woda:tak kto:filip kolor:granat`. Bez garderoby: ogólna rada wg temperatury.
Profil (prywatny, poza git): ~/.hermes/autonomy/wyjscie/profil.json albo $WYJSCIE_PROFIL.
Tylko biblioteka standardowa. Kody wyjścia: 0 ok, 1 błąd, 2 złe argumenty (data, okno).
"""
import argparse
import json
import os
import pwd
import subprocess
import sys
import unicodedata
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir
PROFILE_PATH = os.environ.get("WYJSCIE_PROFIL") or os.path.join(REAL_HOME, ".hermes/autonomy/wyjscie/profil.json")
DOM = os.path.join(HERE, "dom.py")

DEFAULT_PROFILE = {
    "dom": "Gdańsk",
    "zawsze": [],          # osobiste rzeczy zawsze, np. "okulary", "słuchawki"
    "pomijaj": [],         # rzeczy z listy, których nie chcesz widzieć
    "kto": "filip",        # czyja garderoba
    "dziecko": {"kto": "teos", "pieluchy": True, "wozek": True},
    "przygotowanie_min": {"bazowo": 10, "dziecko": 20, "elegancko": 15},
}

# okazja -> akceptowane style (pierwszy najlepszy)
STYLE = {
    "randka": ["smart", "elegancki", "casual"], "praca": ["smart", "casual"],
    "spotkanie_sluzbowe": ["smart", "elegancki"], "wesele": ["formalny", "elegancki"],
    "chrzciny": ["elegancki", "formalny", "smart"], "komunia": ["elegancki", "formalny", "smart"],
    "pogrzeb": ["formalny", "elegancki"], "teatr": ["elegancki", "smart"], "filharmonia": ["elegancki", "smart"],
    "koncert": ["casual", "smart"], "kino": ["casual", "smart"], "urodziny": ["casual", "smart"],
    "imieniny": ["smart", "casual"], "rocznica": ["elegancki", "smart"], "sport": ["sport"], "silownia": ["sport"],
    "spacer": ["casual", "sport"], "wycieczka": ["casual", "sport"], "plac_zabaw": ["casual", "sport"],
    "zakupy": ["casual", "smart"], "lekarz": ["casual", "smart"], "urzad": ["casual", "smart"],
    "mecz": ["casual", "sport"], "podroz": ["casual", "sport", "smart"], "parapetowka": ["casual", "smart"],
}
DEFAULT_STYLE = ["casual", "smart"]
ELEGANT = {"wesele", "chrzciny", "komunia", "pogrzeb", "teatr", "filharmonia", "rocznica", "spotkanie_sluzbowe"}
TRANSPORT = ["pieszo", "auto", "taxi", "komunikacja", "pociag", "rower", "hulajnoga", "traficar"]
FLAGS = ["deszcz", "snieg", "burza", "zimno", "mroz", "cieplo", "upal", "slonce", "wiatr", "ciemno", "spadek_temp"]
SLOTS = [("okrycie", "Okrycie"), ("gora", "Góra"), ("dol", "Dół"), ("buty", "Buty"), ("dodatek", "Dodatki")]
TYP2SLOT = {
    "kurtka": "okrycie", "plaszcz": "okrycie", "plaszcz_przeciwdeszczowy": "okrycie", "marynarka": "okrycie",
    "kamizelka": "okrycie", "bluza": "gora", "sweter": "gora", "koszula": "gora", "koszulka": "gora",
    "t-shirt": "gora", "polo": "gora", "bluzka": "gora", "sukienka": "gora", "spodnie": "dol", "jeansy": "dol",
    "szorty": "dol", "spodnica": "dol", "dresy": "dol", "buty": "buty", "kalosze": "buty", "trampki": "buty",
    "sneakersy": "buty", "polbuty": "buty", "kozaki": "buty", "sandaly": "buty", "czapka": "dodatek",
    "szalik": "dodatek", "rekawiczki": "dodatek", "krawat": "dodatek", "pasek": "dodatek",
}
GENERIC = {
    1: "koszulka, lekkie spodnie lub szorty, przewiewne buty",
    2: "koszulka z długim rękawem albo koszula, lekka bluza lub kurtka, długie spodnie",
    3: "sweter lub bluza, kurtka przejściowa, długie spodnie, pełne buty",
    4: "ciepła kurtka, sweter, czapka, pełne buty",
    5: "kurtka zimowa, warstwy (termo + sweter), czapka, szalik, rękawiczki, ciepłe buty",
}
SNOW = set(range(71, 78)) | {85, 86}
STORM = {95, 96, 99}


def fold(s) -> str:
    s = unicodedata.normalize("NFKD", str(s).lower().replace("ł", "l"))
    return "".join(c for c in s if not unicodedata.combining(c)).strip().replace(" ", "_")


def load_profile(path=None) -> dict:
    prof = json.loads(json.dumps(DEFAULT_PROFILE))
    try:
        with open(path or PROFILE_PATH, encoding="utf-8") as f:
            user = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return prof
    for k, v in user.items():
        prof[k] = dict(prof.get(k, {}), **v) if isinstance(v, dict) and isinstance(prof.get(k), dict) else v
    return prof


def load_rules(path=None) -> dict:
    with open(path or os.path.join(HERE, "listy.json"), encoding="utf-8") as f:
        return json.load(f)


def parse_when(s: str, base: date | None = None) -> datetime:
    s = s.strip().replace("T", " ")
    base = base or date.today()
    words = {"dzis": 0, "dzisiaj": 0, "jutro": 1, "pojutrze": 2}
    parts = s.split()
    if parts and fold(parts[0]) in words:
        d = base + timedelta(days=words[fold(parts[0])])
        hm = parts[1] if len(parts) > 1 else "00:00"
        return datetime.combine(d, datetime.strptime(hm, "%H:%M").time())
    if len(parts) == 2 and parts[0].count(".") == 1:  # „31.10 18:00”: dopisz rok, zanim strptime zgadnie
        s = f"{parts[0]}.{base.year} {parts[1]}"
        try:
            dt = datetime.strptime(s, "%d.%m.%Y %H:%M")
        except ValueError:
            raise ValueError(f"nie rozumiem daty „{s}”") from None
        return dt if dt.date() >= base else dt.replace(year=base.year + 1)
    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%H:%M"):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if fmt == "%H:%M":
            return datetime.combine(base, dt.time())
        return dt
    raise ValueError(f"nie rozumiem daty „{s}” (np. 2026-10-31 18:00, 31.10 18:00, jutro 18:00, 18:00)")


# ---------- pogoda ----------

def fetch_weather(place: str, start: datetime) -> dict:
    """Prognoza z weather.py (moduł z tego samego katalogu): hourly + days."""
    sys.path.insert(0, HERE)
    import weather  # noqa: E402  (deployed next to this script)
    days = (start.date() - date.today()).days + 2
    if days > 16:
        raise ValueError("prognoza sięga 16 dni; sprawdzę bliżej terminu")
    loc = weather.geocode(place)
    try:
        return weather.open_meteo(loc, max(days, 2))
    except Exception:
        return weather.wttr(loc, min(max(days, 2), 3))


def window_weather(data: dict, start: datetime, end: datetime) -> dict:
    s, e = start.strftime("%Y-%m-%dT%H"), end.strftime("%Y-%m-%dT%H")
    hours = [h for h in data.get("hourly", []) if s <= h["time"][:13] <= e]
    if not hours:
        return {"ok": False, "flags": [], "powod": "brak prognozy dla tego okna"}
    vals = lambda k: [h[k] for h in hours if h.get(k) is not None]  # noqa: E731
    temp, feels = vals("temp"), vals("feels") or vals("temp")
    day = next((d for d in data.get("days", []) if d["date"] == start.strftime("%Y-%m-%d")), {})
    w = {
        "ok": True, "od": hours[0]["time"], "do": hours[-1]["time"],
        "tmin": min(temp), "tmax": max(temp), "feels_min": min(feels), "feels_max": max(feels),
        "opad_mm": round(sum(vals("precip_mm")), 1), "opad_szansa": max(vals("precip_prob") or [0]),
        "wiatr_kmh": max(vals("wind_kmh") or [0]), "porywy_kmh": day.get("gusts_kmh"),
        "chmury": round(sum(vals("clouds")) / len(vals("clouds"))) if vals("clouds") else None,
        "kody": sorted(set(vals("code"))), "wschod": day.get("sunrise"), "zachod": day.get("sunset"),
    }
    f = []
    if w["opad_mm"] >= 0.3 or w["opad_szansa"] >= 40:
        f.append("deszcz")
    if SNOW & set(w["kody"]):
        f.append("snieg")
    if STORM & set(w["kody"]):
        f.append("burza")
    if w["feels_min"] < 8:
        f.append("zimno")
    if w["feels_min"] < 0:
        f.append("mroz")
    if w["tmax"] >= 22:
        f.append("cieplo")
    if w["tmax"] >= 28:
        f.append("upal")
    if w["wiatr_kmh"] >= 35 or (w["porywy_kmh"] or 0) >= 50:
        f.append("wiatr")
    if w["zachod"] and w["wschod"]:
        sh, eh = start.strftime("%H:%M"), end.strftime("%H:%M")
        dark = eh > w["zachod"] or sh < w["wschod"] or end.date() > start.date()
        light_hours = [h for h in hours if w["wschod"] <= h["time"][11:16] <= w["zachod"]]
        if dark:
            f.append("ciemno")
        if light_hours and w["chmury"] is not None and w["chmury"] < 50 and w["tmax"] >= 15:
            f.append("slonce")
    if temp[0] - temp[-1] >= 4:
        f.append("spadek_temp")
    w["flags"] = f
    w["cieplo_poziom"] = warmth_level(w["feels_min"])
    return w


def warmth_level(feels_min: float) -> int:
    for lvl, lim in ((1, 20), (2, 14), (3, 8), (4, 0)):
        if feels_min >= lim:
            return lvl
    return 5


def weather_line(w: dict) -> str:
    if not w.get("ok"):
        return f"🌦 Pogoda: {w.get('powod', 'brak danych')}"
    t = f"{w['tmin']:.0f}…{w['tmax']:.0f}°C"
    if abs(w["feels_min"] - w["tmin"]) >= 3:
        t += f" (odczuwalna od {w['feels_min']:.0f}°C)"
    rain = f"opady {w['opad_mm']} mm ({w['opad_szansa']:.0f}%)" if w["opad_mm"] or w["opad_szansa"] else "bez opadów"
    extra = []
    if "wiatr" in w["flags"]:
        extra.append(f"wiatr do {w['wiatr_kmh']:.0f} km/h" + (f", porywy {w['porywy_kmh']:.0f}" if w["porywy_kmh"] else ""))
    if "snieg" in w["flags"]:
        extra.append("śnieg")
    if "burza" in w["flags"]:
        extra.append("burza")
    if "ciemno" in w["flags"] and w.get("zachod"):
        extra.append(f"zmrok {w['zachod']}")
    return "🌦 Pogoda: " + ", ".join([t, rain] + extra)


# ---------- lista ----------

TRANSPORT_WORDS = [
    ("traficar", "traficar"), ("hulajn", "hulajnoga"), ("tier", "hulajnoga"), ("dott", "hulajnoga"),
    ("rower", "rower"), ("mevo", "rower"), ("bolt", "taxi"), ("uber", "taxi"), ("taxi", "taxi"), ("taks", "taxi"),
    ("freenow", "taxi"), ("pkp", "pociag"), ("intercity", "pociag"), ("pociag", "pociag"), ("skm", "komunikacja"),
    ("pkm", "komunikacja"), ("tramwaj", "komunikacja"), ("autobus", "komunikacja"), ("komunik", "komunikacja"),
    ("auto", "auto"), ("samoch", "auto"), ("pieszo", "pieszo"), ("spacer", "pieszo"),
]


def transport_word(sposob: str) -> str | None:
    f = fold(sposob)
    return next((v for k, v in TRANSPORT_WORDS if k in f), None)


def apply_route(a, route: dict) -> None:
    """Kontrakt JSON procedury `trasa`: wyjdz_o, odcinki[].najlepsza.sposob, srodek_dla_wyjscia, powrot."""
    if route.get("wyjdz_o") and not a.wyjazd:
        a.wyjazd = route["wyjdz_o"]
    modes, outside, luggage = list(a.transport), 0, False
    for seg in route.get("odcinki", []):
        m = transport_word((seg.get("najlepsza") or {}).get("sposob", ""))
        if m:
            modes.append(m)
        sw = seg.get("srodek_dla_wyjscia") or {}
        outside += sw.get("na_zewnatrz_min") or 0
        luggage = luggage or bool(sw.get("bagaz"))
    m = transport_word((route.get("powrot") or {}).get("sposob", ""))
    if m:
        modes.append(m)
    if outside >= 15 and "pieszo" not in modes:
        modes.append("pieszo")  # długo na zewnątrz: rzeczy „na pieszo” (odblask, kaptur) też się liczą
    a.transport = list(dict.fromkeys(modes))
    a.na_zewnatrz_min, a.bagaz = outside, luggage


def context(a, prof: dict, w: dict) -> dict:
    hours = max(0.0, (a.end - a.start).total_seconds() / 3600)
    ch = prof.get("dziecko", {})
    return {
        "pogoda": set(w.get("flags", [])), "okazja": {fold(a.okazja)} if a.okazja else set(),
        "miejsce": {fold(m) for m in a.miejsce}, "transport": {fold(t) for t in a.transport},
        "dziecko": {bool(a.z_dzieckiem)}, "pieluchy": {bool(ch.get("pieluchy"))}, "wozek": {bool(ch.get("wozek"))},
        "wiatr": {"wiatr" in w.get("flags", [])},
        "h": hours,
    }


def match(cond: dict, ctx: dict) -> bool:
    for k, allowed in cond.items():
        if k == "min_h":
            if ctx["h"] < allowed:
                return False
            continue
        if not ctx.get(k, set()) & set(allowed if isinstance(allowed, list) else [allowed]):
            return False
    return True


def packing(rules: dict, ctx: dict, prof: dict, extra: list[str]) -> list[tuple[str, list[str]]]:
    skip = {fold(x) for x in prof.get("pomijaj", [])}
    groups = {g: [] for g, _ in rules["grupy"]}
    for r in rules["rzeczy"]:
        if "gdy" in r and not match(r["gdy"], ctx):
            continue
        if "chyba_ze" in r and match(r["chyba_ze"], ctx):
            continue
        if fold(r["co"]) in skip:
            continue
        groups[r["grupa"]].append(r["co"])
    groups["zawsze"] += [x for x in prof.get("zawsze", []) if fold(x) not in skip]
    if extra:
        groups.setdefault("dodatkowo", []).extend(extra)
    names = dict(rules["grupy"], dodatkowo="Dodatkowo (z miejsca, zaproszenia, Twoje)")
    return [(names[g], items) for g, items in groups.items() if items]


# ---------- strój ----------

def attrs(note: str | None) -> dict:
    out = {}
    for tok in (note or "").replace(",", " ").split():
        if ":" in tok:
            k, v = tok.split(":", 1)
            out[fold(k)] = fold(v)
    return out


def load_wardrobe(path: str | None) -> list[dict] | None:
    try:
        if path:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        else:
            if not os.path.exists(DOM):
                return None
            p = subprocess.run([sys.executable, DOM, "--json", "list", "--cat", "ubrania"],
                               capture_output=True, text=True, timeout=30)
            raw = json.loads(p.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    rows = raw.get("data", raw) if isinstance(raw, dict) else raw
    out = []
    for r in rows or []:
        at = attrs(r.get("note"))
        slot = at.get("slot") or TYP2SLOT.get(at.get("typ", ""))
        if not slot:
            continue
        try:
            warm = int(at.get("cieplo", "3"))
        except ValueError:
            warm = 3
        out.append({"nazwa": r.get("item"), "miejsce": r.get("place"), "slot": slot, "cieplo": warm,
                    "styl": at.get("styl", "casual"), "woda": at.get("woda") == "tak", "kto": at.get("kto", "filip"),
                    "kolor": at.get("kolor"), "stan": at.get("stan", "czyste"), "typ": at.get("typ")})
    return out


def outfit(wardrobe: list[dict] | None, w: dict, okazja: str | None, kto: str) -> dict:
    lvl = w.get("cieplo_poziom", 3)
    styles = STYLE.get(fold(okazja), DEFAULT_STYLE) if okazja else DEFAULT_STYLE
    rain = bool({"deszcz", "snieg"} & set(w.get("flags", [])))
    res = {"poziom": lvl, "style": styles, "ogolnie": GENERIC[lvl], "sloty": {}, "braki": []}
    if rain:
        res["ogolnie"] += "; wodoodporne okrycie i buty"
    if fold(okazja or "") == "pogrzeb":
        res["ogolnie"] += "; kolory ciemne"
    if not wardrobe:
        return res
    for slot, _ in SLOTS:
        cands = [x for x in wardrobe if x["slot"] == slot and x["kto"] == fold(kto) and x["stan"] != "pranie"
                 and x["styl"] in styles]
        if slot == "dodatek":
            cands = [x for x in cands if lvl >= 4 or x["typ"] in ("krawat", "pasek")]
        if slot == "okrycie" and lvl <= 1 and not rain:
            continue
        if not cands:
            if slot != "dodatek":
                res["braki"].append(slot)
            continue

        def score(x):
            s = -abs(x["cieplo"] - lvl) * 2 - styles.index(x["styl"])
            if rain and slot in ("okrycie", "buty"):
                s += 3 if x["woda"] else -2
            if fold(okazja or "") == "pogrzeb" and x["kolor"] in ("czarny", "granat", "grafit", "szary"):
                s += 2
            return s
        cands.sort(key=score, reverse=True)
        res["sloty"][slot] = cands[:2]
    return res


def prep_time(a, prof: dict) -> int:
    pm = prof.get("przygotowanie_min", {})
    m = pm.get("bazowo", 10)
    if a.z_dzieckiem:
        m += pm.get("dziecko", 20)
    if fold(a.okazja or "") in ELEGANT:
        m += pm.get("elegancko", 15)
    return m


def hints(a, w: dict, prof: dict) -> list[str]:
    h = []
    ok = fold(a.okazja or "")
    if ok in ("wesele", "teatr", "filharmonia", "chrzciny", "komunia", "spotkanie_sluzbowe"):
        h.append("Dress code: sprawdź zaproszenie lub stronę miejsca.")
    if ok in ("urodziny", "imieniny", "wesele", "chrzciny", "komunia", "rocznica", "parapetowka"):
        h.append("Prezent: czy jest kupiony? (lista „Dla innych”, CRM)")
    if {"auto"} & {fold(t) for t in a.transport}:
        h.append("Auto: paliwo/ładowanie i parking na miejscu (z procedury trasy).")
    if a.z_dzieckiem and fold(a.okazja or "") not in ("plac_zabaw", "spacer"):
        h.append("Dziecko: czy miejsce ma przewijak, krzesełko, kącik? (procedura miejsca)")
    if "burza" in w.get("flags", []):
        h.append("Burza w oknie wyjścia: rozważ przesunięcie albo plan B pod dachem.")
    if a.end - a.start >= timedelta(hours=3):
        h.append("Dom: okna, światła, żelazko; Roborock może posprzątać, gdy Was nie ma (HA).")
    if getattr(a, "bagaz", False):
        h.append("Niesiesz bagaż: plecak zamiast torby w ręku.")
    if not w.get("ok"):
        h.append("Pogoda: sprawdzę ponownie dzień wcześniej i rano.")
    return h


def build(a, prof=None, rules=None, weather_data=None, wardrobe=None, with_outfit=True) -> dict:
    prof = prof or load_profile(a.profil)
    if getattr(a, "trasa_json", None):
        with open(a.trasa_json, encoding="utf-8") as f:
            apply_route(a, json.load(f))
    rules = rules or load_rules()
    if weather_data is None and a.pogoda_json:
        with open(a.pogoda_json, encoding="utf-8") as f:
            weather_data = json.load(f)
    if weather_data is None:
        try:
            weather_data = fetch_weather(a.gdzie or prof["dom"], a.start)
        except Exception as e:  # sieć, geokodowanie, za daleko
            weather_data = {"_error": f"brak prognozy ({e})"[:120]}
    w = window_weather(weather_data, a.start, a.end) if "_error" not in weather_data else \
        {"ok": False, "flags": [], "powod": weather_data["_error"], "cieplo_poziom": 3}
    ctx = context(a, prof, w)
    out = {"od": a.start.isoformat(timespec="minutes"), "do": a.end.isoformat(timespec="minutes"),
           "okazja": a.okazja, "miejsce": a.miejsce, "transport": a.transport, "z_dzieckiem": bool(a.z_dzieckiem),
           "pogoda": w, "lista": packing(rules, ctx, prof, a.dodaj), "podpowiedzi": hints(a, w, prof)}
    leave = parse_when(a.wyjazd, a.start.date()) if a.wyjazd else a.start
    out["wyjazd"] = leave.strftime("%H:%M")
    out["szykuj_od"] = (leave - timedelta(minutes=prep_time(a, prof))).strftime("%H:%M")
    if with_outfit:
        wr = wardrobe if wardrobe is not None else load_wardrobe(a.garderoba_json)
        out["stroj"] = outfit(wr, w, a.okazja, prof.get("kto", "filip"))
        out["stroj"]["garderoba"] = "brak spisu" if not wr else f"{len(wr)} rzeczy"
        if a.z_dzieckiem and wr:
            kid = prof.get("dziecko", {}).get("kto", "teos")
            out["stroj_dziecka"] = outfit(wr, w, a.okazja, kid)
    return out


def fmt_outfit(st: dict, title: str) -> list[str]:
    lines = [f"👕 {title} (ciepło {st['poziom']}/5, styl: {st['style'][0]}): {st['ogolnie']}"]
    names = dict(SLOTS)
    for slot, items in st["sloty"].items():
        best = items[0]
        alt = f" (albo: {items[1]['nazwa']})" if len(items) > 1 else ""
        where = f", {best['miejsce']}" if best.get("miejsce") and "nieznane" not in best["miejsce"] else ""
        lines.append(f"  • {names[slot]}: {best['nazwa']}{where}{alt}")
    if st["braki"] and st.get("garderoba") != "brak spisu":
        lines.append("  • W spisie brak pasujących: " + ", ".join(names[s] for s in st["braki"]))
    if st.get("garderoba") == "brak spisu":
        lines.append("  (garderoba jeszcze nie spisana, rada ogólna)")
    return lines


def fmt(out: dict) -> str:
    head = f"🚪 Wyjście {out['od'][8:10]}.{out['od'][5:7]} {out['od'][11:]}–{out['do'][11:]}"
    if out.get("okazja"):
        head += f", {out['okazja'].replace('_', ' ')}"
    lines = [head, weather_line(out["pogoda"]), f"⏰ Szykuj się od {out['szykuj_od']}, wyjście {out['wyjazd']}."]
    if "stroj" in out:
        lines += fmt_outfit(dict(out["stroj"]), "Strój")
    if "stroj_dziecka" in out:
        st = dict(out["stroj_dziecka"], garderoba=out["stroj"]["garderoba"])
        lines += fmt_outfit(st, "Strój dziecka")
    lines.append("🎒 Spakuj:")
    for g, items in out["lista"]:
        lines.append(f"  {g}: " + "; ".join(items))
    if out["podpowiedzi"]:
        lines.append("💡 " + " ".join(out["podpowiedzi"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Przygotowanie do wyjścia z domu")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "lista"):
        p = sub.add_parser(name)
        p.add_argument("--od", required=True, help="początek: 2026-10-31 18:00 | 31.10 18:00 | jutro 18:00 | 18:00")
        p.add_argument("--do", help="koniec (domyślnie +2 h)")
        p.add_argument("--gdzie", help="miasto docelowe dla pogody (domyślnie dom z profilu)")
        p.add_argument("--okazja", help="randka, urodziny, wesele, praca, lekarz, spacer, … (słownik)")
        p.add_argument("--miejsce", default="", help="typy miejsc po przecinku: restauracja,basen,sala_zabaw")
        p.add_argument("--transport", default="", help="po przecinku: auto,komunikacja,taxi,pieszo,rower,hulajnoga,pociag")
        p.add_argument("--z-dzieckiem", action="store_true")
        p.add_argument("--wyjazd", help="godzina wyjścia z domu (z procedury trasy); domyślnie = początek")
        p.add_argument("--dodaj", action="append", default=[], help="dodatkowa rzecz (z miejsca, zaproszenia)")
        p.add_argument("--trasa-json", help="wynik procedury `trasa` (wyjdz_o, odcinki, powrot)")
        p.add_argument("--pogoda-json", help="gotowa prognoza (format weather.open_meteo), zamiast sieci")
        p.add_argument("--garderoba-json", help="wynik `dom.py --json list --cat ubrania`, zamiast wywołania")
        p.add_argument("--profil", help="ścieżka profilu (domyślnie ~/.hermes/autonomy/wyjscie/profil.json)")
        p.add_argument("--json", action="store_true")
    sub.add_parser("slownik")
    a = ap.parse_args(argv)
    if a.cmd == "slownik":
        rules = load_rules()
        miejsca = sorted({m for r in rules["rzeczy"] for m in r.get("gdy", {}).get("miejsce", [])})
        print(json.dumps({"okazje": sorted(STYLE), "miejsca": miejsca, "transport": TRANSPORT, "pogoda": FLAGS},
                         ensure_ascii=False, indent=1))
        return 0
    try:
        a.start = parse_when(a.od)
        a.end = parse_when(a.do, a.start.date()) if a.do else a.start + timedelta(hours=2)
        if a.end <= a.start:
            a.end += timedelta(days=1)
    except ValueError as e:
        print(f"BŁĄD: {e}", file=sys.stderr)
        return 2
    a.miejsce = [m for m in a.miejsce.split(",") if m.strip()]
    a.transport = [t for t in a.transport.split(",") if t.strip()]
    out = build(a, with_outfit=a.cmd == "plan")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=list) if a.json else fmt(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
