# wyjscie — przygotowanie do wyjścia z domu

Procedura Hermesa (prośba Filipa 25.10, kolejka K108): przed każdym wyjściem sprawdza pogodę w oknie wyjścia,
okazję i z kim się widzimy, środek transportu (z procedury `trasa`, K107), podsuwa strój z tego, co jest
w garderobie, i układa listę do spakowania (osobna długa lista z dzieckiem). Używają jej `randka` (K77),
`wycieczka` (K78) i timeplane; sama nie szuka miejsc (`miejsca`, K106) ani tras.

| Plik | Wdrożenie na prod |
|---|---|
| `wyjscie.py` | `~/.hermes/scripts/wyjscie.py` (755), obok `weather.py` i `dom.py` |
| `listy.json` | `~/.hermes/scripts/listy.json` (obok skryptu) |
| `SKILL.md` | `~/.hermes/skills/productivity/wyjscie/SKILL.md` |

- Tylko biblioteka standardowa (Python 3.10+). Bez nowych usług, bez kluczy API, bez LLM w skrypcie.
- Pogoda: importuje `weather.py` (Open-Meteo, godzinowo w oknie od–do, do 16 dni naprzód; zapasowo wttr.in).
- Garderoba: `dom.py --json list --cat ubrania`; atrybuty w notatce rzeczy (`typ: ciepło: styl: woda: kto: kolor: stan:`).
- Profil prywatny: `~/.hermes/autonomy/wyjscie/profil.json` (`$WYJSCIE_PROFIL`), w backupie `~/.hermes`.
- Reguły listy: `listy.json` (warunki `gdy` / `chyba_ze` po flagach pogody, okazji, miejscu, transporcie, dziecku,
  długości wyjścia). To jedyna lista „co zabrać wg rodzaju miejsca”; `miejsca` dopisuje tylko wymagania
  konkretnego obiektu przez `--dodaj`.

```
wyjscie.py plan --od "31.10 18:00" --do 23:00 --okazja randka --miejsce restauracja,teatr --trasa-json trasa.json
wyjscie.py lista --od "jutro 10:00" --do 13:00 --z-dzieckiem --miejsce basen --transport auto
wyjscie.py slownik
```

Kody wyjścia: 0 ok, 1 błąd, 2 zła data. `--json` dla innych procedur. Testy: `python3 -m pytest -q wyjscie/`.

Deploy: `scp wyjscie.py listy.json SKILL.md ubuntu@<vm>:/tmp/ && ssh ubuntu@<vm> 'install -m 755 /tmp/wyjscie.py ~/.hermes/scripts/ && install -m 644 /tmp/listy.json ~/.hermes/scripts/ && install -Dm 644 /tmp/SKILL.md ~/.hermes/skills/productivity/wyjscie/SKILL.md'`
(docelowo rola w WOBI razem z `weather` i `home-inventory`).
