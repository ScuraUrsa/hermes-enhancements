#!/usr/bin/env python3
"""
Life Management — Unified Launcher
====================================
Jedno miejsce do uruchomienia wszystkiego.

Usage:
  python3 life.py seed          — wypełnij bazę 50 osobami + danymi
  python3 life.py dashboard     — uruchom dashboard HTTP (port 8099)
  python3 life.py bot           — uruchom Telegram bota (wymaga tokena)
  python3 life.py brief         — daily brief
  python3 life.py week          — raport tygodniowy
  python3 life.py status        — pełny status (czas + osoby + gamifikacja)
  python3 life.py cron-setup    — skonfiguruj cron jobs
  python3 life.py test          — uruchom wszystkie testy
  python3 life.py export        — eksportuj dane (JSON)
  python3 life.py import <file> — importuj dane (JSON)
"""

from __future__ import annotations

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

LIFE_DIR = Path(__file__).parent
sys.path.insert(0, str(LIFE_DIR))


def cmd_seed():
    """Wypełnij bazę danymi testowymi."""
    from hermes_integration import SeedGenerator
    from life_cli import LifeDB

    db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    db = LifeDB(db_path)
    SeedGenerator.seed_sample_data(db)
    print("✅ Baza wypełniona: 50 osób, 7 dni danych, wydarzenia, nawyki")


def cmd_dashboard():
    """Uruchom dashboard HTTP."""
    from dashboard_server import main
    main()


def cmd_bot():
    """Uruchom Telegram bota."""
    from telegram_bot import main as bot_main
    bot_main()


def cmd_brief():
    """Daily brief."""
    from life_cli import LifeDB, ReportGenerator
    db_path = _find_db()
    db = LifeDB(db_path)
    rg = ReportGenerator(db)
    print(rg.daily_brief())


def cmd_week():
    """Raport tygodniowy."""
    from life_cli import LifeDB, ReportGenerator
    db_path = _find_db()
    db = LifeDB(db_path)
    rg = ReportGenerator(db)
    print(rg.weekly_deep_dive())


def cmd_status():
    """Pełny status."""
    from life_cli import LifeDB, TimeTracker, PeopleManager, HabitTracker
    from gamification import Gamification

    db_path = _find_db()
    db = LifeDB(db_path)
    tracker = TimeTracker(db)
    people = PeopleManager(db)
    habits = HabitTracker(db)
    g = Gamification(db)

    # Czas
    summary = tracker.get_today_summary()
    print("⏱️  CZAS DZIŚ")
    print(f"   Śledzone: {summary['total_hours']}h ({summary['coverage_pct']}% dnia)")
    for cat, mins in summary.get("by_category", {}).items():
        print(f"   {cat}: {mins/60:.1f}h")

    # Osoby
    balance = people.get_balance_report()
    print(f"\n👥 OSOBY ({balance['total_people']})")
    print(f"   Overdue: {balance['overdue_count']}")

    # Gamifikacja
    lvl = g.get_level()
    print(f"\n🧬 GAMIFIKACJA")
    print(f"   {lvl['name']} — Level {lvl['level']}")
    print(f"   XP: {lvl['xp']} / {lvl['xp_to_next']} ({lvl['progress_pct']}%)")

    # Streaki
    print(f"\n💊 STREAKI")
    print(f"   Pigułki: {habits.get_streak('pills')} dni")
    print(f"   Ćwiczenia: {habits.get_streak('exercise')} dni")

    # Alerty
    needing = people.get_who_needs_attention(5)
    overdue = [p for p in needing if p["overdue"]]
    if overdue:
        print(f"\n🔔 ALERTY")
        for p in overdue:
            print(f"   🔴 {p['name']} — {p['days_since_contact']}d bez kontaktu")


def cmd_cron_setup():
    """Skonfiguruj cron jobs."""
    from hermes_integration import CronManager
    CronManager.setup_all()


def cmd_test():
    """Uruchom wszystkie testy."""
    test_files = [
        "test_life_cli.py",
        "test_health.py",
        "test_mind.py",
    ]
    for tf in test_files:
        path = LIFE_DIR / tf
        if path.exists():
            print(f"\n{'='*60}")
            print(f"🧪 {tf}")
            print(f"{'='*60}")
            result = subprocess.run(
                ["python3", "-m", "pytest", str(path), "-v", "--tb=short"],
                cwd=str(LIFE_DIR),
                capture_output=True,
                text=True,
                timeout=60,
            )
            print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
            if result.returncode != 0:
                print(result.stderr[-500:])


def cmd_export():
    """Eksportuj dane do JSON."""
    from life_cli import LifeDB
    db_path = _find_db()
    db = LifeDB(db_path)

    data = {
        "exported_at": datetime.now().isoformat(),
        "people": db.execute("SELECT * FROM people"),
        "time_blocks": db.execute("SELECT * FROM time_blocks ORDER BY start_time DESC LIMIT 1000"),
        "events": db.execute("SELECT * FROM events"),
        "habit_log": db.execute("SELECT * FROM habit_log ORDER BY timestamp DESC LIMIT 1000"),
    }

    output_path = LIFE_DIR / "data" / f"export_{date.today().isoformat()}.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    print(f"✅ Wyeksportowano do: {output_path}")
    print(f"   Osoby: {len(data['people'])}")
    print(f"   Bloki czasu: {len(data['time_blocks'])}")
    print(f"   Wydarzenia: {len(data['events'])}")
    print(f"   Logi nawyków: {len(data['habit_log'])}")


def cmd_import_(filepath: str):
    """Importuj dane z JSON."""
    from life_cli import LifeDB
    db_path = _find_db()
    db = LifeDB(db_path)

    data = json.loads(Path(filepath).read_text())

    for person in data.get("people", []):
        person.pop("id", None)
        db.insert("people", person)

    for block in data.get("time_blocks", []):
        block.pop("id", None)
        db.insert("time_blocks", block)

    for event in data.get("events", []):
        event.pop("id", None)
        db.insert("events", event)

    for log in data.get("habit_log", []):
        log.pop("id", None)
        db.insert("habit_log", log)

    print(f"✅ Zaimportowano:")
    print(f"   Osoby: {len(data.get('people', []))}")
    print(f"   Bloki: {len(data.get('time_blocks', []))}")
    print(f"   Eventy: {len(data.get('events', []))}")
    print(f"   Logi: {len(data.get('habit_log', []))}")


def _find_db() -> str:
    """Znajdź aktywną bazę danych."""
    candidates = [
        LIFE_DIR / "data" / "hermes_integration.db",
        LIFE_DIR / "data" / "bot_life.db",
        LIFE_DIR / "data" / "life_management.db",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(candidates[0])


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    commands = {
        "seed": cmd_seed,
        "dashboard": cmd_dashboard,
        "bot": cmd_bot,
        "brief": cmd_brief,
        "week": cmd_week,
        "status": cmd_status,
        "cron-setup": cmd_cron_setup,
        "test": cmd_test,
        "export": cmd_export,
    }

    if cmd in commands:
        commands[cmd]()
    elif cmd == "import" and len(sys.argv) >= 3:
        cmd_import_(sys.argv[2])
    else:
        print(f"❌ Nieznana komenda: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
