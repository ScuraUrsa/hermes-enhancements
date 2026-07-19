#!/usr/bin/env python3
"""
POV #8: Notion API Integration — Demo
======================================
Klient Notion API z pobieraniem klucza z Bitwarden.
Operacje: list databases, query database, create page.

Wymagania:
    pip install notion-client

Klucz API pobierany z Bitwarden (bws CLI) lub z env NOTION_API_KEY.
"""

import json
import os
import subprocess
import sys
from datetime import datetime

from notion_client import Client


# ──────────────────────────────────────────────
# 1. Pobieranie NOTION_API_KEY
# ──────────────────────────────────────────────

def get_notion_api_key() -> str:
    """Pobiera NOTION_API_KEY z Bitwarden lub zmiennej środowiskowej."""
    # Najpierw sprawdź zmienną środowiskową
    key = os.environ.get("NOTION_API_KEY", "").strip()
    if key:
        print("[OK] NOTION_API_KEY z env")
        return key

    # Potem spróbuj Bitwarden
    try:
        result = subprocess.run(
            ["bws", "secret", "list", "--server-url", "https://vault.bitwarden.eu"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            secrets = json.loads(result.stdout)
            for s in secrets:
                if s.get("key") == "NOTION_API_KEY":
                    print("[OK] NOTION_API_KEY z Bitwarden")
                    return s["value"]
    except Exception as e:
        print(f"[WARN] Bitwarden niedostępny: {e}")

    print("[ERROR] Brak NOTION_API_KEY — ustaw zmienną lub skonfiguruj Bitwarden")
    sys.exit(1)


# ──────────────────────────────────────────────
# 2. Operacje Notion API
# ──────────────────────────────────────────────

def list_databases(client: Client) -> list:
    """Wypisuje wszystkie bazy danych dostępne w integracji."""
    print("\n" + "=" * 60)
    print("📚 LISTA BAZ DANYCH")
    print("=" * 60)

    # Notion API 2025+: search filter akceptuje tylko "page" lub "data_source"
    # Szukamy data_sources i wyciągamy z nich bazy danych
    all_results = []
    for filter_val in ("page", "data_source"):
        try:
            resp = client.search(
                filter={"property": "object", "value": filter_val},
                page_size=100
            )
            all_results.extend(resp.get("results", []))
        except Exception as e:
            print(f"  [WARN] search filter={filter_val}: {e}")

    # Zbierz unikalne bazy danych (database_id z parent obiektów)
    databases = []
    seen_ids = set()

    for obj in all_results:
        obj_type = obj.get("object", "")
        parent = obj.get("parent", {})

        if obj_type == "database":
            db_id = obj["id"]
            if db_id not in seen_ids:
                seen_ids.add(db_id)
                title = "".join(
                    t.get("plain_text", "")
                    for t in obj.get("title", [])
                )
                databases.append({"id": db_id, "title": title, "url": obj.get("url", "N/A")})

        elif parent.get("type") == "database_id":
            db_id = parent.get("database_id")
            if db_id and db_id not in seen_ids:
                seen_ids.add(db_id)
                # Pobierz tytuł bazy przez GET /v1/databases/{id}
                try:
                    db_info = client.databases.retrieve(database_id=db_id)
                    title = "".join(
                        t.get("plain_text", "")
                        for t in db_info.get("title", [])
                    )
                    databases.append({"id": db_id, "title": title, "url": db_info.get("url", "N/A")})
                except Exception:
                    databases.append({"id": db_id, "title": "(bez nazwy)", "url": "N/A"})

    for db in databases:
        print(f"  📁 {db['title']}")
        print(f"     ID: {db['id']}")
        print(f"     URL: {db.get('url', 'N/A')}")

    if not databases:
        print("  (brak baz danych — sprawdź integrację w Notion)")

    print(f"\n  Znaleziono: {len(databases)} baz(y)")
    return databases


def _get_data_source_id(client: Client, database_id: str) -> str:
    """Pobiera data_source_id dla bazy danych (Notion API 2025+)."""
    db_info = client.databases.retrieve(database_id=database_id)
    data_sources = db_info.get("data_sources", [])
    if data_sources:
        return data_sources[0]["id"]
    raise ValueError(f"Brak data sources dla bazy {database_id}")


def query_database(client: Client, database_id: str, page_size: int = 5) -> list:
    """Odpytuje bazę danych i wypisuje strony."""
    print("\n" + "=" * 60)
    print(f"🔍 QUERY BAZY: {database_id[:8]}...")
    print("=" * 60)

    # Notion API 2025+: query przez data_sources
    ds_id = _get_data_source_id(client, database_id)
    response = client.data_sources.query(
        data_source_id=ds_id,
        page_size=page_size
    )

    pages = response.get("results", [])
    for i, page in enumerate(pages, 1):
        props = page.get("properties", {})
        print(f"\n  📄 Strona {i}:")
        print(f"     ID: {page['id']}")
        for prop_name, prop_data in props.items():
            ptype = prop_data.get("type", "unknown")
            value = _extract_property_value(prop_data)
            if value:
                print(f"     {prop_name} ({ptype}): {value}")

    print(f"\n  Stron: {len(pages)}")
    return pages


def create_page(
    client: Client,
    database_id: str,
    title: str,
    properties: dict = None
) -> dict:
    """Tworzy nową stronę w bazie danych."""
    print("\n" + "=" * 60)
    print(f"➕ TWORZENIE STRONY w bazie {database_id[:8]}...")
    print("=" * 60)

    page_properties = {
        "Name": {
            "title": [{"text": {"content": title}}]
        }
    }

    # Dodaj dodatkowe właściwości jeśli podane
    if properties:
        page_properties.update(properties)

    # Notion API 2025+: parent używa data_source_id
    ds_id = _get_data_source_id(client, database_id)
    new_page = client.pages.create(
        parent={"type": "data_source_id", "data_source_id": ds_id},
        properties=page_properties
    )

    print(f"  ✅ Stworzono: {title}")
    print(f"     ID: {new_page['id']}")
    print(f"     URL: {new_page.get('url', 'N/A')}")
    return new_page


def _extract_property_value(prop_data: dict) -> str:
    """Wyciąga czytelną wartość z property Notion."""
    ptype = prop_data.get("type", "")

    if ptype == "title":
        parts = prop_data.get("title", [])
        return "".join(t.get("plain_text", "") for t in parts)

    if ptype == "rich_text":
        parts = prop_data.get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in parts)

    if ptype == "number":
        return str(prop_data.get("number", ""))

    if ptype == "select":
        sel = prop_data.get("select")
        return sel["name"] if sel else ""

    if ptype == "multi_select":
        items = prop_data.get("multi_select", [])
        return ", ".join(i["name"] for i in items)

    if ptype == "date":
        d = prop_data.get("date")
        return f"{d.get('start', '')} → {d.get('end', '')}" if d else ""

    if ptype == "checkbox":
        return "✅" if prop_data.get("checkbox") else "⬜"

    if ptype == "url":
        return prop_data.get("url", "")

    if ptype == "email":
        return prop_data.get("email", "")

    if ptype == "phone_number":
        return prop_data.get("phone_number", "")

    if ptype == "status":
        s = prop_data.get("status")
        return s["name"] if s else ""

    return f"[{ptype}]"


# ──────────────────────────────────────────────
# 3. Token monitor helper
# ──────────────────────────────────────────────

TOKEN_MONITOR = os.path.expanduser(
    "~/workspace/hermes-enhancements/POV/04-token-monitor/ollama_token_monitor.py"
)


def record_tokens(prompt_tokens: int, completion_tokens: int):
    """Zapisuje zużycie tokenów w monitorze."""
    if not os.path.exists(TOKEN_MONITOR):
        print("[WARN] Token monitor nie znaleziony, pomijam")
        return

    subprocess.run([
        sys.executable, TOKEN_MONITOR, "record",
        str(prompt_tokens), str(completion_tokens), "deepseek-v4-pro"
    ], capture_output=True, timeout=10)


# ──────────────────────────────────────────────
# 4. Main — demo
# ──────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🚀 POV #8: Notion API Integration — Demo")
    print("=" * 60)

    # Pobierz klucz
    api_key = get_notion_api_key()
    client = Client(auth=api_key)

    # --- Krok 1: Lista baz danych ---
    databases = list_databases(client)
    record_tokens(prompt_tokens=500, completion_tokens=200)

    if not databases:
        print("\n⚠️  Brak baz danych. Sprawdź czy integracja ma dostęp do workspace.")
        print("   Przejdź do Notion → Settings → Connections → dodaj integrację.")
        return

    # --- Krok 2: Query pierwszej bazy ---
    first_db = databases[0]
    pages = query_database(client, first_db["id"], page_size=3)
    record_tokens(prompt_tokens=400, completion_tokens=300)

    # --- Krok 3: Stwórz testową stronę (bez dodatkowych properties) ---
    test_title = f"🤖 Test z Hermes — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    new_page = create_page(client, first_db["id"], test_title)
    record_tokens(prompt_tokens=600, completion_tokens=400)

    print("\n" + "=" * 60)
    print("✅ DEMO ZAKOŃCZONE")
    print("=" * 60)
    print(f"  Bazy: {len(databases)}")
    print(f"  Strony w pierwszej bazie: {len(pages)}")
    print(f"  Nowa strona: {test_title}")
    print(f"  URL: {new_page.get('url', 'N/A')}")


if __name__ == "__main__":
    main()
