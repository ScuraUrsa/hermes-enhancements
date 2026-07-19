"""
Life Management System — CLI.
Komendy do zarządzania czasem, ludźmi i zdrowiem z terminala.

Usage:
    python -m life_management.src.cli track start work_deep
    python -m life_management.src.cli track stop
    python -m life_management.src.cli track status
    python -m life_management.src.cli people list
    python -m life_management.src.cli people neglected
    python -m life_management.src.cli people birthdays
    python -m life_management.src.cli report daily
    python -m life_management.src.cli report weekly
    python -m life_management.src.cli report balance
    python -m life_management.src.cli health log --pills --sleep 7.5 --mood 7
    python -m life_management.src.cli focus start --task "kodowanie"
    python -m life_management.src.cli focus stop
    python -m life_management.src.cli init --sample
"""

from __future__ import annotations

import sys
import json
import argparse
from datetime import datetime, timezone, date
from typing import Optional

from .schema import init_db
from .time_tracker import TimeTracker, CATEGORIES as TIME_CATEGORIES, CATEGORY_LABELS
from .people_crm import PeopleCRM, CATEGORIES as PEOPLE_CATEGORIES
from .reporter import Reporter


def cmd_track_start(args):
    """Start tracking a time block."""
    tracker = TimeTracker()
    block_id = tracker.start(
        category=args.category,
        planned=args.planned,
        energy=args.energy,
        notes=args.notes,
    )
    tracker.close()
    print(f"▶️  Started block #{block_id}: {CATEGORY_LABELS.get(args.category, args.category)}")
    if args.energy:
        print(f"   Energia: {args.energy}/10")
    return block_id


def cmd_track_stop(args):
    """Stop the active time block."""
    tracker = TimeTracker()
    active = tracker.get_active_block()
    if not active:
        print("❌ Brak aktywnego bloku")
        tracker.close()
        return

    result = tracker.stop(
        active["id"],
        focus=args.focus,
        satisfaction=args.satisfaction,
        notes=args.notes,
    )
    tracker.close()

    print(f"⏹️  Zatrzymano block #{result['id']}")
    print(f"   Kategoria: {CATEGORY_LABELS.get(result['category'], result['category'])}")
    print(f"   Czas: {result['duration_minutes']} min ({result['duration_blocks']} bloków)")
    if result.get("focus"):
        print(f"   Focus: {result['focus']}/10")
    if result.get("satisfaction"):
        print(f"   Satysfakcja: {result['satisfaction']}/10")


def cmd_track_status(args):
    """Show current tracking status."""
    tracker = TimeTracker()
    stats = tracker.stats()
    tracker.close()

    t = stats["today"]
    print("📊 DZIŚ:")
    print(f"   Łącznie: {t['total_hours']}h ({t['total_minutes']} min)")
    print(f"   Głęboka praca: {t['breakdown'].get('work_deep', 0)} min ({stats['deep_work_ratio_pct']}%)")
    print(f"   Zmarnowane: {t['breakdown'].get('waste', 0)} min ({stats['waste_ratio_pct']}%)")
    print(f"   Czas z ludźmi: {stats['people_minutes_today']} min")

    if t["active_block"]:
        ab = t["active_block"]
        print(f"\n   🔴 AKTYWNY: {CATEGORY_LABELS.get(ab['category'], ab['category'])} ({ab['elapsed_minutes']} min)")

    print(f"\n📅 TYDZIEŃ: {stats['week']['total_hours']}h")


def cmd_people_list(args):
    """List people."""
    crm = PeopleCRM()
    people = crm.get_all_people(
        category=args.category,
        order_by=args.sort,
    )
    crm.close()

    if args.json:
        print(json.dumps(people, indent=2, ensure_ascii=False))
        return

    print(f"👥 Osoby ({len(people)}):")
    for p in people:
        last = p["last_contact"] or "nigdy"
        if last != "nigdy":
            last = last[:10]
        print(f"  [{p['priority']}] {p['name']} ({p['category']}) — ostatni kontakt: {last}")


def cmd_people_neglected(args):
    """Show neglected people."""
    crm = PeopleCRM()
    neglected = crm.get_neglected(days_threshold=args.days)
    crm.close()

    if not neglected:
        print("✅ Wszyscy w kontakcie!")
        return

    print(f"🔴 Zaniedbane osoby ({len(neglected)}):")
    for p in neglected:
        print(f"  [{p['urgency']}/10] {p['name']} — {p['days_since_contact']} dni bez kontaktu (próg: {p['threshold_days']}d)")


def cmd_people_birthdays(args):
    """Show upcoming birthdays."""
    crm = PeopleCRM()
    birthdays = crm.get_upcoming_birthdays(days_ahead=args.days)
    crm.close()

    if not birthdays:
        print("🎂 Brak urodzin w najbliższym czasie")
        return

    print(f"🎂 Nadchodzące urodziny ({len(birthdays)}):")
    for b in birthdays:
        age_str = f" ({b['age']} lat)" if b.get("age") else ""
        print(f"  {b['days_until']}d — {b['name']}{age_str} — {b['birthday_date']}")


def cmd_report_daily(args):
    """Daily briefing."""
    reporter = Reporter()
    briefing = reporter.daily_briefing()
    reporter.close()

    if args.json:
        print(json.dumps(briefing, indent=2, ensure_ascii=False))
        return

    print("📋 DAILY BRIEFING")
    print(f"   Data: {briefing['date']}")
    print(f"   Czas: {briefing['time']['total_hours']}h")

    # Alerts
    if briefing["alerts"]:
        print("\n   ⚠️  ALERTY:")
        for a in briefing["alerts"]:
            print(f"      {a['message']}")

    # People
    if briefing["people"]["to_contact_today"]:
        print(f"\n   👥 Do kontaktu:")
        for p in briefing["people"]["to_contact_today"]:
            print(f"      {p['name']} — {p['days_since_contact']}d bez kontaktu")

    # Birthdays
    if briefing["people"]["upcoming_birthdays"]:
        print(f"\n   🎂 Urodziny:")
        for b in briefing["people"]["upcoming_birthdays"]:
            print(f"      {b['days_until']}d — {b['name']}")

    # Health
    if briefing["health"].get("has_data"):
        h = briefing["health"]
        print(f"\n   ❤️ Zdrowie:")
        print(f"      Sen: {h.get('sleep_hours', '?')}h | Nastrój: {h.get('mood', '?')}/10")
        print(f"      Pigułki: {'✅' if h.get('pills_taken') else '❌'}")
        print(f"      Podjadanie: {h.get('snacking_episodes', 0)}x")
        print(f"      Natarczywe myśli: {h.get('intrusive_thoughts', 0)}")

    # Habits
    if briefing["habits"]["total"] > 0:
        print(f"\n   ✅ Nawyki: {briefing['habits']['completed']}/{briefing['habits']['total']} ({briefing['habits']['rate_pct']}%)")


def cmd_report_weekly(args):
    """Weekly summary."""
    reporter = Reporter()
    summary = reporter.weekly_summary()
    reporter.close()

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    print("📊 WEEKLY SUMMARY")
    print(f"   Tydzień: {summary['week']}")
    print(f"   Czas: {summary['time']['total_hours']}h")

    # Time breakdown
    print("\n   ⏱️  Czas:")
    for cat, mins in summary["time"]["breakdown"].items():
        if mins > 0:
            label = CATEGORY_LABELS.get(cat, cat)
            pct = round(mins / max(summary["time"]["total_minutes"], 1) * 100, 1)
            print(f"      {label}: {mins} min ({pct}%)")

    # People
    print(f"\n   👥 Ludzie:")
    print(f"      W kontakcie: {summary['people']['total'] - summary['people']['neglected']}")
    print(f"      Zaniedbani: {summary['people']['neglected']}")
    if summary["people"]["neglected_list"]:
        for p in summary["people"]["neglected_list"]:
            print(f"         {p['name']} — {p['days_since_contact']}d")

    # Health
    if summary["health"].get("has_data"):
        h = summary["health"]
        print(f"\n   ❤️ Zdrowie:")
        print(f"      Sen: {h.get('avg_sleep_hours', '?')}h | Nastrój: {h.get('avg_mood', '?')}/10")
        print(f"      Ćwiczenia: {h.get('total_exercise_minutes', 0)} min")
        print(f"      Pigułki: {h.get('pills_adherence_pct', 0)}%")
        print(f"      Podjadanie: {h.get('total_snacking', 0)}x")
        print(f"      Natarczywe myśli: {h.get('total_intrusive_thoughts', 0)}")

    # Alerts
    if summary["alerts"]:
        print(f"\n   ⚠️  ALERTY:")
        for a in summary["alerts"]:
            print(f"      {a['message']}")


def cmd_report_balance(args):
    """People balance report."""
    reporter = Reporter()
    balance = reporter.balance_alert()
    reporter.close()

    if args.json:
        print(json.dumps(balance, indent=2, ensure_ascii=False))
        return

    print("⚖️  BALANCE REPORT")
    print(f"   Osób: {balance['total_people']}")
    print(f"   🔴 Krytyczne: {len(balance['critical'])}")
    print(f"   🟡 Ostrzeżenia: {len(balance['warning'])}")
    print(f"   🟢 OK: {balance['healthy_count']}")

    if balance["critical"]:
        print(f"\n   🔴 KRYTYCZNE (zaniedbani):")
        for p in balance["critical"]:
            print(f"      {p['name']} — score: {p['balance_score']}, {p['actual_minutes_this_week']}/{p['target_minutes_per_week']} min")

    if balance["warning"]:
        print(f"\n   🟡 OSTRZEŻENIA:")
        for p in balance["warning"]:
            print(f"      {p['name']} — score: {p['balance_score']}")


def cmd_health_log(args):
    """Log health data for today."""
    from .schema import get_db
    conn = get_db()
    today = date.today().isoformat()

    fields = {}
    if args.pills is not None:
        fields["pills_taken"] = 1 if args.pills else 0
    if args.sleep is not None:
        fields["sleep_hours"] = args.sleep
    if args.sleep_quality is not None:
        fields["sleep_quality"] = args.sleep_quality
    if args.water is not None:
        fields["water_ml"] = args.water
    if args.meals is not None:
        fields["meals_count"] = args.meals
    if args.snacking is not None:
        fields["snacking_episodes"] = args.snacking
    if args.exercise is not None:
        fields["exercise_minutes"] = args.exercise
    if args.mood is not None:
        fields["mood"] = args.mood
    if args.energy is not None:
        fields["energy"] = args.energy
    if args.stress is not None:
        fields["stress"] = args.stress
    if args.intrusive is not None:
        fields["intrusive_thoughts_count"] = args.intrusive

    if not fields:
        print("❌ Podaj przynajmniej jeden parametr (--pills, --sleep, --mood, itp.)")
        conn.close()
        return

    # UPSERT
    columns = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    updates = ", ".join(f"{k} = excluded.{k}" for k in fields)

    conn.execute(
        f"""INSERT INTO health_log (date, {columns})
            VALUES (?, {placeholders})
            ON CONFLICT(date) DO UPDATE SET {updates}""",
        [today] + list(fields.values()),
    )
    conn.commit()
    conn.close()

    print(f"✅ Zdrowie zapisane ({today}):")
    for k, v in fields.items():
        print(f"   {k}: {v}")


def cmd_focus_start(args):
    """Start a focus session."""
    tracker = TimeTracker()
    session_id = tracker.start_focus(
        duration=args.duration,
        task=args.task,
    )
    tracker.close()
    print(f"🎯 Focus session #{session_id} started ({args.duration} min)")
    if args.task:
        print(f"   Zadanie: {args.task}")


def cmd_focus_stop(args):
    """Stop the active focus session."""
    tracker = TimeTracker()
    # Find active focus session
    from .schema import get_db
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM focus_sessions WHERE end_time IS NULL ORDER BY start_time DESC LIMIT 1"
    ).fetchone()
    conn.close()

    if not row:
        print("❌ Brak aktywnej sesji focus")
        tracker.close()
        return

    result = tracker.stop_focus(
        row["id"],
        interruptions=args.interruptions or 0,
        focus_level=args.focus,
        notes=args.notes,
    )
    tracker.close()

    print(f"✅ Focus session #{result['id']} zakończona")
    print(f"   Planowane: {result['planned']} min | Rzeczywiste: {result['actual']} min")
    print(f"   Przerwania: {result['interruptions']}")
    if result.get("focus"):
        print(f"   Focus: {result['focus']}/10")


def cmd_init(args):
    """Initialize database and optionally import sample data."""
    conn = init_db()
    print("✅ Baza danych zainicjalizowana")

    if args.sample:
        crm = PeopleCRM()
        count = crm.import_sample_50()
        crm.close()
        print(f"✅ Zaimportowano {count} przykładowych osób")

    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Life Management System — zarządzanie czasem, ludźmi i zdrowiem",
    )
    subparsers = parser.add_subparsers(dest="command", help="Komendy")

    # ─── init ───
    p_init = subparsers.add_parser("init", help="Inicjalizuj bazę danych")
    p_init.add_argument("--sample", action="store_true", help="Importuj 50 przykładowych osób")

    # ─── track ───
    p_track = subparsers.add_parser("track", help="Śledzenie czasu")
    track_subs = p_track.add_subparsers(dest="subcommand")

    p_start = track_subs.add_parser("start", help="Rozpocznij blok czasu")
    p_start.add_argument("category", choices=TIME_CATEGORIES, help="Kategoria")
    p_start.add_argument("--planned", action="store_true", help="Zaplanowany")
    p_start.add_argument("--energy", type=int, choices=range(1, 11), help="Poziom energii 1-10")
    p_start.add_argument("--notes", help="Notatki")

    p_stop = track_subs.add_parser("stop", help="Zatrzymaj aktywny blok")
    p_stop.add_argument("--focus", type=int, choices=range(1, 11), help="Poziom skupienia 1-10")
    p_stop.add_argument("--satisfaction", type=int, choices=range(1, 11), help="Satysfakcja 1-10")
    p_stop.add_argument("--notes", help="Notatki")

    p_status = track_subs.add_parser("status", help="Pokaż status")

    # ─── people ───
    p_people = subparsers.add_parser("people", help="Zarządzanie ludźmi")
    people_subs = p_people.add_subparsers(dest="subcommand")

    p_list = people_subs.add_parser("list", help="Lista osób")
    p_list.add_argument("--category", choices=PEOPLE_CATEGORIES, help="Filtruj po kategorii")
    p_list.add_argument("--sort", choices=["priority", "name", "last_contact", "category", "balance"], default="priority")
    p_list.add_argument("--json", action="store_true", help="JSON output")

    p_neg = people_subs.add_parser("neglected", help="Zaniedbane osoby")
    p_neg.add_argument("--days", type=int, help="Próg dni (domyślnie: per-person)")

    p_bday = people_subs.add_parser("birthdays", help="Nadchodzące urodziny")
    p_bday.add_argument("--days", type=int, default=30, help="Ile dni do przodu")

    # ─── report ───
    p_report = subparsers.add_parser("report", help="Raporty")
    report_subs = p_report.add_subparsers(dest="subcommand")

    p_daily = report_subs.add_parser("daily", help="Raport dzienny")
    p_daily.add_argument("--json", action="store_true", help="JSON output")

    p_weekly = report_subs.add_parser("weekly", help="Raport tygodniowy")
    p_weekly.add_argument("--json", action="store_true", help="JSON output")

    p_balance = report_subs.add_parser("balance", help="Bilans czasu z ludźmi")
    p_balance.add_argument("--json", action="store_true", help="JSON output")

    # ─── health ───
    p_health = subparsers.add_parser("health", help="Logowanie zdrowia")
    p_health.add_argument("--pills", type=lambda x: x.lower() in ("true", "1", "yes", "tak"), help="Pigułki wzięte? (true/false)")
    p_health.add_argument("--sleep", type=float, help="Godziny snu")
    p_health.add_argument("--sleep-quality", type=int, choices=range(1, 11), help="Jakość snu 1-10")
    p_health.add_argument("--water", type=int, help="Woda (ml)")
    p_health.add_argument("--meals", type=int, help="Liczba posiłków")
    p_health.add_argument("--snacking", type=int, help="Epizody podjadania")
    p_health.add_argument("--exercise", type=int, help="Minuty ćwiczeń")
    p_health.add_argument("--mood", type=int, choices=range(1, 11), help="Nastrój 1-10")
    p_health.add_argument("--energy", type=int, choices=range(1, 11), help="Energia 1-10")
    p_health.add_argument("--stress", type=int, choices=range(1, 11), help="Stres 1-10")
    p_health.add_argument("--intrusive", type=int, help="Liczba natarczywych myśli")

    # ─── focus ───
    p_focus = subparsers.add_parser("focus", help="Sesje skupienia")
    focus_subs = p_focus.add_subparsers(dest="subcommand")

    p_fstart = focus_subs.add_parser("start", help="Rozpocznij sesję focus")
    p_fstart.add_argument("--duration", type=int, default=25, help="Czas trwania (min)")
    p_fstart.add_argument("--task", help="Zadanie")

    p_fstop = focus_subs.add_parser("stop", help="Zakończ sesję focus")
    p_fstop.add_argument("--interruptions", type=int, help="Liczba przerwań")
    p_fstop.add_argument("--focus", type=int, choices=range(1, 11), help="Poziom skupienia 1-10")
    p_fstop.add_argument("--notes", help="Notatki")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to handler
    if args.command == "init":
        cmd_init(args)
    elif args.command == "track":
        if args.subcommand == "start":
            cmd_track_start(args)
        elif args.subcommand == "stop":
            cmd_track_stop(args)
        elif args.subcommand == "status":
            cmd_track_status(args)
        else:
            p_track.print_help()
    elif args.command == "people":
        if args.subcommand == "list":
            cmd_people_list(args)
        elif args.subcommand == "neglected":
            cmd_people_neglected(args)
        elif args.subcommand == "birthdays":
            cmd_people_birthdays(args)
        else:
            p_people.print_help()
    elif args.command == "report":
        if args.subcommand == "daily":
            cmd_report_daily(args)
        elif args.subcommand == "weekly":
            cmd_report_weekly(args)
        elif args.subcommand == "balance":
            cmd_report_balance(args)
        else:
            p_report.print_help()
    elif args.command == "health":
        cmd_health_log(args)
    elif args.command == "focus":
        if args.subcommand == "start":
            cmd_focus_start(args)
        elif args.subcommand == "stop":
            cmd_focus_stop(args)
        else:
            p_focus.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
