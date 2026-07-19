# POV #8: Notion API Integration

Integracja z Notion API — listowanie baz danych, query, tworzenie stron.

## Wymagania

```bash
pip install notion-client
```

## Konfiguracja

Klucz API pobierany automatycznie z **Bitwarden** (bws CLI) lub ze zmiennej środowiskowej:

```bash
# Opcja 1: Bitwarden (automatycznie)
bws secret list --server-url https://vault.bitwarden.eu
# Klucz: NOTION_API_KEY

# Opcja 2: Zmienna środowiskowa
export NOTION_API_KEY="ntn_..."
```

## Integracja z Notion

1. Przejdź do [Notion Integrations](https://www.notion.so/my-integrations)
2. Kliknij **New integration**
3. Nadaj nazwę (np. "Hermes Agent")
4. Skopiuj **Internal Integration Secret** → zapisz w Bitwarden jako `NOTION_API_KEY`
5. W Notion, dla każdej bazy danych:
   - Otwórz bazę → `...` → **Connections** → **Add connections** → wybierz integrację

## Użycie

```bash
# Pełne demo (list databases → query → create page)
python3 demo.py

# Tylko lista baz
python3 -c "
from demo import get_notion_api_key, list_databases
from notion_client import Client
client = Client(auth=get_notion_api_key())
list_databases(client)
"
```

## Operacje

| Funkcja | Opis |
|---------|------|
| `list_databases(client)` | Wypisuje wszystkie dostępne bazy danych |
| `query_database(client, db_id)` | Odpytuje bazę i wypisuje strony |
| `create_page(client, db_id, title)` | Tworzy nową stronę w bazie |

## Token Monitor

Każda operacja API jest rejestrowana w token monitorze (`POV/04-token-monitor/`).

## Struktura

```
POV/08-notion-integration/
├── demo.py      # Główny skrypt demonstracyjny
└── README.md    # Ten plik
```
