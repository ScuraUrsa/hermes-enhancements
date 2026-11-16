"""Plugin Hermesa `bibliografia`: każde web_search / web_extract / browser_navigate przechodzi przez bazę.

- pre_tool_call web_extract: odrzucone i niezmienione linki są wycinane z listy (wszystkie odrzucone = blokada
  z powodem); browser_navigate na odrzucony link = blokada. Ominięcie: dopisz do URL #bib-wymus.
- transform_tool_result web_search: każdy wynik znany z bazy dostaje pole "bib" (werdykt, data, notatka).
- post_tool_call web_extract: zapis wizyty z hashem treści (do wykrywania zmian).
- narzędzie `bibliografia`: ocena źródła, ocena linków, historia, śledzenie decyzji (bez terminala).

Logika i baza: bib.py (ta sama co w skillu research-kit). Wszystko bez tokenów.
"""
import json
import logging
import os
import sys
from pathlib import Path

TU = Path(__file__).resolve().parent
for _k in (TU, Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser() / "research-kit" / "skrypty",
           TU.parents[2] / "skrypty"):
    if (_k / "bib.py").is_file():
        sys.path.insert(0, str(_k))
        break
import bib  # noqa: E402

log = logging.getLogger(__name__)


def _baza():
    return bib.Baza(bib.katalog_bazy())


def _pre(tool_name, args, task_id="", **kwargs):
    try:
        if tool_name == "web_extract" and isinstance(args.get("urls"), list):
            baza = _baza()
            zostaja, odrzucone = [], []
            for url in args["urls"]:
                r = bib.ocen(baza, url, siec=True)
                (odrzucone if r["decyzja"] == "pomin" else zostaja).append((url, r))
            if not odrzucone:
                return None
            powody = "; ".join(f"{u}: {r['powod']}" for u, r in odrzucone)
            if not zostaja:
                return {"action": "block", "message": f"Bibliografia: pomijam odrzucone źródła ({powody}). "
                                                       f"Jeśli naprawdę potrzebne, dopisz do URL #{bib.WYMUS}."}
            log.info("bibliografia: wycięte z web_extract: %s", powody)
            return {"action": "modify", "args": {"urls": [u.replace("#" + bib.WYMUS, "") for u, _ in zostaja]}}
        if tool_name == "browser_navigate" and args.get("url"):
            r = bib.ocen(_baza(), args["url"], siec=True)
            if r["decyzja"] == "pomin":
                return {"action": "block", "message": f"Bibliografia: {r['powod']}. Ominięcie: #{bib.WYMUS}."}
    except Exception as e:  # błąd bazy nie może zatrzymać pracy
        log.warning("bibliografia pre_tool_call: %s", e)
    return None


def _transform(tool_name, args, result, **kwargs):
    if tool_name != "web_search" or not isinstance(result, str):
        return None
    try:
        dane = json.loads(result)
        wyniki = (dane.get("data") or {}).get("web") or []
        baza = _baza()
        zmiana = False
        for w in wyniki:
            n = bib.normalizuj(w.get("url", ""))
            if n not in baza.urls:
                continue
            r = bib.ocen(baza, n, siec=False, zapisuj=False)
            if r["decyzja"] == "otworz" and not r.get("werdykt"):
                continue
            w["bib"] = {k: r[k] for k in ("decyzja", "powod", "notatka") if r.get(k)}
            zmiana = True
        return json.dumps(dane, ensure_ascii=False) if zmiana else None
    except Exception as e:
        log.warning("bibliografia transform_tool_result: %s", e)
        return None


def _post(tool_name, args, result, **kwargs):
    if tool_name != "web_extract" or not isinstance(result, str):
        return
    try:
        dane = json.loads(result)
        baza = _baza()
        for w in dane.get("results") or []:
            if w.get("url") and not w.get("error"):
                baza.zapisz(typ="wizyta", url=bib.normalizuj(w["url"]), tytul=(w.get("title") or "")[:200],
                            hash=bib.hash_tresci(w.get("content") or ""), narzedzie="web_extract")
    except Exception as e:
        log.warning("bibliografia post_tool_call: %s", e)


SCHEMA = {
    "name": "bibliografia",
    "description": (
        "Baza bibliografii: pamięć wszystkich źródeł. Akcje: 'ocena' zapisuje werdykt o źródle po jego użyciu "
        "(uzyteczne/neutralne/odrzucone + powód + krótka notatka do ponownego użycia); 'ocen' mówi, czy warto "
        "otwierać linki; 'historia' pokazuje, co wiemy o linku; 'decyzja' zapisuje decyzję i jej źródła do "
        "okresowego sprawdzania (klasy: na-zywo 15 min, krytyczna 1 h, ceny/news 1 dzień, zwykla 7 dni, kod 30 dni)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "akcja": {"type": "string", "enum": ["ocena", "ocen", "historia", "decyzja"]},
            "url": {"type": "string"},
            "urls": {"type": "array", "items": {"type": "string"}},
            "werdykt": {"type": "string", "enum": list(bib.WERDYKTY)},
            "powod": {"type": "string"},
            "notatka": {"type": "string", "description": "1–3 zdania z treści, do użycia bez otwierania strony"},
            "temat": {"type": "string"},
            "przebieg": {"type": "string"},
            "id": {"type": "string", "description": "ID decyzji, np. K76-1"},
            "tytul": {"type": "string"},
            "link": {"type": "string"},
            "klasa": {"type": "string", "enum": sorted(bib.KLASY_MIN)},
        },
        "required": ["akcja"],
    },
}


def _narzedzie(params, **kwargs):
    baza = _baza()
    a = params.get("akcja")
    try:
        if a == "ocena":
            z = baza.zapisz(typ="ocena", url=bib.normalizuj(params["url"]), werdykt=params["werdykt"],
                            powod=(params.get("powod") or "")[:300], notatka=(params.get("notatka") or "")[:600],
                            temat=params.get("temat"), przebieg=params.get("przebieg"))
            return json.dumps({"success": True, "zapisane": z}, ensure_ascii=False)
        if a == "ocen":
            urls = params.get("urls") or [params["url"]]
            return json.dumps({"success": True, "wyniki": [bib.ocen(baza, u, siec=True) for u in urls]}, ensure_ascii=False)
        if a == "historia":
            return json.dumps({"success": True, "historia": baza.urls.get(bib.normalizuj(params["url"]))}, ensure_ascii=False)
        if a == "decyzja":
            urls = [bib.normalizuj(u) for u in params.get("urls") or []]
            if not urls:
                return json.dumps({"success": False, "error": "decyzja wymaga listy urls (źródeł)"})
            baza.zapisz(typ="decyzja", id=params["id"], tytul=params.get("tytul", ""), link=params.get("link"),
                        klasa=params.get("klasa", "zwykla"))
            for u in urls:
                r = bib.sprawdz_siec(u)
                baza.zapisz(typ="zrodlo_decyzji", id=params["id"], url=u, hash=r.get("hash"), etag=r.get("etag"), lm=r.get("lm"))
            return json.dumps({"success": True, "id": params["id"], "zrodla": len(urls)}, ensure_ascii=False)
    except KeyError as e:
        return json.dumps({"success": False, "error": f"brak parametru {e}"})
    return json.dumps({"success": False, "error": f"nieznana akcja {a}"})


def register(ctx):
    ctx.register_hook("pre_tool_call", _pre)
    ctx.register_hook("transform_tool_result", _transform)
    ctx.register_hook("post_tool_call", _post)
    ctx.register_tool(name="bibliografia", toolset="bibliografia", schema=SCHEMA, handler=_narzedzie)
