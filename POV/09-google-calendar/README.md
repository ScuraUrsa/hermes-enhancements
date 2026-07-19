# POV #9: Google Calendar Integration

Integracja z Google Calendar API — listowanie wydarzeń, tworzenie, quick add (język naturalny).

## Wymagania

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## Konfiguracja

Token OAuth pobierany automatycznie z **Bitwarden** (bws CLI) lub z pliku na dysku.

### Token OAuth

Konto: `f.j.kazmierczak@gmail.com`

| Źródło | Lokalizacja |
|--------|------------|
| Bitwarden | `GOOGLE_FJKAZMIERCZAK_TOKEN_JSON` (id: `ddece7b5-...`) |
| Dysk | `~/.hermes/google_token_fjkazmierczak.json` |

Token zawiera scope `https://www.googleapis.com/auth/calendar` — pełny dostęp do kalendarza.

### Client Secret (do refresh tokena)

| Źródło | Lokalizacja |
|--------|------------|
| Bitwarden | `GOOGLE_PRAKTYKI_CLIENT_SECRET` (id: `70483a8c-...`) |
| Dysk | `~/.hermes/google_client_secret.json` |

### Pierwsze uruchomienie (jeśli token nie istnieje)

1. Pobierz client_secret z Bitwarden:
   ```bash
   bws secret get 70483a8c-6540-4273-bbc6-b45e00bfa303 --server-url https://vault.bitwarden.eu | \
     python3 -c "import sys,json; print(json.load(sys.stdin)['value'])" > ~/.hermes/google_client_secret.json
   ```

2. Uruchom OAuth flow (wymaga przeglądarki):
   ```bash
   python3 ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --auth-url
   # Otwórz URL, zaloguj się, skopiuj callback URL z localhost:1
   python3 ~/.hermes/skills/productivity/google-workspace/scripts/setup.py --auth-code "CALLBACK_URL"
   ```

3. Skopiuj token:
   ```bash
   cp ~/.hermes/google_token.json ~/.hermes/google_token_fjkazmierczak.json
   ```

## Użycie

```bash
# Pełne demo (list → quick add → create → list → cleanup)
python3 demo.py

# Tylko lista wydarzeń
python3 -c "
from demo import get_credentials, list_events
from googleapiclient.discovery import build
creds = get_credentials()
service = build('calendar', 'v3', credentials=creds)
list_events(service)
"

# Quick add (język naturalny)
python3 -c "
from demo import get_credentials, quick_add
from googleapiclient.discovery import build
creds = get_credentials()
service = build('calendar', 'v3', credentials=creds)
quick_add(service, 'Spotkanie z zespołem jutro o 14:00')
"
```

## Operacje

| Funkcja | Opis |
|---------|------|
| `list_events(service, max_results, days_ahead)` | Wypisuje nadchodzące wydarzenia |
| `create_event(service, summary, start_dt, end_dt, ...)` | Tworzy wydarzenie z pełnymi szczegółami |
| `quick_add(service, text)` | Szybkie dodawanie w języku naturalnym |
| `delete_event(service, event_id)` | Usuwa wydarzenie po ID |

### Quick Add — przykłady

Google Calendar API parsuje tekst automatycznie:

- `"Spotkanie jutro o 15:00"` → jutro, 15:00-16:00
- `"Obiad z Janem w piątek 12:00-13:00"` → najbliższy piątek
- `"Dentysta 2026-07-25 10:00"` → konkretna data
- `"Konferencja 2026-08-01 do 2026-08-03"` → zakres dat

## Token Monitor

Każda operacja API jest rejestrowana w token monitorze (`POV/04-token-monitor/`).

## Struktura

```
POV/09-google-calendar/
├── demo.py      # Główny skrypt demonstracyjny
└── README.md    # Ten plik
```

## Scope'y

Token `f.j.kazmierczak@gmail.com` zawiera:

- `calendar` — pełny dostęp do kalendarza
- `gmail.send`, `gmail.readonly`, `gmail.modify` — Gmail
- `drive` — Google Drive
- `documents`, `spreadsheets` — Docs/Sheets
- `contacts.readonly` — Kontakty
- `youtube`, `youtube.upload`, `yt-analytics.readonly` — YouTube
