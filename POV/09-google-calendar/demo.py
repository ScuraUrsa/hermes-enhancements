#!/usr/bin/env python3
"""
POV #9: Google Calendar Integration — Demo
===========================================
Klient Google Calendar API z pobieraniem tokena OAuth z Bitwarden.
Operacje: list events, create event, quick add (natural language).

Wymagania:
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Token OAuth pobierany z Bitwarden (bws CLI) lub z pliku na dysku.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# ──────────────────────────────────────────────
# 1. Pobieranie tokena OAuth
# ──────────────────────────────────────────────

BWS_SECRET_ID = "ddece7b5-6a66-4715-8b20-b47700d092de"
BWS_CLIENT_SECRET_ID = "70483a8c-6540-4273-bbc6-b45e00bfa303"
BWS_SERVER = "https://vault.bitwarden.eu"

TOKEN_DISK_PATH = os.path.expanduser("~/.hermes/google_token_fjkazmierczak.json")
CLIENT_SECRET_PATH = os.path.expanduser("~/.hermes/google_client_secret.json")


def _bws_get(secret_id: str) -> dict:
    """Pobiera sekret z Bitwarden Secrets Manager."""
    result = subprocess.run(
        ["bws", "secret", "get", secret_id, "--server-url", BWS_SERVER],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"bws error: {result.stderr.strip()}")
    return json.loads(result.stdout)


def get_credentials() -> Credentials:
    """Pobiera Google OAuth credentials z Bitwarden lub pliku na dysku."""
    token_data = None
    source = ""

    # 1. Spróbuj z pliku na dysku (świeższa kopia)
    if os.path.exists(TOKEN_DISK_PATH):
        try:
            with open(TOKEN_DISK_PATH) as f:
                token_data = json.load(f)
            source = f"dysk ({TOKEN_DISK_PATH})"
        except (json.JSONDecodeError, IOError):
            pass

    # 2. Spróbuj z Bitwarden
    if token_data is None:
        try:
            secret = _bws_get(BWS_SECRET_ID)
            token_data = json.loads(secret["value"])
            source = "Bitwarden"
        except Exception as e:
            print(f"[ERROR] Nie można pobrać tokena: {e}")
            sys.exit(1)

    print(f"[OK] Token z: {source}")

    # 3. Pobierz client_secret do refresh
    client_secret_data = None
    if os.path.exists(CLIENT_SECRET_PATH):
        with open(CLIENT_SECRET_PATH) as f:
            client_secret_data = json.load(f)
    else:
        try:
            secret = _bws_get(BWS_CLIENT_SECRET_ID)
            client_secret_data = json.loads(secret["value"])
        except Exception:
            pass

    client_id = None
    client_secret = None
    if client_secret_data:
        installed = client_secret_data.get("installed", client_secret_data.get("web", {}))
        client_id = installed.get("client_id")
        client_secret = installed.get("client_secret")

    creds = Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=token_data.get("scopes", []),
    )

    # Odśwież jeśli wygasł
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(creds._make_request())
            print("[OK] Token odświeżony")
        except Exception as e:
            print(f"[WARN] Nie udało się odświeżyć tokena: {e}")

    return creds


# ──────────────────────────────────────────────
# 2. Operacje Google Calendar API
# ──────────────────────────────────────────────

def list_events(service, max_results: int = 10, days_ahead: int = 7) -> list:
    """Wypisuje nadchodzące wydarzenia z kalendarza."""
    print("\n" + "=" * 60)
    print("📅 NADCHODZĄCE WYDARZENIA")
    print("=" * 60)

    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=days_ahead)).isoformat()

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except HttpError as e:
        print(f"  [ERROR] {e}")
        return []

    events = events_result.get("items", [])

    if not events:
        print(f"  Brak wydarzeń w ciągu najbliższych {days_ahead} dni.")
        return []

    for i, event in enumerate(events, 1):
        start = event["start"].get("dateTime", event["start"].get("date", "?"))
        summary = event.get("summary", "(bez tytułu)")
        event_id = event["id"]
        location = event.get("location", "")
        loc_str = f" 📍 {location}" if location else ""

        # Formatuj datę
        try:
            if "T" in start:
                dt = datetime.fromisoformat(start)
                start_str = dt.strftime("%Y-%m-%d %H:%M")
            else:
                start_str = start
        except (ValueError, TypeError):
            start_str = start

        print(f"\n  📌 {i}. {summary}")
        print(f"     🕐 {start_str}{loc_str}")
        print(f"     ID: {event_id}")

    print(f"\n  Znaleziono: {len(events)} wydarzeń")
    return events


def create_event(
    service,
    summary: str,
    start_dt: datetime = None,
    end_dt: datetime = None,
    description: str = "",
    location: str = "",
    attendees: list = None,
) -> dict:
    """Tworzy nowe wydarzenie w kalendarzu."""
    print("\n" + "=" * 60)
    print(f"➕ TWORZENIE WYDARZENIA: {summary}")
    print("=" * 60)

    if start_dt is None:
        start_dt = datetime.now(timezone.utc) + timedelta(hours=1)
    if end_dt is None:
        end_dt = start_dt + timedelta(hours=1)

    event_body = {
        "summary": summary,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": "Europe/Warsaw",
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": "Europe/Warsaw",
        },
    }

    if description:
        event_body["description"] = description
    if location:
        event_body["location"] = location
    if attendees:
        event_body["attendees"] = [{"email": a} for a in attendees]

    try:
        event = service.events().insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all" if attendees else "none",
        ).execute()
    except HttpError as e:
        print(f"  [ERROR] {e}")
        return {}

    print(f"  ✅ Utworzono: {event.get('summary')}")
    print(f"     ID: {event['id']}")
    print(f"     Link: {event.get('htmlLink', 'N/A')}")
    print(f"     Start: {event['start'].get('dateTime', '?')}")
    return event


def quick_add(service, text: str) -> dict:
    """Szybkie dodawanie wydarzenia w języku naturalnym.

    Google Calendar API quickAdd parsuje tekst jak:
    - "Spotkanie jutro o 15:00"
    - "Obiad z Janem w piątek 12:00-13:00"
    - "Dentysta 2026-07-25 10:00"
    """
    print("\n" + "=" * 60)
    print(f"⚡ QUICK ADD: {text}")
    print("=" * 60)

    try:
        event = service.events().quickAdd(
            calendarId="primary",
            text=text,
        ).execute()
    except HttpError as e:
        print(f"  [ERROR] {e}")
        return {}

    print(f"  ✅ Utworzono: {event.get('summary')}")
    print(f"     ID: {event['id']}")
    print(f"     Link: {event.get('htmlLink', 'N/A')}")
    print(f"     Start: {event['start'].get('dateTime', event['start'].get('date', '?'))}")
    print(f"     Koniec: {event['end'].get('dateTime', event['end'].get('date', '?'))}")
    return event


def delete_event(service, event_id: str) -> bool:
    """Usuwa wydarzenie po ID."""
    print(f"\n🗑️  USUWANIE: {event_id}")
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
        print(f"  ✅ Usunięto")
        return True
    except HttpError as e:
        print(f"  [ERROR] {e}")
        return False


# ──────────────────────────────────────────────
# 3. Token monitor helper
# ──────────────────────────────────────────────

TOKEN_MONITOR = os.path.expanduser(
    "~/workspace/hermes-enhancements/POV/04-token-monitor/ollama_token_monitor.py"
)


def record_tokens(prompt_tokens: int, completion_tokens: int):
    """Zapisuje zużycie tokenów w monitorze."""
    if not os.path.exists(TOKEN_MONITOR):
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
    print("🚀 POV #9: Google Calendar Integration — Demo")
    print("=" * 60)

    # Pobierz credentials
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    # --- Krok 1: Lista nadchodzących wydarzeń ---
    events = list_events(service, max_results=5, days_ahead=7)
    record_tokens(prompt_tokens=300, completion_tokens=200)

    # --- Krok 2: Quick add — testowe wydarzenie ---
    test_text = f"POV #9 test {datetime.now().strftime('%H:%M')}"
    new_event = quick_add(service, test_text)
    record_tokens(prompt_tokens=200, completion_tokens=150)

    # --- Krok 3: Stwórz wydarzenie z pełnymi szczegółami ---
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    tomorrow_10 = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
    tomorrow_11 = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

    detailed_event = create_event(
        service,
        summary="🤖 Hermes POV #9 — pełne demo",
        start_dt=tomorrow_10,
        end_dt=tomorrow_11,
        description="Wydarzenie utworzone przez Hermes Agent w ramach POV #9: Google Calendar Integration.",
        location="Gdańsk, Polska",
    )
    record_tokens(prompt_tokens=400, completion_tokens=300)

    # --- Krok 4: Ponowna lista (powinna zawierać nowe wydarzenia) ---
    events_after = list_events(service, max_results=5, days_ahead=7)
    record_tokens(prompt_tokens=300, completion_tokens=200)

    # --- Krok 5: Posprzątaj — usuń testowe wydarzenia ---
    if new_event.get("id"):
        delete_event(service, new_event["id"])
    if detailed_event.get("id"):
        delete_event(service, detailed_event["id"])

    print("\n" + "=" * 60)
    print("✅ DEMO ZAKOŃCZONE")
    print("=" * 60)
    print(f"  Wydarzenia przed: {len(events)}")
    print(f"  Wydarzenia po: {len(events_after)}")
    print(f"  Quick add: {'✅' if new_event else '❌'}")
    print(f"  Create event: {'✅' if detailed_event else '❌'}")
    print(f"  Cleanup: ✅ (testowe wydarzenia usunięte)")


if __name__ == "__main__":
    main()
