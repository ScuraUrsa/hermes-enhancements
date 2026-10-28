# API — `video-digest` (`ytdigest` + `sitedigest`)

Powierzchnia publiczna projektu `video-digest`: dwa CLI, most MCP, serwer HTTP, kontrakt
manifestu archiwum oraz konfiguracja i zależności. Wszystko poniżej sprawdzone na kodzie
z gałęzi `wt/t_f9f61629` (baza `37513c4`) i uruchomione 2026-10-28 na VM `hermes-vm-1`
(Python 3.10.12; `pytest tests/ -q` → **83 passed in 45.31s**; mostek MCP sprawdzony
`initialize` + `tools/list`, serwer HTTP sprawdzony curlem na portach 8799 i 8801).

Uruchamiaj z katalogu `video-digest/` — `-m ytdigest` działa tylko przy `cwd` w tym
katalogu (lokalna kopia pakietu przesłania zainstalowaną).

> **Zero sekretów w plikach.** Klucze i tokeny przychodzą wyłącznie ze środowiska
> (Hermes wczytuje je z Bitwarden do `~/.hermes/.env`); `config.py` nigdy ich nie czyta z YAML-a.

Nawigacja: [1 CLI `ytdigest`](#1-cli-ytdigest) · [2 CLI `sitedigest`](#2-cli-sitedigest) ·
[3 MCP i HTTP](#3-most-mcp-i-serwer-http) · [4 Manifest](#4-kontrakt-manifestu-archiwum) ·
[5 Konfiguracja](#5-konfiguracja-i-zależności) · [6 Dalej](#6-gdzie-szukać-dalej)

## 1. CLI `ytdigest`

Wejście: `python -m ytdigest <komenda>`. Globalny `--config ŚCIEŻKA` (opcjonalny).
Oznaczenia: `*` — komenda uruchomiona naprawdę; `†` — zweryfikowana przez `--help`
(mutuje kolejkę/zużywa model albo wymaga sieci i logowania konta).

| Komenda | Co robi | Efekt (pliki / API) |
|---|---|---|
| `run URL` `*` | Przetwarza jedno wideo teraz: transkrypt → ramki → klasyfikacja → raport (pomija Notion z `--no-notion`; `--analyzer {gemini_url,frames}` wymusza analizę; `--json` drukuje wynik jako JSON, bez `trace`) | `data_dir/bundles/<video_id>/{bundle.json,frames/,report.json,report.md}`; przy sukcesie wiersz w `queue.db` (`USER_PRIORITY` = 100, konto „ręcznie”, uzupełnione `status`/`notion_url`/`cost_usd`), opcjonalnie strona Notion; raport Markdown na stdout, rc=0. Błąd: baner `FAILED <id>: ValueError: not a YouTube video link: …` + traceback na stderr, rc=1, bez wpisu do kolejki (zmierzone na `run notaurl`) |
| `add [URL...]` `†` | Tylko kolejkuje, nie przetwarza (`--file` = lista URL/ID, `#` komentuje; `--account`, `--playlist`) | `queue.db`: `--now` → 100, `--backlog` lub `--file` → 10, samo `add` → 30 |
| `compare [URL...]` `†` | Te same filmy przez kilka modeli, obok siebie (`--refs a,b`, `--file`, `--notion-parent`, `--title`) | `data_dir/compare/<YYYYMMDD-HHMM>/<model>/…` + `results.json` i `comparison.md` |
| `discover` `*` | Ostatnie filmy z kanałów/subskrypcji do TSV; zero wywołań modeli (`--days`, `--no-subs`, `--skip-shorts`, `--min-seconds`, `--max-per-channel`, `--ids-file`, `--out`, `--queue`) | `data_dir/discover_<account>_<days>d.tsv` (nagłówek `video_id published seconds channel title source`); `--queue` = priorytet 5 (za całym backlogiem). U nas: `{'channels': 0, 'videos': 0 …}` — ciasteczka konta nie mają subskrypcji, więc TSV wychodzi pusty |
| `categorize INPUT --out OUT` `*` | Sortuje wynik `discover` do kategorii heurystycznych (`--min-score`, domyślnie 3); zero wywołań modeli | `OUT/ai_software.txt` (per kategoria), `OUT/categories.json`, `OUT/categorized.jsonl` + podsumowanie wideo/godzin na stdout |
| `rerender` `†` | Przebudowuje `report.md` (i stronę Notion) z zapisanych bundle'ów bieżącym szablonem (`--video`, `--data-dir`, `--notion`, `--refetch`) | nadpisuje `report.md` w bundlu; sieci nie dotyka, chyba że `--refetch` — wtedy dociąga sam opis wideo, gdy bundel go nie ma |
| `worker` `†` | Przetwarza kolejkę (`--idle-only` = brama bezczynności, `--only-user` = same priorytety 100, `--max-videos`, `--max-minutes`) | te same artefakty co `run`; jeden ciężki job naraz (8 GB RAM) |
| `backlog-sync` `†` | Uzupełnia kolejkę z YouTube Data API i Watch Later przez yt-dlp (`--account`) | wiersze w `queue.db`, priorytet 10. **Nie uruchamiane tutaj** — mutuje żywą kolejkę |
| `gate` `*` | Drukuje decyzję bramy: `OPEN`/`CLOSED` + 6 powodów w kolejności (tryb quota, własny cap wydatków, aktywność Filipa, jego zadania, obciążenie maszyny, budżet self) | tylko czyta; zmierzone `CLOSED` (powód: `NO self budget spent`) z kodem wyjścia 1 |
| `status` `*` | JSON: liczniki i koszt kolejki per status oraz dzisiejsze wydatki `backlog`/`manual` | tylko czyta `queue.db` i `spend.jsonl`; zmierzone `{"queue": {"artistic": {…}, "done": {…}}, "backlog_spend_today_usd": 0.0, "manual_spend_today_usd": 0.0}` |
| `serve` `*` | Serwer HTTP dla jednego kliknięcia (`--host`, domyślnie `127.0.0.1`; `--port`, domyślnie 8765) | nasłuchuje; wymaga `YTDIGEST_TOKEN` i odmawia `0.0.0.0` — patrz §3 |

Przykłady (te przebiegi były wykonane naprawdę; `run` pełnego pipeline'u nie uruchamiałem —
brama była `CLOSED`, koszt modeli):

```bash
cd video-digest
P=~/.hermes/ytdigest/venv/bin/python
$P -m ytdigest status                                        # JSON z licznikami kolejki
$P -m ytdigest gate                                          # CLOSED + 6 powodów, rc=1
$P -m ytdigest discover --account koalamis6 --days 2 --max-per-channel 3 --out /tmp/disc.tsv
$P -m ytdigest categorize /tmp/disc.tsv --out /tmp/kategorie   # ai_software.txt, categories.json
$P -m ytdigest run notaurl --no-notion                        # ścieżka błędu: FAILED …, rc=1
$P -m ytdigest serve --host 127.0.0.1 --port 8799              # HTTP (wymaga YTDIGEST_TOKEN)
```

## 2. CLI `sitedigest`

Wejście: `python -m sitedigest <komenda>`; globalny `--config`. Czyta ten sam plik co
`ytdigest` plus sekcję `site:`; dane trzyma per witryna w `<root>/<site>/`
(`root` = `~/.hermes/sitedigest`). Oznaczenia jak w §1: `*` uruchomione naprawdę,
`†` tylko `--help` (pełny `run`/`pool` = crawl + LLM + Notion, więc nie w tej karcie).

| Komenda | Co robi | Efekt |
|---|---|---|
| `login URL` `†` (`--site`, `--auto`) | Jednorazowe logowanie w widocznej przeglądarce | zapisana sesja witryny |
| `import-cookies PLIK` `†` (`--site`, `--url`) | Alternatywa: ciasteczka wyeksportowane z przeglądarki | zapisana sesja witryny |
| `map URL` `†` (`--include`, `--exclude`, `--max-pages`, `--host`, `--max-depth`, `--refresh`, `--show`) | Mapuje witrynę; wznawialne | mapa stron/lekcji w `<root>/<site>/` |
| `outline SITE` `*` | Moduły, lekcje, wideo i pliki znalezione na mapie | wydruk na stdout: `# <site>: <start_url>`, potem `N stron, N wideo, N plików, N błędów, N jeszcze nieodwiedzonych` i sekcje `## <kurs> / <moduł>` z liniami `- [lesson] … (1 wideo|tekst) <url>`; zmierzone: 1139 stron / 1121 wideo |
| `fetch SITE` `†` (`--limit`, `--include`, `--redo`, `--show`) | Pobiera wideo i pliki tam, gdzie żyje logowanie | pliki w `<root>/<site>/` |
| `digest SITE` `†` (`--page`, `--limit`, `--model`, `--no-notion`, `--redo`, `--all`) | Analizuje lekcje (tekst, pliki, mowa, obraz) | raport lekcji + strona Notion |
| `pool SITE` `†` (`--workers`, `--model`, `--fallback-model`, `--follow`, `--require-vtt`, `--include`) | Równoległy `digest` ze wspólnej kolejki, bez kolizji | raporty lekcji w partiach |
| `course SITE` `†` | Przegląd kursu z raportów lekcji | strona przeglądu + Notion |
| `run URL` `†` (`--site`, `--include`, `--exclude`, `--max-pages`, `--limit`, `--model`, `--no-notion`) | `map` + `digest` + `course` w jednym przebiegu | komplet raportów witryny |
| `worker` `†` (`--idle-only`, `--max-pages`, `--max-minutes`) | Wszystkie witryny, tylko gdy Hermes jest bezczynny (cron) | przyrostowe raporty |
| `status` `*` | Per witryna: strony, zadigestowane, koszt | lista JSON, po jednym obiekcie na witrynę; zmierzone pola: `site`, `start_url`, `pages`, `mapped`, `queued_to_map`, `lessons_to_digest`, `digested`, `failed`, `videos`, `files`, `cost_usd`, `logged_in` |
| `notion-setup --parent PAGE_ID` `†` | Tworzy bazę „Kursy: lekcje” | ID bazy Notion do konfiguracji |

```bash
P=~/.hermes/ytdigest/venv/bin/python      # z katalogu video-digest/
$P -m sitedigest status                    # [{"site": "akademiasaas-pl", "pages": 1143, … "logged_in": false}]
$P -m sitedigest outline akademiasaas-pl   # drzewo kursów/lekcji z mapy, zero kosztu modeli
$P -m sitedigest run https://przyklad.pl/kurs --limit 3 --no-notion   # (nieuruchamiane tutaj)
$P -m sitedigest pool moj-kurs --workers 3 --follow                   # (nieuruchamiane tutaj)
```

## 3. Most MCP i serwer HTTP

`ytdigest serve` wystawia mały endpoint HTTP (share sheet na telefonie, bookmarklet, mostek
MCP). Token `YTDIGEST_TOKEN` przyjmowany jest jako pole `token` (query przy GET, JSON przy
POST) **albo** `Authorization: Bearer` — to drugie działa tylko dla POST; GET czyta wyłącznie
query, więc `-H 'Authorization: Bearer …'` na `/report` zwraca 401. Porównanie jest
stałoczasowe (`hmac.compare_digest`).

| Metoda | Ścieżka | Odpowiedź (zmierzona na portach 8799 i 8801) |
|---|---|---|
| `GET` | `/health` | `200 {"ok": true}` — jedyna ścieżka bez tokenu |
| `GET`/`POST` | `/digest?url=…` | `202 {"queued": "<video_id>", "priority": "now"}` — przetwarza od razu (priorytet 100, jeden ciężki job naraz przez `threading.Lock`) |
| `GET`/`POST` | `/queue?url=…` | `202 {"queued": "<video_id>", "priority": "backlog"}` — tylko kolejkuje (priorytet 30) |
| `GET`/`POST` | `/report?url=…` | `200 {"video_id", "status", "notion_url", "error"}`, plus `report_md` gdy `status` ∈ {`done`, `artistic`}; zmierzone `{"video_id": "fWjsdhR3z3c", "status": "processing", "notion_url": null, "error": null}` |

Błędy: `401 {"error": "bad token"}`, `400 {"error": "not a YouTube video link: "}`,
`404 {"error": "unknown path"}`. Ścieżka `/status` **nie istnieje** (`status` to komenda CLI):
z tokenem wraca 400, bo nieznana ścieżka wpada w parsowanie parametru `url`.

Zmierzone zachowanie tokenu (curl, `probe-token-123` jako wartość testowa):

```bash
curl -s "$B/health"                                          # 200 {"ok": true}
curl -s "$B/digest?url=https://youtu.be/fWjsdhR3z3c&token=…" # 202 {"queued": "fWjsdhR3z3c", "priority": "now"}
curl -s "$B/queue?url=https://youtu.be/dQw4w9WgXcQ&token=…"  # 202 {"queued": "dQw4w9WgXcQ", "priority": "backlog"}
curl -s -X POST "$B/report" -H 'Authorization: Bearer …' \
     -H 'Content-Type: application/json' -d '{"url":"https://youtu.be/fWjsdhR3z3c"}'   # 200
curl -s "$B/report?url=https://youtu.be/fWjsdhR3z3c" -H 'Authorization: Bearer …'      # 401 (GET czyta tylko query)
curl -s "$B/status?token=…"                                                            # 400 (nie ma /status)
```

### Mostek MCP (`ytdigest/mcp_bridge.py`)

Stdio, wyłącznie biblioteka standardowa (Python 3.9+ wystarcza, także na Windows), logiki
własnej nie ma — woła `serve` po HTTP. Zmierzony handshake (JSON-RPC po stdin):

```bash
printf '%s\n%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
 | YTDIGEST_URL=http://127.0.0.1:8765 python ytdigest/mcp_bridge.py
# {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},
#  "serverInfo":{"name":"youtube-digest","version":"0.1"}}}
```

`tools/list` zwraca dokładnie dwa narzędzia (schematy zmierzone, nie przepisane z opisu):

| Narzędzie | Argumenty | Zachowanie |
|---|---|---|
| `digest_youtube_video` | `url` (wymagany), `wait_seconds` (domyślnie 600) | `GET /report`; jeśli status nie jest `done`/`artistic` → `POST /digest` i odpytuje co 15 s aż do `done`/`artistic`/`failed` albo do upływu `wait_seconds`; zwraca Markdown raportu + link do Notion |
| `get_youtube_report` | `url` (wymagany) | tylko `GET /report` — nic nie kolejkuje |

Po przekroczeniu `wait_seconds` odpowiedź brzmi dokładnie: „Hermes is still working on it; ask
again with get_youtube_report in a few minutes.” (zmierzone w źródle, nie wywołane — brak
kolejki do odczekania w tej karcie).

```json
// claude_desktop_config.json — mostek startuje na komputerze, serwer zostaje na VM
{"mcpServers": {"youtube-digest": {
  "command": "python", "args": ["C:\\ścieżka\\do\\mcp_bridge.py"],
  "env": {"YTDIGEST_URL": "http://<tailscale-ip>:8765", "YTDIGEST_TOKEN": "<z Bitwarden>"}}}}
```

Zasady wiązania (`ytdigest/server.py`): tylko `localhost` albo adres Tailscale, nigdy
`0.0.0.0` — `serve()` kończy się `SystemExit("refusing to listen on all interfaces; use
127.0.0.1 or the Tailscale IP")`; bez `YTDIGEST_TOKEN` serwer nie wstaje.

## 4. Kontrakt manifestu archiwum

Jedno źródło prawdy o archiwum YouTube: `/home/ubuntu/crewai-orchestrator/archive_manifest.json`
(poza tym repo — konsument, nie producent). 259 wpisów, 209 404 B, `mtime` 2026-10-28 09:20:39Z.

```bash
python3 -c "import json,collections;d=json.load(open('/home/ubuntu/crewai-orchestrator/archive_manifest.json'));print(len(d), collections.Counter(v['status'] for v in d.values()))"
# 259 Counter({'pending': 111, 'done': 84, 'needs_whisper': 64})
```

Klucz = `video_id`. Pola (typy zmierzone na wszystkich wpisach):

| Pole | Typ | Kiedy występuje |
|---|---|---|
| `status` | str | zawsze — `pending` \| `needs_whisper` \| `done` |
| `error` | str | zawsze przy `pending` (111/111) i `needs_whisper` (64/64): `IpBlocked`, `NoTranscriptFound`, … |
| `source` | str | `needs_whisper` i `done`; przy `needs_whisper` zawsze `whisper` |
| `transcript_path` | str | `done` (84/84) — ścieżka pliku z transkryptem |
| `gdrive_file_id`, `gdrive_path`, `persisted_at` | str | `done` z publikacją do Drive (67/84) |
| `provider`, `model`, `language`, `transcribe_seconds`, `audio_seconds`, `title`, `channel`, `playlist` | str/float | `done` po pełnym przebiegu (14/84) |

```json
{"status": "needs_whisper", "source": "whisper",
 "error": "NoTranscriptFound: \nCould not retrieve a transcript for the video https://www.youtube.com/watch?v=…"}
```

Maszyna stanów: `pending` (napisy nie wyszły) → `needs_whisper` (trzeba Whispera) →
`done` (`transcript_path` + opcjonalnie `gdrive_*`). Reguły: `status` jest jedynym
źródłem prawdy (nie zgaduj z obecności pól); `done` bez `transcript_path` to błąd danych;
`gdrive_*` są opcjonalne i mogą pojawić się później (`persisted_at` = czas publikacji).

## 5. Konfiguracja i zależności

Kolejność wczytywania (`ytdigest/config.py`): `DEFAULTS` → plik
`$YTDIGEST_CONFIG`, `~/.hermes/ytdigest/config.yaml`, `./config.yaml` (pierwszy istniejący,
deep-merge) → zmienne środowiskowe. Żywy plik ma 10 kluczy:

| Klucz | Znaczenie w żywym pliku |
|---|---|
| `report_language` | język raportu (`"pl"`) |
| `accounts` | konta przetwarzane przez backlog, w kolejności |
| `extra_playlists`, `skip_playlists` | dodatkowe / pomijane playlisty (puste) |
| `include_liked` | czy brać „polubione” (`false`) |
| `backlog_daily_cap_usd` | dzienny cap pracy nienadzorowanej (`1.0` USD) |
| `routing_file` | tabela routingu modeli (pusta) |
| `transcript_order` | kolejność źródeł transkryptu: `manual, groq, parakeet, local, auto` |
| `notify_ha_service` | usługa Home Assistant do powiadomień (pusta) |
| `notion_data_source_id` | baza Notion z raportami |

`DEFAULTS` w `config.py` niesie rzeczy, których nie ma w pliku — m.in. `data_dir` (~/.hermes/ytdigest),
`caption_languages: [pl, en]`, `whisper_local_max_minutes: 40` (lokalny Whisper na 8 GB
VM jest wolny), `max_frames: 60`, `gemini_enabled: false`, `topic_routes` (`ai_software`
i `manual` → `claude-code:sonnet`), `processed_playlist` (playlista „Przetworzone przez
Hermesa”, konto `fjkazmierczak`, `enabled: true`), `idle_user_quiet_minutes` /
`idle_max_load_per_cpu` / `idle_min_free_mem_mb` (brama bezczynności), `providers` +
`prices_per_mtok` (koszt liczony lokalnie).

Zmienne środowiskowe: `YTDIGEST_CONFIG`, `YTDIGEST_DATA_DIR`, `YTDIGEST_NOTION_DATA_SOURCE`,
`YTDIGEST_ROUTING`, `SITEDIGEST_ROOT`, `SITEDIGEST_NOTION_DATA_SOURCE`, `YTDIGEST_TOKEN`
(serwer), a także klucze providerów wskazywane przez `providers[*].key_env`:
`OLLAMA_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY` i token Notion.
`HERMES_REAL_HOME` przesuwa `~/.hermes`.

Zależności: `pyproject.toml`. Rdzeń (CLI, kolejka, raporty) nie wymaga extra; extras:
`local-asr` (Whisper/ONNX lokalnie), `site` (`sitedigest`: Playwright + PyPDF), `dev`
(`pytest`). YAML wymaga PyYAML — w venv `~/.hermes/ytdigest/venv` jest (zmierzone: 6.0.3).

## 6. Gdzie szukać dalej

Operacyjne runbooki żyją w repo `crewai-orchestrator` (to on produkuje manifest):

- `docs/youtube-archive-README.md` — jak działa archiwum YouTube.
- `docs/youtube-archive-RUNBOOK.md` — przebieg end-to-end.
- `docs/RUNBOOK-youtube-archive-end-to-end.md` — procedura krok po kroku.
- `docs/transcription-path-comparison.md` — ścieżki transkrypcji (koszt vs jakość).
- `docs/youtube-quota-strategy.md` i `docs/RESEARCH-rate-limit-backoff-youtube-vs-litellm.md`
  — limity YouTube i backoff.
- `video-digest/README.md` (to repo) — skrót użytkowy i przykłady.
