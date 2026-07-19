#!/usr/bin/env python3
"""
Telegram Bot — Life Management Quick Logger
============================================
Szybkie logowanie przez Telegram:
- /start — powitanie
- /praca, /rodzina, /hobby, /jedzenie... — start bloku czasu
- /stop — zakończ blok
- /pill — zaloguj pigułki
- /thought 7 — natarczywa myśl
- /snack 4 — podjadanie
- /brief — daily brief
- /attention — kto potrzebuje kontaktu
- /balance — balans czasu z osobami

Wymaga: TELEGRAM_BOT_TOKEN w Bitwarden (lub env)
"""

from __future__ import annotations

import sys
import os
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import (
    LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator,
)

LIFE_DIR = Path(__file__).parent
LIFE_CLI = LIFE_DIR / "life_cli.py"

# ── Bot Core ─────────────────────────────────────────────────────────────────

class LifeBot:
    """Telegram bot do szybkiego logowania."""

    CATEGORY_ALIASES = {
        "praca": "praca", "work": "praca",
        "rodzina": "rodzina", "family": "rodzina",
        "znajomi": "znajomi", "friends": "znajomi",
        "zdrowie": "zdrowie", "health": "zdrowie", "silownia": "zdrowie", "sport": "zdrowie",
        "jedzenie": "jedzenie", "food": "jedzenie", "obiad": "jedzenie",
        "hobby": "hobby", "gitara": "hobby", "czytanie": "hobby",
        "odpoczynek": "odpoczynek", "rest": "odpoczynek", "relaks": "odpoczynek",
        "nauka": "nauka", "learn": "nauka", "kurs": "nauka",
        "administracja": "administracja", "admin": "administracja", "zakupy": "administracja",
        "transport": "transport", "dojazd": "transport",
        "higiena": "higiena", "prysznic": "higiena",
        "inne": "inne", "other": "inne",
    }

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = str(LIFE_DIR / "data" / "bot_life.db")
        self.db = LifeDB(db_path)
        self.tracker = TimeTracker(self.db)
        self.people = PeopleManager(self.db)
        self.events = EventManager(self.db)
        self.habits = HabitTracker(self.db)
        self.reports = ReportGenerator(self.db)

    def handle(self, text: str) -> str:
        """Obsłuż komendę tekstową, zwróć odpowiedź."""
        text = text.strip()
        if not text:
            return self._help()

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().lstrip("/")
        arg = parts[1] if len(parts) > 1 else ""

        # Mapowanie komend
        handlers = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "praca": lambda a: self._start_block("praca", a),
            "work": lambda a: self._start_block("praca", a),
            "rodzina": lambda a: self._start_block("rodzina", a),
            "family": lambda a: self._start_block("rodzina", a),
            "znajomi": lambda a: self._start_block("znajomi", a),
            "friends": lambda a: self._start_block("znajomi", a),
            "zdrowie": lambda a: self._start_block("zdrowie", a),
            "health": lambda a: self._start_block("zdrowie", a),
            "silownia": lambda a: self._start_block("zdrowie", a),
            "jedzenie": lambda a: self._start_block("jedzenie", a),
            "food": lambda a: self._start_block("jedzenie", a),
            "obiad": lambda a: self._start_block("jedzenie", a),
            "hobby": lambda a: self._start_block("hobby", a),
            "odpoczynek": lambda a: self._start_block("odpoczynek", a),
            "rest": lambda a: self._start_block("odpoczynek", a),
            "nauka": lambda a: self._start_block("nauka", a),
            "learn": lambda a: self._start_block("nauka", a),
            "admin": lambda a: self._start_block("administracja", a),
            "zakupy": lambda a: self._start_block("administracja", a),
            "transport": lambda a: self._start_block("transport", a),
            "dojazd": lambda a: self._start_block("transport", a),
            "stop": self._cmd_stop,
            "koniec": self._cmd_stop,
            "pill": self._cmd_pill,
            "pills": self._cmd_pill,
            "pigułki": self._cmd_pill,
            "pigułka": self._cmd_pill,
            "thought": self._cmd_thought,
            "myśl": self._cmd_thought,
            "snack": self._cmd_snack,
            "podjadanie": self._cmd_snack,
            "brief": self._cmd_brief,
            "raport": self._cmd_brief,
            "attention": self._cmd_attention,
            "kto": self._cmd_attention,
            "balance": self._cmd_balance,
            "balans": self._cmd_balance,
            "today": self._cmd_today,
            "dziś": self._cmd_today,
            "week": self._cmd_week,
            "tydzień": self._cmd_week,
            "birthdays": self._cmd_birthdays,
            "urodziny": self._cmd_birthdays,
            "events": self._cmd_events,
            "wydarzenia": self._cmd_events,
            "people": self._cmd_people,
            "osoby": self._cmd_people,
            "woda": self._cmd_water,
            "water": self._cmd_water,
            "ćwiczenia": self._cmd_exercise,
            "cwiczenia": self._cmd_exercise,
            "exercise": self._cmd_exercise,
            "sen": self._cmd_sleep,
            "sleep": self._cmd_sleep,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(arg)
        else:
            # Spróbuj dopasować jako kategorię
            cat = self.CATEGORY_ALIASES.get(cmd)
            if cat:
                return self._start_block(cat, arg)
            return f"❓ Nie znam komendy '{cmd}'. /help — lista komend."

    def _help(self) -> str:
        return """🧬 Life Management Bot

⏱️ CZAS — wyślij kategorię by rozpocząć:
  /praca /rodzina /znajomi /zdrowie /jedzenie
  /hobby /odpoczynek /nauka /admin /transport
  /stop — zakończ blok

💊 NAWYKI:
  /pill — zaloguj pigułki
  /thought 7 — natarczywa myśl (1-10)
  /snack 4 — podjadanie (1-10)
  /woda 250 — szklanka wody (ml)
  /ćwiczenia 30 — trening (minuty)
  /sen 7.5 — godziny snu

📊 RAPORTY:
  /brief — daily brief
  /today — podsumowanie dnia
  /week — raport tygodniowy
  /attention — kto potrzebuje kontaktu
  /balance — balans czasu z osobami
  /birthdays — nadchodzące urodziny
  /events — nadchodzące wydarzenia
  /people — lista osób"""

    def _cmd_start(self, _: str) -> str:
        return f"🧬 Cześć! Jestem Life Management Bot.\n\n{self._help()}"

    def _cmd_help(self, _: str) -> str:
        return self._help()

    def _start_block(self, category: str, desc: str) -> str:
        block = self.tracker.start_block(category=category, description=desc)  # type: ignore[arg-type]
        emoji = {
            "praca": "💼", "rodzina": "👨‍👩‍👧", "znajomi": "👥",
            "zdrowie": "💪", "jedzenie": "🍽️", "hobby": "🎸",
            "odpoczynek": "😴", "nauka": "📚", "administracja": "📋",
            "transport": "🚗", "higiena": "🚿", "inne": "📌",
        }.get(category, "⏱️")
        return f"{emoji} START: {category}\n   {block.start_time[:19]}\n   /stop gdy skończysz"

    def _cmd_stop(self, desc: str) -> str:
        block = self.tracker.stop_block(description=desc)
        if not block:
            return "❌ Brak aktywnego bloku. Zacznij od /praca, /hobby itp."
        duration = self._format_duration(block.start_time, block.end_time)
        return f"⏹️ STOP: {block.category}\n   {duration}\n   {block.description or '—'}"

    def _cmd_pill(self, arg: str) -> str:
        val = "taken" if not arg or arg.lower() in ("taken", "tak", "yes", "wzięte") else arg
        self.habits.log("pills", val)
        streak = self.habits.get_streak("pills")
        fire = "🔥" * min(streak, 10)
        return f"💊 Pigułki: {val}\n   Seria: {streak} dni {fire}"

    def _cmd_thought(self, arg: str) -> str:
        try:
            intensity = int(arg) if arg else 5
        except ValueError:
            intensity = 5
        self.habits.log("intrusive_thought", "occurred", intensity=min(10, max(1, intensity)))
        return f"🧠 Natarczywa myśl: {intensity}/10\n   Zalogowane. Oddychaj. To tylko myśl."

    def _cmd_snack(self, arg: str) -> str:
        try:
            intensity = int(arg) if arg else 5
        except ValueError:
            intensity = 5
        self.habits.log("snacking", "occurred", intensity=min(10, max(1, intensity)))
        return f"🍪 Podjadanie: {intensity}/10\n   Zalogowane. Świadomość to pierwszy krok."

    def _cmd_water(self, arg: str) -> str:
        try:
            ml = int(arg) if arg else 250
        except ValueError:
            ml = 250
        self.habits.log("water", f"{ml}ml")
        return f"💧 Woda: +{ml}ml"

    def _cmd_exercise(self, arg: str) -> str:
        try:
            minutes = int(arg) if arg else 30
        except ValueError:
            minutes = 30
        self.habits.log("exercise", f"{minutes}min")
        return f"💪 Ćwiczenia: {minutes}min"

    def _cmd_sleep(self, arg: str) -> str:
        try:
            hours = float(arg) if arg else 7.0
        except ValueError:
            hours = 7.0
        self.habits.log("sleep", f"{hours}h")
        return f"😴 Sen: {hours}h"

    def _cmd_brief(self, _: str) -> str:
        return self.reports.daily_brief()

    def _cmd_today(self, _: str) -> str:
        summary = self.tracker.get_today_summary()
        lines = [f"📅 {summary['date']}", f"⏱️ {summary['total_hours']}h ({summary['coverage_pct']}% dnia)"]
        for cat, mins in summary.get("by_category", {}).items():
            lines.append(f"  {cat}: {mins/60:.1f}h")
        return "\n".join(lines)

    def _cmd_week(self, _: str) -> str:
        return self.reports.weekly_deep_dive()

    def _cmd_attention(self, _: str) -> str:
        needing = self.people.get_who_needs_attention(top_n=10)
        if not needing:
            return "✅ Wszyscy w normie!"
        lines = ["👥 Kto potrzebuje kontaktu:"]
        for p in needing:
            flag = "🔴" if p["overdue"] else "🟢"
            days = p["days_since_contact"] or "?"
            lines.append(f"  {flag} {p['name']} ({p['category']}) — {days}d | prio {p['priority']}")
        return "\n".join(lines)

    def _cmd_balance(self, _: str) -> str:
        report = self.people.get_balance_report()
        lines = [f"👥 Balans czasu (30 dni) — {report['total_people']} osób, {report['overdue_count']} overdue"]
        for p in report["people"]:
            if p["hours_last_30d"] > 0 or p["overdue"]:
                flag = "🔴" if p["overdue"] else "🟢"
                lines.append(f"  {flag} {p['name']:20s} {p['hours_last_30d']:5.1f}h | {p['days_since_contact']}d")
        return "\n".join(lines)

    def _cmd_birthdays(self, arg: str) -> str:
        try:
            days = int(arg) if arg else 30
        except ValueError:
            days = 30
        upcoming = self.people.get_upcoming_birthdays(days_ahead=days)
        if not upcoming:
            return f"🎂 Brak urodzin w ciągu {days} dni"
        lines = [f"🎂 Urodziny (za {days} dni):"]
        for b in upcoming:
            lines.append(f"  {'🎈' if b['days_until'] == 0 else '📅'} {b['name']} — {b['birthday']} (za {b['days_until']}d, {b['age']} lat)")
        return "\n".join(lines)

    def _cmd_events(self, arg: str) -> str:
        try:
            days = int(arg) if arg else 7
        except ValueError:
            days = 7
        upcoming = self.events.get_upcoming_events(days_ahead=days)
        if not upcoming:
            return f"📅 Brak wydarzeń w ciągu {days} dni"
        lines = [f"📅 Wydarzenia (za {days} dni):"]
        for e in upcoming:
            lines.append(f"  📌 {e['event_date']} — {e['title']} ({e['event_type']})")
        return "\n".join(lines)

    def _cmd_people(self, arg: str) -> str:
        cat = arg.strip() if arg else None
        all_people = self.people.get_all_people(category=cat)  # type: ignore[arg-type]
        lines = [f"👥 Osoby ({len(all_people)}):"]
        for p in all_people[:20]:
            lines.append(f"  [{p.id}] {p.name} ({p.category}) — prio {p.priority}")
        if len(all_people) > 20:
            lines.append(f"  ... i {len(all_people) - 20} więcej")
        return "\n".join(lines)

    @staticmethod
    def _format_duration(start: str, end: str) -> str:
        try:
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
            minutes = int((e - s).total_seconds() / 60)
            if minutes >= 60:
                return f"{minutes // 60}h {minutes % 60}m"
            return f"{minutes}m"
        except Exception:
            return "?"


# ── Polling Bot Runner ───────────────────────────────────────────────────────

async def run_polling(token: str, db_path: str = ""):
    """Uruchom bota w trybie long polling (bez zewnętrznych bibliotek)."""
    import aiohttp

    bot = LifeBot(db_path)
    offset = 0
    base_url = f"https://api.telegram.org/bot{token}"

    print(f"🤖 Life Management Bot — start polling...")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(
                    f"{base_url}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                ) as resp:
                    data = await resp.json()

                if not data.get("ok"):
                    print(f"⚠️ API error: {data}")
                    await asyncio.sleep(5)
                    continue

                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    msg = update.get("message")
                    if not msg:
                        continue

                    chat_id = msg["chat"]["id"]
                    text = msg.get("text", "")
                    user = msg.get("from", {}).get("first_name", "?")

                    print(f"  📩 {user}: {text[:50]}")

                    reply = bot.handle(text)

                    # Wyślij odpowiedź
                    async with session.post(
                        f"{base_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": reply[:4000],  # Telegram limit
                            "parse_mode": "HTML",
                        },
                    ) as send_resp:
                        if send_resp.status != 200:
                            print(f"  ⚠️ Send error: {await send_resp.text()}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"  ❌ Error: {e}")
                await asyncio.sleep(5)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI do uruchomienia bota."""
    if len(sys.argv) < 2:
        print("Life Management Telegram Bot")
        print()
        print("Użycie:")
        print("  python3 telegram_bot.py run [token]     — uruchom bota (long polling)")
        print("  python3 telegram_bot.py test [token]    — test: wyślij /brief i pokaż odpowiedź")
        print()
        print("Token z Bitwarden: TELEGRAM_BOT_TOKEN lub jako argument")
        return

    cmd = sys.argv[1]

    # Pobierz token
    token = ""
    if len(sys.argv) >= 3:
        token = sys.argv[2]
    else:
        # Spróbuj z Bitwarden
        try:
            result = subprocess.run(
                ["bws", "secret", "get", "TELEGRAM_BOT_TOKEN"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                token = result.stdout.strip()
        except Exception:
            pass

    if not token:
        # Spróbuj z env
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    if not token:
        print("❌ Brak tokena. Podaj jako argument lub ustaw TELEGRAM_BOT_TOKEN w env/Bitwarden.")
        return

    if cmd == "run":
        asyncio.run(run_polling(token))
    elif cmd == "test":
        bot = LifeBot()
        print("=== /brief ===")
        print(bot.handle("/brief"))
        print()
        print("=== /attention ===")
        print(bot.handle("/attention"))
        print()
        print("=== /pill ===")
        print(bot.handle("/pill"))
        print()
        print("=== /praca test ===")
        print(bot.handle("/praca test"))
        print()
        print("=== /stop ===")
        print(bot.handle("/stop"))
    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
