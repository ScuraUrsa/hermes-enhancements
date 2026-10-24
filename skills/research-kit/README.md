# research-kit

Jeden pakiet skilli (format [Agent Skills](https://agentskills.io/specification)) dla Hermesa i Claude Code:
sztywna procedura researchu w 8 krokach, pliki typów (wiedza, decyzja techniczna, zakupy, wycieczka, randka,
osoba/firma, zdrowie/prawo/finanse, monitoring), standard raportu z walidatorem oraz **baza bibliografii**,
która pamięta każdy link i źródła każdej decyzji.

Plan i decyzje: `plany/research/2026-10-23-standaryzacja-researchu/plan.md` (K76), `plany/decyzje.md`
(2026-10-24). Typy rozwijają wątki K77 (randki), K78 (wycieczki), K79 (zakupy), K80 (standard raportu).

## Zawartość

| Ścieżka | Co |
|---|---|
| `SKILL.md` | rdzeń: 8 kroków, tryby, bibliografia, router typów |
| `typy/*.md` | pytania startowe, pola obowiązkowe, źródła, świeżość, wyjście dla typu |
| `szablony/` | `raport.md` + `standard-raportu.md` (K80) |
| `kontekst/filip.md` | stałe preferencje bez danych wrażliwych |
| `skrypty/bib.py` | baza bibliografii (stdlib, bez tokenów) |
| `skrypty/waliduj_raport.py`, `eksport_raportu.py` | walidator i eksport raportu (K80) |
| `integracje/claude-code/` | hak WebFetch/WebSearch → bibliografia + przykład `settings.json` |
| `integracje/hermes/bibliografia/` | plugin Hermesa: haki `web_search`/`web_extract`/`browser_navigate` + narzędzie `bibliografia` |
| `testy/` | `python3 -m unittest discover -s testy -v` |

## Baza bibliografii w skrócie

- Każde otwarcie linku (WebFetch, `web_extract`) zapisuje wizytę z hashem treści; agent po użyciu zapisuje
  werdykt (`uzyteczne` / `neutralne` / `odrzucone`) z powodem i krótką notatką.
- Przed otwarciem `bib.py ocen` mówi bez tokenów: `otworz`, `uzyj-notatki`, `sprawdz-ponownie` albo `pomin`.
  Odrzucony link nie jest otwierany ponownie, chyba że strona się zmieniła (warunkowe GET + hash tekstu) albo
  minęło 180 dni. Wyniki wyszukiwania znane z bazy dostają adnotację z werdyktem i notatką.
- Decyzje (`bib.py decyzja dodaj`) śledzą swoje źródła; `bib.py sprawdz-decyzje` (cron bez tokenów) sprawdza
  je według klasy: `na-zywo` 15 min, `krytyczna` 1 h, `ceny`/`news` 1 dzień, `zwykla` 7 dni, `kod` 30 dni,
  i oznacza decyzję `do-przegladu`, gdy źródło się zmieniło albo zniknęło.
- Przechowywanie: `zdarzenia/<pisarz>.jsonl` w katalogu bazy (każda maszyna i sesja pisze do swojego pliku,
  więc kopie łączy się kopiowaniem plików). Hermes: `~/.hermes/bibliografia`; wątki Claude w projekcie:
  `BIB_DIR=/mnt/project-files/bibliografia`.

## Instalacja

- **Hermes (prod):** rola WOBI `research_kit` kopiuje katalog do `~/.hermes/research-kit`, dopisuje go do
  `skills.external_dirs`, instaluje plugin `bibliografia` i cron `bib-sprawdz-decyzje` (no_agent, co 15 min,
  dostarczenie do Matrix).
- **Claude Code:** skopiuj katalog do `~/.claude/skills/research-kit` i dołącz haki z
  `integracje/claude-code/settings.example.json` do `~/.claude/settings.json`; ustaw `BIB_DIR`.
