#!/usr/bin/env python3
"""Inwentarz kont/serwisów założonych na adresy Gmail Filipa, bez LLM.

Jak oszczędza tokeny: nie czyta treści maili. Pobiera z Gmail API wyłącznie nagłówki
(format=metadata: From, To, Delivered-To, Subject, Date, List-Unsubscribe) wszystkich
przychodzących wiadomości, partiami po 50 (batch), z wznawianiem z SQLite. Potem lokalnie:
grupuje po domenie nadawcy (eTLD+1), szuka w tematach sygnałów „mam tu konto” (witamy,
potwierdź e-mail, reset hasła, logowanie, kod 2FA, zamówienie, regulamin) i liczy pewność.

Uruchomienie (na prod, venv Hermesa, tokeny z ~/.hermes/google-accounts/<alias>/google_token.json):
  python3 konta_z_maili.py pobierz [--konta a,b] [--limit N]   # nagłówki -> konta.sqlite (wznawialne)
  python3 konta_z_maili.py raport  [--wyj katalog]              # CSV + podsumowanie.md

Konto służbowe Hitachi Energy jest zawsze pomijane (reguła Filipa z 24.10).
Tylko odczyt (scope gmail.readonly wystarcza). Nie zapisuje treści ani sekretów; ciągi cyfr
w tematach (kody weryfikacyjne) są maskowane.
"""
import argparse, collections, csv, datetime as dt, email.utils, json, os, re, sqlite3, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("HERMES_GACCTS", Path.home() / ".hermes/google-accounts"))
DB = Path(os.environ.get("KONTA_DB", Path.home() / ".hermes/konta-z-maili/konta.sqlite"))
POMIN = re.compile(r"hitachi", re.I)
HEADERS = ["From", "To", "Delivered-To", "Subject", "Date", "List-Unsubscribe"]
QUERY = "-in:sent -in:chats -in:drafts"

# --- sygnały w tematach (PL + EN); waga: 3 = konto prawie pewne, 2 = prawdopodobne, 1 = słaby
SYGNALY = [
    ("rejestracja", 3, r"welcome|witamy|witaj w|dziękujemy za rejestracj|thanks for (signing|joining|registering)|account (created|has been created)|konto (zostało )?(utworzone|założone)|rejestracj|registration|sign(ed)? ?up|get started|zaczynamy|aktywuj|activate"),
    ("weryfikacja", 3, r"verif|weryfik|potwierd[źz]|confirm (your )?(e-?mail|account|address|registration)|potwierdzenie (adresu|rejestracji|e-?mail)"),
    ("haslo", 3, r"password|hasł|haslo|reset|odzyskiw|recover"),
    ("logowanie", 3, r"sign[- ]?in|log[- ]?in|logowani|zalogow|new device|nowe urządzen|nowego urządzen|security alert|alert bezpiecze|unusual activity|nietypow|access(ed)? your account|dostęp do konta"),
    ("kod", 3, r"\bcode\b|\bkod\b|one[- ]time|jednorazow|2fa|two[- ]factor|dwuetap|otp"),
    ("konto", 2, r"your account|twoje konto|twojego konta|account (update|settings|change)|zmiany? (na|w) koncie|profil|profile|usunięci[ea] konta|delete (your )?account|account (deletion|closure)"),
    ("regulamin", 2, r"terms|regulamin|privacy policy|polityk[ai] prywatno|warunk|zmiany w dokument|umow"),
    ("zakup", 2, r"order|zamówieni|zamowieni|receipt|paragon|faktur|invoice|payment|płatno|platnosc|subscription|subskrypc|abonament|renew|odnowieni|trial|okres próbny|booking|rezerwac|bilet|ticket|przesyłk|shipment|dostaw"),
]
SYG_RE = [(n, w, re.compile(p, re.I)) for n, w, p in SYGNALY]

# Skrzynki osób prywatnych i ogólne domeny pocztowe — nie są „serwisem”, chyba że mają sygnały.
POCZTA_OSOB = {"gmail.com", "googlemail.com", "wp.pl", "o2.pl", "onet.pl", "onet.eu", "op.pl", "interia.pl",
               "interia.eu", "poczta.fm", "tlen.pl", "gazeta.pl", "yahoo.com", "outlook.com", "hotmail.com",
               "live.com", "icloud.com", "me.com", "proton.me", "protonmail.com", "gmx.com", "gmx.de", "vp.pl"}
# Domeny pośredników wysyłki — nazwę serwisu bierzemy wtedy z nazwy wyświetlanej nadawcy.
POSREDNICY = {"sendgrid.net", "mailchimp.com", "mcsv.net", "mandrillapp.com", "amazonses.com", "sparkpostmail.com",
              "mailgun.org", "hubspotemail.net", "sendinblue.com", "brevo.com", "freshdesk.com", "zendesk.com",
              "intercom-mail.com", "customer.io", "postmarkapp.com", "cmail19.com", "cmail20.com", "rsgsv.net",
              "list-manage.com", "e-mail.pl", "getresponse.com", "salesmanago.pl", "facebookmail.com"}
DWUCZLONOWE = {"co.uk", "com.pl", "net.pl", "org.pl", "edu.pl", "gov.pl", "waw.pl", "com.au", "co.jp", "com.br",
               "co.nz", "co.in", "com.tr", "com.cn", "org.uk", "ac.uk", "gov.uk", "co.za", "com.mx", "com.ua"}


def domena_glowna(adres):
    host = adres.rsplit("@", 1)[-1].lower().strip(" >.")
    czesci = host.split(".")
    if len(czesci) >= 3 and ".".join(czesci[-2:]) in DWUCZLONOWE:
        return ".".join(czesci[-3:])
    return ".".join(czesci[-2:])


def maskuj(t):
    return re.sub(r"\d{4,}", "####", t or "")[:160]


# ---------------------------------------------------------------- pobieranie
def usluga(alias):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    tok = ROOT / alias / "google_token.json"
    creds = Credentials.from_authorized_user_file(str(tok))
    if not creds.valid:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def baza():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""create table if not exists m(konto text, id text, watek text, ts integer, od text, od_nazwa text,
                 do_ text, delivered text, temat text, unsub integer, primary key(konto,id))""")
    c.execute("create table if not exists ids(konto text, id text, primary key(konto,id))")
    c.execute("create table if not exists stan(konto text primary key, adres text, listing_ok integer)")
    return c


def konta(arg):
    wszystkie = sorted(p.name for p in ROOT.iterdir() if (p / "google_token.json").exists())
    wybrane = [a for a in (arg.split(",") if arg else wszystkie) if a]
    return [a for a in wybrane if not POMIN.search(a)]


def pobierz(args):
    c = baza()
    for alias in konta(args.konta):
        s = usluga(alias)
        adres = s.users().getProfile(userId="me").execute()["emailAddress"]
        if POMIN.search(adres):
            print(f"[{alias}] pomijam konto służbowe"); continue
        c.execute("insert or replace into stan(konto,adres,listing_ok) values(?,?,coalesce((select listing_ok from stan where konto=?),0))", (alias, adres, alias))
        if not c.execute("select listing_ok from stan where konto=?", (alias,)).fetchone()[0]:
            tok, n = None, 0
            while True:
                r = s.users().messages().list(userId="me", q=QUERY, maxResults=500, pageToken=tok).execute()
                c.executemany("insert or ignore into ids values(?,?)", [(alias, m["id"]) for m in r.get("messages", [])])
                n += len(r.get("messages", [])); c.commit()
                print(f"[{alias}] lista id: {n}", flush=True)
                tok = r.get("nextPageToken")
                if not tok or (args.limit and n >= args.limit): break
            c.execute("update stan set listing_ok=1 where konto=?", (alias,)); c.commit()
        brak = [r[0] for r in c.execute("select id from ids where konto=? and id not in (select id from m where konto=?)", (alias, alias))]
        if args.limit: brak = brak[: args.limit]
        print(f"[{alias}] {adres}: do pobrania nagłówków {len(brak)}", flush=True)
        pobierz_naglowki(s, c, alias, brak)
    c.close()


def pobierz_naglowki(s, c, alias, ids):
    from googleapiclient.errors import HttpError
    kolejka, zrobione, przerwa = list(ids), 0, 1.2  # 50 x 5 jednostek / partia; limit 15000/min
    while kolejka:
        partia, kolejka = kolejka[:50], kolejka[50:]
        wyniki, bledy = [], []

        def cb(rid, resp, exc):
            if exc is not None:
                bledy.append(rid); return
            h = {x["name"].lower(): x["value"] for x in resp.get("payload", {}).get("headers", [])}
            nazwa, od = email.utils.parseaddr(h.get("from", ""))
            wyniki.append((alias, resp["id"], resp.get("threadId"), int(resp.get("internalDate", 0)) // 1000,
                           od.lower(), nazwa[:120], h.get("to", "")[:300], h.get("delivered-to", "")[:120],
                           maskuj(h.get("subject", "")), 1 if "list-unsubscribe" in h else 0))

        b = s.new_batch_http_request(callback=cb)
        for mid in partia:
            b.add(s.users().messages().get(userId="me", id=mid, format="metadata", metadataHeaders=HEADERS), request_id=mid)
        try:
            b.execute()
        except HttpError as e:
            print(f"[{alias}] HttpError {e.status_code}, czekam 30 s", flush=True)
            kolejka = partia + kolejka; time.sleep(30); continue
        c.executemany("insert or replace into m values(?,?,?,?,?,?,?,?,?,?)", wyniki); c.commit()
        zrobione += len(wyniki)
        if bledy:  # zwykle 429 (limit): zwolnij i dołóż błędne na koniec kolejki
            przerwa = min(przerwa * 2, 30); kolejka += bledy
        else:
            przerwa = max(1.2, przerwa * 0.8)
        if zrobione % 1000 < 50:
            print(f"[{alias}] nagłówki {zrobione}, zostało {len(kolejka)}, przerwa {przerwa:.1f} s", flush=True)
        time.sleep(przerwa)


# ---------------------------------------------------------------- raport
def raport(args):
    c = baza()
    wyj = Path(args.wyj); wyj.mkdir(parents=True, exist_ok=True)
    adresy = dict(c.execute("select konto, adres from stan"))
    grupy = collections.defaultdict(lambda: {"n": 0, "pierwszy": 9e18, "ostatni": 0, "syg": collections.Counter(),
                                             "nazwy": collections.Counter(), "nadawcy": collections.Counter(),
                                             "do": collections.Counter(), "przyklad": None, "przyklad_w": 0, "unsub": 0})
    for konto, mid, watek, ts, od, nazwa, do_, deliv, temat, unsub in c.execute("select * from m"):
        if not od or "@" not in od: continue
        dom = domena_glowna(od)
        klucz_dom = dom
        if dom in POSREDNICY and nazwa:
            klucz_dom = f"{dom}:{nazwa.lower()[:40]}"
        elif dom in POCZTA_OSOB:
            klucz_dom = f"{dom}:{od}"
        g = grupy[(adresy.get(konto, konto), klucz_dom)]
        g["n"] += 1; g["pierwszy"] = min(g["pierwszy"], ts); g["ostatni"] = max(g["ostatni"], ts)
        g["nazwy"][nazwa] += 1; g["nadawcy"][od] += 1; g["unsub"] += unsub
        for a in email.utils.getaddresses([do_, deliv]):
            if a[1]: g["do"][a[1].lower()] += 1
        wmax = 0
        for n, w, rx in SYG_RE:
            if rx.search(temat):
                g["syg"][n] += 1; wmax = max(wmax, w)
        if wmax > g["przyklad_w"] or g["przyklad"] is None:
            g["przyklad"], g["przyklad_w"] = (temat, watek, konto), wmax

    wiersze = []
    for (adres, dom), g in grupy.items():
        wagi = {n: w for n, w, _ in SYGNALY}
        mocne = sum(v for k, v in g["syg"].items() if wagi[k] == 3)
        srednie = sum(v for k, v in g["syg"].items() if wagi[k] == 2)
        osoba = dom.split(":")[0] in POCZTA_OSOB
        if mocne: pewnosc = "konto prawie pewne"
        elif srednie: pewnosc = "konto prawdopodobne"
        elif osoba: pewnosc = "osoba prywatna"
        elif g["unsub"]: pewnosc = "newsletter (konto możliwe)"
        else: pewnosc = "inne"
        temat, watek, konto = g["przyklad"]
        wiersze.append({
            "adres_filipa": adres, "domena": dom.split(":")[0], "serwis": g["nazwy"].most_common(1)[0][0] or dom,
            "pewnosc": pewnosc, "sygnaly": " ".join(f"{k}:{v}" for k, v in g["syg"].most_common()),
            "maili": g["n"], "pierwszy": dt.date.fromtimestamp(g["pierwszy"]).isoformat(),
            "ostatni": dt.date.fromtimestamp(g["ostatni"]).isoformat(),
            "nadawca": g["nadawcy"].most_common(1)[0][0],
            "wyslane_na": ";".join(a for a, _ in g["do"].most_common(3)),
            "przyklad_temat": temat,
            "link": f"https://mail.google.com/mail/?authuser={adres}#all/{watek}",
        })
    rank = {"konto prawie pewne": 0, "konto prawdopodobne": 1, "newsletter (konto możliwe)": 2, "inne": 3, "osoba prywatna": 4}
    wiersze.sort(key=lambda r: (r["adres_filipa"], rank[r["pewnosc"]], -r["maili"]))
    pola = list(wiersze[0].keys()) if wiersze else []
    with open(wyj / "konta-wszystko.csv", "w", newline="") as f:
        w = csv.DictWriter(f, pola); w.writeheader(); w.writerows(wiersze)
    konta_csv = [r for r in wiersze if r["pewnosc"] in ("konto prawie pewne", "konto prawdopodobne")]
    with open(wyj / "konta.csv", "w", newline="") as f:
        w = csv.DictWriter(f, pola); w.writeheader(); w.writerows(konta_csv)

    # podsumowanie
    L = [f"# Konta z maili: podsumowanie ({dt.date.today().isoformat()})", ""]
    L += ["| Adres | Maili przejrzanych (nagłówki) | Konto prawie pewne | Prawdopodobne | Newsletter | Osoby |", "|---|---|---|---|---|---|"]
    for konto, adres in adresy.items():
        n = c.execute("select count(*) from m where konto=?", (konto,)).fetchone()[0]
        cnt = collections.Counter(r["pewnosc"] for r in wiersze if r["adres_filipa"] == adres)
        L.append(f"| {adres} | {n} | {cnt['konto prawie pewne']} | {cnt['konto prawdopodobne']} | {cnt['newsletter (konto możliwe)']} | {cnt['osoba prywatna']} |")
    # serwisy na kilku adresach
    wiele = collections.defaultdict(set)
    for r in konta_csv: wiele[r["domena"]].add(r["adres_filipa"])
    dup = sorted(d for d, s in wiele.items() if len(s) > 1)
    L += ["", f"Serwisy z kontem na więcej niż jednym adresie: {len(dup)}", "", ", ".join(dup) or "brak"]
    (wyj / "podsumowanie.md").write_text("\n".join(L) + "\n")
    print("\n".join(L)); print(f"\nZapisano: {wyj}/konta.csv, konta-wszystko.csv, podsumowanie.md")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("pobierz"); a.add_argument("--konta"); a.add_argument("--limit", type=int)
    b = sp.add_parser("raport"); b.add_argument("--wyj", default=str(DB.parent / "raport"))
    args = p.parse_args()
    {"pobierz": pobierz, "raport": raport}[args.cmd](args)
