#!/usr/bin/env python3
"""
Push Notifications — ntfy.sh integration for Life Management
=============================================================
Darmowe powiadomienia push na telefon przez ntfy.sh.
Bez konta, bez API key, zero konfiguracji po stronie serwera.

Użycie:
  python3 push_notifications.py setup    — wygeneruj unikalny topic
  python3 push_notifications.py test     — wyślij testowe powiadomienie
  python3 push_notifications.py send "tekst" — wyślij powiadomienie
  python3 push_notifications.py daily    — wyślij daily brief
  python3 push_notifications.py alerts   — wyślij alerty

Na telefonie:
  Zainstaluj ntfy z Google Play / App Store
  Subskrybuj topic wyświetlony przez 'setup'
"""

from __future__ import annotations

import sys
import os
import json
import uuid
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator

LIFE_DIR = Path(__file__).parent
CONFIG_PATH = LIFE_DIR / "data" / "push_config.json"

# ── ntfy.sh client ───────────────────────────────────────────────────────────

class PushNotifier:
    """Wysyła powiadomienia przez ntfy.sh."""

    def __init__(self, topic: str = "", server: str = "https://ntfy.sh"):
        self.server = server
        self.topic = topic or self._load_topic()
        self.db = LifeDB(str(LIFE_DIR / "data" / "hermes_integration.db"))
        self.tracker = TimeTracker(self.db)
        self.people = PeopleManager(self.db)
        self.events = EventManager(self.db)
        self.habits = HabitTracker(self.db)
        self.reports = ReportGenerator(self.db)

    def _load_topic(self) -> str:
        """Wczytaj topic z configu lub wygeneruj nowy."""
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text())
            return cfg.get("topic", "")
        return ""

    def _save_topic(self, topic: str):
        """Zapisz topic do configu."""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps({"topic": topic, "created_at": datetime.now().isoformat()}))

    def setup(self) -> str:
        """Wygeneruj unikalny topic i pokaż instrukcję."""
        if not self.topic:
            self.topic = f"life-mgmt-{uuid.uuid4().hex[:12]}"
            self._save_topic(self.topic)

        return (
            f"📱 Push notifications gotowe!\n"
            f"\n"
            f"Topic: {self.topic}\n"
            f"\n"
            f"Na telefonie:\n"
            f"  1. Zainstaluj ntfy (Google Play / App Store)\n"
            f"  2. Otwórz → + (dodaj subskrypcję)\n"
            f"  3. Wpisz: {self.topic}\n"
            f"  4. Gotowe! Powiadomienia będą przychodzić na telefon.\n"
            f"\n"
            f"Test: python3 push_notifications.py test"
        )

    def send(self, title: str, message: str, priority: str = "default", tags: str = "") -> bool:
        """Wyślij powiadomienie przez ntfy.sh."""
        if not self.topic:
            return False

        url = f"{self.server}/{self.topic}"

        # ntfy.sh headers must be ASCII — strip emoji from title, put in body
        import re
        ascii_title = re.sub(r'[^\x00-\x7F]+', '', title).strip()
        if not ascii_title:
            ascii_title = "Life Management"

        headers = {
            "Title": ascii_title,
            "Priority": priority,
            "Tags": tags,
        }

        # Prepend emoji title to message body
        if title != ascii_title:
            message = f"{title}\n\n{message}"

        data = message.encode("utf-8")

        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"  ⚠️ Push failed: {e}")
            return False

    def send_pill_reminder(self, time_of_day: str = "morning") -> bool:
        """Przypomnienie o pigułkach."""
        streak = self.habits.get_streak("pills")
        if time_of_day == "morning":
            return self.send(
                "💊 Poranne pigułki",
                f"Czas na poranne pigułki! Seria: {streak} dni. Nie przerwij jej!",
                priority="high",
                tags="pill,alarm",
            )
        else:
            return self.send(
                "💊 Wieczorne pigułki",
                f"Czas na wieczorne pigułki. Seria: {streak} dni.",
                priority="high",
                tags="pill,moon",
            )

    def send_birthday_alert(self) -> int:
        """Alert o dzisiejszych urodzinach."""
        birthdays = self.people.get_upcoming_birthdays(days_ahead=1)
        count = 0
        for b in birthdays:
            if b["days_until"] == 0:
                self.send(
                    f"🎂 Urodziny: {b['name']}",
                    f"Dziś {b['name']} kończy {b['age']} lat! Wyślij życzenia!",
                    priority="max",
                    tags="birthday,cake",
                )
                count += 1
            elif b["days_until"] == 1:
                self.send(
                    f"🎂 Jutro urodziny: {b['name']}",
                    f"Jutro {b['name']} kończy {b['age']} lat. Przygotuj życzenia!",
                    priority="high",
                    tags="birthday",
                )
                count += 1
        return count

    def send_overdue_alert(self) -> int:
        """Alert o zaniedbanych kontaktach."""
        needing = self.people.get_who_needs_attention(top_n=5)
        overdue = [p for p in needing if p["overdue"]]
        if not overdue:
            return 0

        names = ", ".join(p["name"] for p in overdue[:3])
        self.send(
            f"🔴 Zaniedbane kontakty ({len(overdue)})",
            f"Brak kontaktu z: {names}. Znajdź dziś chwilę na telefon lub wiadomość.",
            priority="high",
            tags="warning,people",
        )
        return len(overdue)

    def send_daily_brief(self) -> bool:
        """Wyślij daily brief jako powiadomienie."""
        summary = self.tracker.get_today_summary()
        needing = self.people.get_who_needs_attention(top_n=3)
        birthdays = self.people.get_upcoming_birthdays(days_ahead=1)

        lines = [f"⏱️ {summary['total_hours']}h śledzone ({summary['coverage_pct']}%)"]

        # Top 3 kategorie
        top_cats = list(summary.get("by_category", {}).items())[:3]
        for cat, mins in top_cats:
            lines.append(f"  {cat}: {mins/60:.1f}h")

        # Alerty
        overdue = [p for p in needing if p["overdue"]]
        if overdue:
            lines.append(f"🔴 {len(overdue)} overdue kontaktów")

        if birthdays:
            lines.append(f"🎂 Dziś urodziny: {birthdays[0]['name']}" if birthdays[0]["days_until"] == 0 else "")

        pill_streak = self.habits.get_streak("pills")
        lines.append(f"💊 Pigułki: {pill_streak}d")

        return self.send(
            "📊 Daily Brief",
            "\n".join(lines),
            priority="default",
            tags="chart,calendar",
        )

    def send_all_alerts(self) -> dict:
        """Wyślij wszystkie alerty i zwróć podsumowanie."""
        results = {
            "birthdays": self.send_birthday_alert(),
            "overdue": self.send_overdue_alert(),
        }

        # Pigułki — tylko jeśli jeszcze nie wzięte
        today_habits = self.habits.get_today_habits()
        pills_today = today_habits.get("pills", [])
        now = datetime.now()
        if not pills_today:
            if now.hour < 12:
                results["pills_morning"] = self.send_pill_reminder("morning")
            elif now.hour >= 20:
                results["pills_evening"] = self.send_pill_reminder("evening")

        return results


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Push Notifications — CLI")
        print()
        print("Komendy:")
        print("  setup     — wygeneruj topic i pokaż instrukcję")
        print("  test      — wyślij testowe powiadomienie")
        print("  send MSG  — wyślij powiadomienie o treści MSG")
        print("  daily     — wyślij daily brief")
        print("  alerts    — wyślij wszystkie alerty (pigułki, urodziny, overdue)")
        print("  pill      — wyślij przypomnienie o pigułkach")
        return

    cmd = sys.argv[1]
    pn = PushNotifier()

    if cmd == "setup":
        print(pn.setup())

    elif cmd == "test":
        ok = pn.send(
            "🧪 Test powiadomienia",
            "Life Management System działa! Jeśli to widzisz — powiadomienia są skonfigurowane poprawnie.",
            tags="check",
        )
        print("✅ Wysłano!" if ok else "❌ Błąd wysyłania")

    elif cmd == "send" and len(sys.argv) >= 3:
        msg = " ".join(sys.argv[2:])
        ok = pn.send("📬 Life Management", msg, tags="incoming")
        print("✅ Wysłano!" if ok else "❌ Błąd")

    elif cmd == "daily":
        ok = pn.send_daily_brief()
        print("✅ Daily brief wysłany!" if ok else "❌ Błąd")

    elif cmd == "alerts":
        results = pn.send_all_alerts()
        total = sum(1 for v in results.values() if v)
        print(f"✅ Wysłano {total} alertów: {results}")

    elif cmd == "pill":
        now = datetime.now()
        time_of_day = "morning" if now.hour < 12 else "evening"
        ok = pn.send_pill_reminder(time_of_day)
        print(f"✅ Przypomnienie ({time_of_day}) wysłane!" if ok else "❌ Błąd")

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
