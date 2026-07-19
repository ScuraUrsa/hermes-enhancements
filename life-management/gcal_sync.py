#!/usr/bin/env python3
"""
Google Calendar Sync — Life Management ↔ Google Calendar
=========================================================
Eksportuje bloki czasu do Google Calendar jako eventy.
Importuje eventy z Google Calendar do life_management.db.

Wymaga: Google OAuth credentials (Bitwarden: GOOGLE_CALENDAR_CREDENTIALS)
Lub service account JSON.
"""

from __future__ import annotations

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta, timezone
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker

LIFE_DIR = Path(__file__).parent

# ── Google Calendar Client ───────────────────────────────────────────────────

class GoogleCalendarSync:
    """Synchronizacja z Google Calendar przez REST API."""

    # Mapowanie kategorii czasu na kolory Google Calendar
    CATEGORY_COLORS = {
        "praca": "9",       # niebieski
        "rodzina": "6",     # pomarańczowy
        "znajomi": "5",     # żółty
        "zdrowie": "2",     # zielony
        "jedzenie": "4",    # różowy
        "hobby": "3",       # fioletowy
        "odpoczynek": "7",  # turkusowy
        "nauka": "1",       # lawendowy
        "administracja": "8", # grafitowy
        "transport": "10",  # zielony ciemny
        "higiena": "11",    # czerwony
        "inne": "0",        # domyślny
    }

    def __init__(self, db: LifeDB, credentials_path: str = ""):
        self.db = db
        self.tracker = TimeTracker(db)
        self.people = PeopleManager(db)
        self.events = EventManager(db)

        if not credentials_path:
            credentials_path = str(LIFE_DIR / "data" / "google_credentials.json")

        self.credentials_path = credentials_path
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _get_token(self) -> str:
        """Pobierz access token z credentials (service account lub OAuth)."""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token

        # Spróbuj service account
        if os.path.exists(self.credentials_path):
            try:
                creds = json.loads(Path(self.credentials_path).read_text())
                if "client_email" in creds and "private_key" in creds:
                    return self._get_service_account_token(creds)
            except Exception:
                pass

        # Spróbuj OAuth z Bitwarden
        try:
            result = subprocess.run(
                ["bws", "secret", "get", "GOOGLE_CALENDAR_TOKEN"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self._token = result.stdout.strip()
                self._token_expiry = datetime.now() + timedelta(minutes=50)
                return self._token
        except Exception:
            pass

        raise RuntimeError(
            "Brak credentials Google. Umieść service account JSON w "
            f"{self.credentials_path} lub GOOGLE_CALENDAR_TOKEN w Bitwarden."
        )

    def _get_service_account_token(self, creds: dict) -> str:
        """Wygeneruj JWT i wymień na access token (service account)."""
        import base64
        import time

        # Minimal JWT implementation (no external deps)
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()

        now = int(time.time())
        claim = base64.urlsafe_b64encode(
            json.dumps({
                "iss": creds["client_email"],
                "scope": "https://www.googleapis.com/auth/calendar",
                "aud": "https://oauth2.googleapis.com/token",
                "exp": now + 3600,
                "iat": now,
            }).encode()
        ).rstrip(b"=").decode()

        # Sign with private key
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            creds["private_key"].encode(), password=None
        )
        signature = private_key.sign(
            f"{header}.{claim}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

        assertion = f"{header}.{claim}.{sig_b64}"

        # Exchange for access token
        import urllib.request
        import urllib.parse

        data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode()

        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req) as resp:
            token_data = json.loads(resp.read())

        self._token = token_data["access_token"]
        self._token_expiry = datetime.now() + timedelta(seconds=token_data.get("expires_in", 3500))
        return self._token

    def _api_call(self, method: str, endpoint: str, data: dict | None = None) -> dict:
        """Wykonaj zapytanie do Google Calendar API."""
        import urllib.request

        token = self._get_token()
        url = f"https://www.googleapis.com/calendar/v3{endpoint}"

        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method=method,
        )

        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise RuntimeError(f"Google API error ({e.code}): {error_body}")

    def export_blocks(
        self,
        calendar_id: str = "primary",
        days_back: int = 7,
    ) -> int:
        """Eksportuj bloki czasu z ostatnich N dni do Google Calendar."""
        start_date = (date.today() - timedelta(days=days_back)).isoformat()
        blocks = self.tracker.get_blocks(start_date=start_date)

        count = 0
        for block in blocks:
            if not block["end_time"]:
                continue

            color_id = self.CATEGORY_COLORS.get(block["category"], "0")

            event_data = {
                "summary": f"[{block['category']}] {block['description'] or 'Bez opisu'}",
                "start": {
                    "dateTime": block["start_time"],
                    "timeZone": "Europe/Warsaw",
                },
                "end": {
                    "dateTime": block["end_time"],
                    "timeZone": "Europe/Warsaw",
                },
                "colorId": color_id,
                "description": (
                    f"Kategoria: {block['category']}\n"
                    f"Energia: {block['energy_level']}/10\n"
                    f"Focus: {block['focus_level']}/10\n"
                    f"Zaplanowane: {'tak' if block['was_planned'] else 'nie'}"
                ),
            }

            # Dodaj osobę jeśli przypisana
            if block["person_id"]:
                person = self.people.get_person(block["person_id"])
                if person:
                    event_data["summary"] += f" z {person.name}"

            try:
                self._api_call("POST", f"/calendars/{calendar_id}/events", event_data)
                count += 1
            except Exception as e:
                print(f"  ⚠️ Błąd eksportu bloku {block['id']}: {e}")

        return count

    def import_events(
        self,
        calendar_id: str = "primary",
        days_ahead: int = 30,
    ) -> int:
        """Importuj eventy z Google Calendar do life_management.db."""
        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

        try:
            data = self._api_call(
                "GET",
                f"/calendars/{calendar_id}/events"
                f"?timeMin={now}&timeMax={end}"
                f"&singleEvents=true&orderBy=startTime&maxResults=100",
            )
        except Exception as e:
            print(f"  ❌ Błąd importu: {e}")
            return 0

        count = 0
        for item in data.get("items", []):
            title = item.get("summary", "Bez tytułu")
            start = item.get("start", {})

            event_date = ""
            if "date" in start:
                event_date = start["date"]
            elif "dateTime" in start:
                event_date = start["dateTime"][:10]

            if not event_date:
                continue

            # Sprawdź czy już istnieje
            existing = self.db.execute(
                "SELECT id FROM events WHERE title = ? AND event_date = ?",
                (title, event_date),
            )
            if existing:
                continue

            # Określ typ
            event_type = "inne"
            title_lower = title.lower()
            if any(w in title_lower for w in ["urodziny", "birthday"]):
                event_type = "urodziny"
            elif any(w in title_lower for w in ["deadline", "termin"]):
                event_type = "deadline"
            elif any(w in title_lower for w in ["lekarz", "dentysta", "wizyta"]):
                event_type = "zdrowie"
            elif any(w in title_lower for w in ["spotkanie", "meeting", "kawa"]):
                event_type = "spotkanie"

            self.events.add_event(
                title=title,
                event_date=event_date,
                event_type=event_type,
                notes=item.get("description", ""),
            )
            count += 1

        return count

    def sync_birthdays_to_calendar(self, calendar_id: str = "primary") -> int:
        """Dodaj urodziny z people DB jako recurring eventy w Google Calendar."""
        all_people = self.people.get_all_people()
        count = 0

        for person in all_people:
            if not person.birthday:
                continue

            try:
                bday = date.fromisoformat(person.birthday)
                # Ustaw na najbliższe urodziny
                this_year = date(date.today().year, bday.month, bday.day)
                if this_year < date.today():
                    this_year = date(date.today().year + 1, bday.month, bday.day)

                age = this_year.year - bday.year

                event_data = {
                    "summary": f"🎂 Urodziny: {person.name} ({age} lat)",
                    "start": {
                        "date": this_year.isoformat(),
                        "timeZone": "Europe/Warsaw",
                    },
                    "end": {
                        "date": this_year.isoformat(),
                        "timeZone": "Europe/Warsaw",
                    },
                    "recurrence": [f"RRULE:FREQ=YEARLY"],
                    "reminders": {
                        "useDefault": False,
                        "overrides": [
                            {"method": "popup", "minutes": 7 * 24 * 60},  # 7 dni przed
                            {"method": "popup", "minutes": 24 * 60},       # 1 dzień przed
                        ],
                    },
                }

                self._api_call("POST", f"/calendars/{calendar_id}/events", event_data)
                count += 1
            except Exception as e:
                print(f"  ⚠️ Błąd sync urodzin {person.name}: {e}")

        return count


# ── Notion Backup ────────────────────────────────────────────────────────────

class NotionBackup:
    """Backup danych life management do Notion."""

    def __init__(self, db: LifeDB, notion_token: str = "", database_id: str = ""):
        self.db = db
        self.tracker = TimeTracker(db)
        self.people = PeopleManager(db)
        self.events = EventManager(db)
        self.habits = HabitTracker(db)

        if not notion_token:
            try:
                result = subprocess.run(
                    ["bws", "secret", "get", "NOTION_API_KEY"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    notion_token = result.stdout.strip()
            except Exception:
                pass

        self.token = notion_token or os.environ.get("NOTION_API_KEY", "")
        self.database_id = database_id

    def export_people_to_markdown(self) -> str:
        """Eksportuj listę osób jako markdown (do Notion)."""
        all_people = self.people.get_all_people()
        balance = self.people.get_balance_report()

        lines = [
            "# 👥 People CRM",
            f"Stan na: {date.today().isoformat()}",
            f"Liczba osób: {len(all_people)}",
            f"Overdue: {balance['overdue_count']}",
            "",
            "## Według kategorii",
            "",
        ]

        categories: dict[str, list] = {}
        for p in all_people:
            cat = p.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(p)

        for cat, people_list in categories.items():
            lines.append(f"### {cat} ({len(people_list)})")
            lines.append("")
            for p in people_list:
                bday = f"🎂 {p.birthday}" if p.birthday else ""
                last = f"📞 {p.last_contact[:10]}" if p.last_contact else "📞 brak kontaktu"
                lines.append(f"- **{p.name}** (prio {p.priority}) — {bday} {last}")
            lines.append("")

        return "\n".join(lines)

    def export_weekly_to_markdown(self) -> str:
        """Eksportuj raport tygodniowy jako markdown."""
        from life_cli import ReportGenerator
        rg = ReportGenerator(self.db)

        weekly = self.tracker.get_weekly_report()
        balance = self.people.get_balance_report()
        habit_report = self.habits.get_weekly_habit_report()

        lines = [
            f"# 📊 Raport tygodniowy",
            f"Tydzień: {weekly['week_start']} → {weekly['week_end']}",
            f"Średnio dziennie: {weekly['daily_average_hours']}h",
            "",
            "## ⏱️ Kategorie czasu",
            "",
        ]

        for cat, hours in weekly.get("by_category", {}).items():
            lines.append(f"- **{cat}**: {hours}h")

        lines.extend([
            "",
            "## 👥 Osoby",
            f"Overdue: {balance['overdue_count']}/{balance['total_people']}",
            "",
        ])

        for p in balance["people"]:
            if p["hours_last_30d"] > 0 or p["overdue"]:
                flag = "🔴" if p["overdue"] else "🟢"
                lines.append(f"- {flag} {p['name']}: {p['hours_last_30d']}h")

        lines.extend([
            "",
            "## 💊 Nawykowe trendy",
            "",
        ])

        for ht, data in habit_report.get("habits", {}).items():
            lines.append(f"- **{ht}**: {data['count']}x (śr. intensywność: {data['avg_intensity']})")

        return "\n".join(lines)

    def push_to_notion(self, content: str, title: str = "") -> bool:
        """Wyślij markdown do Notion (wymaga NOTION_API_KEY)."""
        if not self.token:
            print("❌ Brak NOTION_API_KEY. Ustaw w Bitwarden lub env.")
            return False

        import urllib.request

        # Tworzymy nową stronę
        data = {
            "parent": {"database_id": self.database_id} if self.database_id else {},
            "properties": {
                "title": {
                    "title": [{"text": {"content": title or f"Life Report {date.today()}"}}]
                }
            },
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                    },
                }
            ],
        }

        req = urllib.request.Request(
            "https://api.notion.com/v1/pages",
            data=json.dumps(data).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
                print(f"✅ Zapisano do Notion: {result.get('id', '?')}")
                return True
        except urllib.error.HTTPError as e:
            print(f"❌ Notion API error: {e.read().decode()}")
            return False


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Google Calendar Sync & Notion Backup — CLI")
        print()
        print("Komendy:")
        print("  gcal-export [dni]         — eksportuj bloki czasu do Google Calendar")
        print("  gcal-import [dni]         — importuj eventy z Google Calendar")
        print("  gcal-sync-birthdays       — dodaj urodziny do Google Calendar")
        print("  notion-people             — eksportuj listę osób jako markdown")
        print("  notion-weekly             — eksportuj raport tygodniowy jako markdown")
        print("  notion-push <tytuł>       — wyślij raport do Notion")
        return

    cmd = sys.argv[1]
    db_path = str(LIFE_DIR / "data" / "bot_life.db")
    if not os.path.exists(db_path):
        db_path = str(LIFE_DIR / "data" / "hermes_integration.db")

    db = LifeDB(db_path)

    if cmd == "gcal-export":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 7
        sync = GoogleCalendarSync(db)
        try:
            count = sync.export_blocks(days_back=days)
            print(f"✅ Wyeksportowano {count} bloków do Google Calendar")
        except Exception as e:
            print(f"❌ {e}")

    elif cmd == "gcal-import":
        days = int(sys.argv[2]) if len(sys.argv) >= 3 else 30
        sync = GoogleCalendarSync(db)
        try:
            count = sync.import_events(days_ahead=days)
            print(f"✅ Zaimportowano {count} eventów z Google Calendar")
        except Exception as e:
            print(f"❌ {e}")

    elif cmd == "gcal-sync-birthdays":
        sync = GoogleCalendarSync(db)
        try:
            count = sync.sync_birthdays_to_calendar()
            print(f"✅ Zsynchronizowano {count} urodzin do Google Calendar")
        except Exception as e:
            print(f"❌ {e}")

    elif cmd == "notion-people":
        nb = NotionBackup(db)
        print(nb.export_people_to_markdown())

    elif cmd == "notion-weekly":
        nb = NotionBackup(db)
        print(nb.export_weekly_to_markdown())

    elif cmd == "notion-push":
        title = sys.argv[2] if len(sys.argv) >= 3 else f"Life Report {date.today()}"
        nb = NotionBackup(db)
        content = nb.export_weekly_to_markdown()
        nb.push_to_notion(content, title)

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
