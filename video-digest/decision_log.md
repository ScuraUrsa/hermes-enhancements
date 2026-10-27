# Decision log: video-digest (MCP bridge tests, 2026-10-27)

**Zadanie.** Karta `t_449b1bb1` (C2 run52): `ytdigest/mcp_bridge.py` miało zero testów
(62 instrukcje, 58 % pokrycia) mimo że to most, przez który Claude Desktop/Hermes na laptopie
Filipa woła `digest_youtube_video` i `get_youtube_report` na VM przez Tailscale. Cel: ≥ 90 %
pokrycia i dowód, że kontrakt nie pęknie przy refaktorze.

**Decyzje.**

- Kontrakt pinujemy **substytucją, nie uruchamianiem serwera**: `urllib.request.urlopen` jest
  podmieniany na rekorder żądań, `time` na zegar udający (`.sleep` tylko zapisuje), `os.environ`
  przez `monkeypatch`. Żadnego `ytdigest serve`, żadnego Tailscale w testach — plik 48 testów
  wykonuje się w 0,07 s, więc nikt go nie wyłączy jako „za wolny”.
- Hermetyczność jest **osobnym testem, nie założeniem**: `test_bridge_opens_no_sockets_during_a_full_digest`
  twardo blokuje `socket.socket` i `socket.create_connection` i przeprowadza pełny digest.
  Gdyby rekorder kiedyś przestał przechwytywać, ten test pada zamiast cicho iść do sieci.
- Rozszerzyłem `tests/test_mcp_bridge.py`, nie `ytdigest/mcp_bridge.py`: jedyna zmiana produkcyjna
  to bugfix `wait_seconds=0` (niżej). Publiczny schemat `TOOLS` nietknięty — Claude Desktop ma
  zapisane te schematy u siebie na laptopie.
- Testy ujawniły realny defekt i **został naprawiony osobnym commitem**, zgodnie z zakresem pkt 2
  karty: `deadline = time.time() + int(args.get("wait_seconds") or 600)` traktował jawne `0`
  („zakolejkuj i wróć od razu”) jak brak wartości — model dostawał 600 s i 40 × `GET /report`
  co 15 s, blokując proces stdio (a więc i wywołanie narzędzia w Claude Desktop) na 10 minut.
  Teraz tylko *brak* `wait_seconds` daje 600; `0` i wartości ujemne znaczą „nie czekaj”.
- Mutacje jako dowód, że testy mają zęby: 10/10 zabitych (nie 5 wymaganych), każda z nazwanym
  czerwonym testem — tabela w PR. Runner mutacji był jednorazowy (skrypt w `/tmp`, nie w repo):
  nie jest testem, a commitowanie go wymagałoby utrzymywania listy mutacji przy każdej zmianie mostu.
- Nie tworzę `docs/` ani innych plików projektu poza tym logiem — karta zabrania zmian w innych
  modułach.

**Pomiar (ten sam interpreter `/home/ubuntu/crewai-orchestrator/.venv/bin/python`).**

| | `mcp_bridge.py` | suite |
|---|---|---|
| PRZED (`547740a`, bez nowego pliku) | 62 stmts, 26 miss, **58 %** | 84 passed, 1 skipped, 16,1 s |
| PO (`wt/c2-mcp-bridge-tests`) | 63 stmts, 0 miss, **100 %** | 132 passed, 1 skipped, 15,8 s |

Punkt wyjścia zgadza się z pomiarem plannera (58 %, 62 instrukcje) — różnica 63 stmt „po” to jedna
linia dodana przez bugfix.

**Czego świadomie nie ma.** Testów integracyjnych z prawdziwym `ytdigest serve` (wymagałyby VM,
Tailscale i YouTube quota — osobna klasa ryzyka, nie ta karta) i testów ramki MCP na żywym kliencie
Claude Desktop (nie da się uruchomić w CI). Kontrakt na drucie jest pinowany, transport realny nie.

**Następne kroki.** Merge tylko Filip (brama człowieka). Po merge warto powtórzyć pomiar pokrycia
całego `ytdigest` — `mcp_bridge.py` przestał być najsłabszym ogniwem; kolejne kandydatki to moduły
z poprzednich kart C2 pozostawione w `blocked` (`transcript.py`, `notion.py`, `discover.py`).
