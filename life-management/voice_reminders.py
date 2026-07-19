#!/usr/bin/env python3
"""
Voice Reminders — Hermes TTS integration for Life Management
=============================================================
Generuje przypomnienia głosowe dla:
- Pigułki (rano i wieczorem)
- Urodziny (dzień przed i w dniu)
- Overdue kontakty
- Daily brief

Używa Hermes text_to_speech (Edge TTS lub ElevenLabs).
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from datetime import date, datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import LifeDB, PeopleManager, EventManager, HabitTracker, TimeTracker

LIFE_DIR = Path(__file__).parent


class VoiceReminder:
    """Generator przypomnień głosowych."""

    def __init__(self, db: LifeDB):
        self.db = db
        self.people = PeopleManager(db)
        self.events = EventManager(db)
        self.habits = HabitTracker(db)
        self.tracker = TimeTracker(db)

    def pill_reminder(self, time_of_day: str = "morning") -> str:
        """Przypomnienie o pigułkach."""
        streak = self.habits.get_streak("pills")
        if time_of_day == "morning":
            return (
                f"Dzień dobry! Czas na poranne pigułki. "
                f"Twoja obecna seria to {streak} dni. Nie przerwiesz jej, prawda?"
            )
        else:
            return (
                f"Dobry wieczór. Czas na wieczorne pigułki. "
                f"Seria {streak} dni. Pamiętaj, zdrowie to podstawa."
            )

    def birthday_reminder(self) -> list[str]:
        """Przypomnienia o urodzinach."""
        reminders = []
        birthdays = self.people.get_upcoming_birthdays(days_ahead=2)

        for b in birthdays:
            if b["days_until"] == 0:
                reminders.append(
                    f"Dziś są urodziny {b['name']}! Kończy {b['age']} lat. "
                    f"Wyślij życzenia — to ważne."
                )
            elif b["days_until"] == 1:
                reminders.append(
                    f"Jutro są urodziny {b['name']}. Będzie mieć {b['age']} lat. "
                    f"Przygotuj życzenia lub prezent."
                )

        return reminders

    def overdue_contact_reminder(self) -> str:
        """Przypomnienie o zaniedbanych kontaktach."""
        needing = self.people.get_who_needs_attention(top_n=3)
        overdue = [p for p in needing if p["overdue"]]

        if not overdue:
            return ""

        names = ", ".join(p["name"] for p in overdue[:3])
        return (
            f"Uwaga! Zaniedbujesz kontakty. {names} — "
            f"dawno się nie odzywałeś. Znajdź dziś chwilę na kontakt."
        )

    def daily_brief_voice(self) -> str:
        """Głosowe podsumowanie dnia."""
        summary = self.tracker.get_today_summary()
        needing = self.people.get_who_needs_attention(top_n=3)
        birthdays = self.people.get_upcoming_birthdays(days_ahead=1)

        parts = [f"Dziś {date.today().strftime('%A')}. "]

        if summary["total_hours"] > 0:
            parts.append(f"Śledziłeś {summary['total_hours']} godzin. ")
            top_cat = list(summary.get("by_category", {}).keys())
            if top_cat:
                parts.append(f"Najwięcej czasu na {top_cat[0]}. ")

        overdue = [p for p in needing if p["overdue"]]
        if overdue:
            parts.append(f"Powinieneś skontaktować się z {overdue[0]['name']}. ")

        if birthdays:
            parts.append(f"Pamiętaj — jutro urodziny {birthdays[0]['name']}. ")

        pill_streak = self.habits.get_streak("pills")
        if pill_streak > 0:
            parts.append(f"Seria pigułek: {pill_streak} dni. Tak trzymaj!")

        return " ".join(parts)

    def generate_all(self) -> list[dict]:
        """Generuj wszystkie przypomnienia jako listę (type, text)."""
        reminders = []

        # Pigułki — sprawdź czy dziś wzięte
        today_habits = self.habits.get_today_habits()
        pills_today = today_habits.get("pills", [])
        now = datetime.now()

        if not pills_today:
            if now.hour < 12:
                reminders.append({"type": "pill_morning", "text": self.pill_reminder("morning")})
            else:
                reminders.append({"type": "pill_missed", "text": self.pill_reminder("evening")})

        # Urodziny
        for text in self.birthday_reminder():
            reminders.append({"type": "birthday", "text": text})

        # Overdue kontakty
        overdue_text = self.overdue_contact_reminder()
        if overdue_text:
            reminders.append({"type": "overdue_contact", "text": overdue_text})

        return reminders


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Voice Reminders — CLI")
        print()
        print("Komendy:")
        print("  generate     — wygeneruj wszystkie przypomnienia (tekst)")
        print("  speak        — wygeneruj i odtwórz przez TTS")
        print("  brief        — daily brief głosowy")
        return

    cmd = sys.argv[1]
    db_path = str(LIFE_DIR / "data" / "bot_life.db")
    if not os.path.exists(db_path):
        db_path = str(LIFE_DIR / "data" / "hermes_integration.db")

    db = LifeDB(db_path)
    vr = VoiceReminder(db)

    if cmd == "generate":
        reminders = vr.generate_all()
        for r in reminders:
            print(f"[{r['type']}] {r['text']}")
            print()

    elif cmd == "speak":
        reminders = vr.generate_all()
        for r in reminders:
            print(f"🔊 [{r['type']}] {r['text'][:80]}...")
            # Hermes TTS — wywołanie przez text_to_speech
            # (wymaga aktywnego Hermesa)
            try:
                import subprocess
                subprocess.run(
                    ["hermes", "tts", r["text"]],
                    capture_output=True, timeout=30,
                )
            except Exception as e:
                print(f"  ⚠️ TTS error: {e}")

    elif cmd == "brief":
        text = vr.daily_brief_voice()
        print(text)

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
