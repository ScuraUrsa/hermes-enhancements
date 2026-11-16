#!/usr/bin/env python3
"""Hak Claude Code: każde WebFetch / WebSearch przechodzi przez bazę bibliografii (bez tokenów).

- PreToolUse WebFetch: link odrzucony i niezmieniony → odmowa z powodem (ominięcie: dopisz #bib-wymus).
- PostToolUse WebFetch: zapis wizyty z hashem treści; krótka linijka kontekstu tylko dla linków już znanych.
- PostToolUse WebSearch: przy wynikach już znanych z bazy jedna linijka statusu (odrzucone / użyteczne + notatka).

Konfiguracja: settings.json (przykład w settings.example.json obok). Baza: BIB_DIR albo domyślna z bib.py.
Hak nigdy nie blokuje pracy z powodu własnego błędu: wyjątek = cisza i kod 0.
"""
import json
import os
import re
import sys
from pathlib import Path

TU = Path(__file__).resolve().parent
for kandydat in (TU, TU.parent.parent / "skrypty", Path(os.environ.get("BIB_SKRYPTY", "")).expanduser()):
    if (kandydat / "bib.py").is_file():
        sys.path.insert(0, str(kandydat))
        break
import bib  # noqa: E402

MAX_LINII = 8  # tyle linijek statusu przy wynikach wyszukiwania, reszta jest pomijana


def wyjscie(zdarzenie, **pola):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": zdarzenie, **pola}}, ensure_ascii=False))


def tekst_odpowiedzi(odp):
    if isinstance(odp, str):
        return odp
    try:
        return json.dumps(odp, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(odp)


def main():
    we = json.load(sys.stdin)
    zdarzenie, narzedzie = we.get("hook_event_name"), we.get("tool_name")
    wejscie = we.get("tool_input") or {}
    baza = bib.Baza(bib.katalog_bazy())

    if narzedzie == "WebFetch" and wejscie.get("url"):
        url = wejscie["url"]
        if zdarzenie == "PreToolUse":
            r = bib.ocen(baza, url, siec=True)
            if r["decyzja"] == "pomin":
                wyjscie("PreToolUse", permissionDecision="deny",
                        permissionDecisionReason=f"Bibliografia: {r['powod']}. Jeśli naprawdę potrzebne, "
                                                 f"dopisz do URL #{bib.WYMUS}.")
            return
        if zdarzenie == "PostToolUse":
            n = bib.normalizuj(url)
            znane = baza.urls.get(n)
            baza.zapisz(typ="wizyta", url=n, hash=bib.hash_tresci(tekst_odpowiedzi(we.get("tool_response"))),
                        narzedzie="WebFetch")
            if znane and znane.get("werdykt"):
                wyjscie("PostToolUse", additionalContext=(
                    f"Bibliografia: to źródło było już ocenione jako {znane['werdykt']} "
                    f"({(znane['data_oceny'] or '')[:10]}). Po użyciu zapisz werdykt: "
                    f"bib.py ocena URL --werdykt uzyteczne|neutralne|odrzucone --powod …"))
            return

    if narzedzie == "WebSearch" and zdarzenie == "PostToolUse":
        urls = re.findall(r"https?://[^\s\"'<>)\]]+", tekst_odpowiedzi(we.get("tool_response")))
        linie, widziane = [], set()
        for u in urls:
            n = bib.normalizuj(u)
            if n in widziane or n not in baza.urls:
                continue
            widziane.add(n)
            r = bib.ocen(baza, u, siec=False, zapisuj=False)
            if r["decyzja"] == "otworz" and not r.get("werdykt"):
                continue
            opis = f"{r['decyzja']}: {r['powod']}"
            if r.get("notatka"):
                opis += f" | notatka: {r['notatka']}"
            linie.append(f"- {n} → {opis}")
            if len(linie) >= MAX_LINII:
                break
        if linie:
            wyjscie("PostToolUse", additionalContext="Bibliografia (znane wyniki):\n" + "\n".join(linie))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # hak nie może zatrzymać pracy agenta
        pass
    sys.exit(0)
