#!/usr/bin/env python3
"""
Life Management System — CLI v2 (SQLAlchemy)
==============================================
Szybki interfejs do zarządzania życiem z terminala.
Używa SQLAlchemy models z core/models.py i services z core/services.py.

Usage:
    life-cli time start WORK "coding" "Working on API"
    life-cli time summary [--week]
    life-cli people list
    life-cli people overdue
    life-cli people next
    life-cli people add "Imię" close_friend 8
    life-cli people interact <id> call 30 4
    life-cli meds list
    life-cli meds missed
    life-cli meds take <id>
    life-cli meds skip <id>
    life-cli exercise log "Bieganie" 30 high 350
    life-cli exercise week
    life-cli weight log 80.5
    life-cli weight trend
    life-cli sleep log 23:00 07:00 4
    life-cli sleep avg
    life-cli meal log breakfast "Owsianka" 450 15 60 12 4
    life-cli meal calories
    life-cli meal macros
    life-cli recipe add "Nazwa" "składniki" "instrukcje"
    life-cli recipe favs
    life-cli thought log "Martwię się o X" 7 work
    life-cli thought unresolved
    life-cli thought resolve <id> "Jak sobie poradziłem"
    life-cli urge log stres 6 yes "Woda"
    life-cli urge stats
    life-cli focus start "Deep work" 25
    life-cli focus end <id> 2 4
    life-cli focus stats
    life-cli event add "Urodziny" 2026-08-15 birthday
    life-cli event upcoming
    life-cli event birthdays
    life-cli hobby add "Gitara" muzyka 3.0
    life-cli hobby log <id> 60 4
    life-cli hobby balance
    life-cli briefing

Author: Hermes Agent (Coder profile)
"""

import sys
import os
from datetime import date, time, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.models import (
    create_engine_sqlite, init_db, get_session,
    TimeCategory, RelationshipType, InteractionType,
    MealType, ExerciseIntensity,
    Medication, Recipe, Hobby,
)
from core.services import (
    TimeTracker, PeopleManager, HealthManager,
    NutritionManager, MentalManager, EventManager, HobbyManager,
    DailyBriefing,
)

DB_PATH = os.environ.get("LIFE_MANAGEMENT_DB", str(Path(__file__).parent / "core" / "life_management.db"))


def get_engine_and_session():
    engine = create_engine_sqlite(DB_PATH)
    init_db(engine)
    return engine, get_session(engine)


def cmd_time(args, session):
    tracker = TimeTracker(session)
    if not args:
        print("Usage: life-cli time <start|summary> [opcje]")
        return
    sub = args[0]
    if sub == "start":
        if len(args) < 2:
            print("Usage: life-cli time start <kategoria> [subkategoria] [opis]")
            return
        cat = TimeCategory(args[1])
        subcat = args[2] if len(args) > 2 else None
        desc = args[3] if len(args) > 3 else None
        block = tracker.start_block(cat, subcat, desc)
        print(f"⏱️  Blok #{block.id} rozpoczęty: {cat.value} ({block.start_time:%H:%M})")
    elif sub == "summary":
        week = "--week" in args
        summary = tracker.get_weekly_summary() if week else tracker.get_daily_summary()
        label = "tygodnia" if week else f"dnia ({date.today()})"
        print(f"📊 Podsumowanie {label}:")
        total = sum(summary.values())
        for cat, hours in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            pct = (hours / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5)
            print(f"  {cat:20s} {hours:5.1f}h ({pct:4.0f}%) {bar}")
        print(f"  {'─' * 20} {'─' * 5} {'─' * 4}")
        print(f"  {'RAZEM':20s} {total:5.1f}h")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_people(args, session):
    mgr = PeopleManager(session)
    if not args:
        print("Usage: life-cli people <list|overdue|next|add|interact|balance|stats> [opcje]")
        return
    sub = args[0]
    if sub == "list":
        people = mgr.get_all_active()
        print(f"👥 Aktywne osoby ({len(people)}):")
        for p in people:
            overdue = " ⚠️ ZALEGŁY!" if p.is_overdue else ""
            days = f" ({p.days_since_last_contact}d temu)" if p.days_since_last_contact else ""
            print(f"  [{p.id:2d}] {p.name:30s} {p.relationship_type.value:20s} prio={p.priority}{days}{overdue}")
    elif sub == "overdue":
        overdue = mgr.get_overdue()
        print(f"⚠️  Zaległe kontakty ({len(overdue)}):")
        for p in overdue:
            days = (date.today() - p.next_contact_due).days if p.next_contact_due else "?"
            print(f"  [{p.id:2d}] {p.name:30s} — {days} dni po terminie!")
    elif sub == "next":
        for p in mgr.get_next_to_contact(5):
            due = p.next_contact_due.isoformat() if p.next_contact_due else "brak"
            print(f"  [{p.id:2d}] {p.name:30s} {p.relationship_type.value:20s} due: {due}")
    elif sub == "add":
        if len(args) < 3:
            print("Usage: life-cli people add <imię> <typ_relacji> [priorytet]")
            return
        person = mgr.add_person(args[1], RelationshipType(args[2]), int(args[3]) if len(args) > 3 else 5)
        print(f"✅ Dodano: {person.name}" if person else "❌ Limit 50 osób!")
    elif sub == "interact":
        if len(args) < 3:
            print("Usage: life-cli people interact <id> <typ> [minuty] [jakość]")
            return
        r = mgr.log_interaction(int(args[1]), InteractionType(args[2]),
                                int(args[3]) if len(args) > 3 else None,
                                int(args[4]) if len(args) > 4 else None)
        print(f"✅ Interakcja zalogowana" if r else "❌ Osoba nie istnieje")
    elif sub == "balance":
        for rel_type, pct in sorted(mgr.get_balance_score().items(), key=lambda x: x[1], reverse=True):
            print(f"  {rel_type:20s} {pct:5.1f}% {'█' * int(pct / 5)}")
    elif sub == "stats":
        if len(args) < 2:
            print("Usage: life-cli people stats <id>")
            return
        s = mgr.get_person_stats(int(args[1]))
        if s:
            p = s["person"]
            print(f"📊 {p.name} | {p.relationship_type.value} | prio={p.priority}")
            print(f"  Interakcje (30d): {s['interactions_30d']} | Czas: {s['total_minutes_30d']}min")
            print(f"  Jakość: {s['avg_quality'] or '?'}/5 | Ostatni kontakt: {s['days_since_last_contact']}d")
            print(f"  Zaległy: {'TAK ⚠️' if s['is_overdue'] else 'Nie'}")
        else:
            print("❌ Nie istnieje")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_meds(args, session):
    mgr = HealthManager(session)
    if not args:
        print("Usage: life-cli meds <list|missed|take|skip|add|low> [opcje]")
        return
    sub = args[0]
    if sub == "list":
        for m in session.query(Medication).filter(Medication.active == True).all():
            stock = f" (pozostało: {m.stock_remaining})" if m.stock_remaining else ""
            print(f"  [{m.id}] {m.name:25s} {m.dosage or '':10s} {m.frequency_per_day}x/dzień{stock}")
    elif sub == "missed":
        missed = mgr.get_missed_medications()
        if missed:
            print("⚠️  Pominięte dziś leki:")
            for m in missed:
                print(f"  [{m.id}] {m.name} — {m.dosage} ({m.frequency_per_day}x/dzień)")
        else:
            print("✅ Wszystkie leki dziś wzięte!")
    elif sub == "take":
        if len(args) < 2: print("Usage: life-cli meds take <id>"); return
        r = mgr.log_medication(int(args[1]), skipped=False)
        print(f"✅ Przyjęto lek #{args[1]}" if r else f"❌ Lek #{args[1]} nie istnieje")
    elif sub == "skip":
        if len(args) < 2: print("Usage: life-cli meds skip <id>"); return
        r = mgr.log_medication(int(args[1]), skipped=True)
        print(f"⏭️  Pominięto lek #{args[1]}" if r else f"❌ Lek #{args[1]} nie istnieje")
    elif sub == "add":
        if len(args) < 2: print("Usage: life-cli meds add <nazwa> [dawka] [częst.] [godziny] [stan]"); return
        med = mgr.add_medication(args[1], args[2] if len(args) > 2 else None,
                                 int(args[3]) if len(args) > 3 else 1,
                                 args[4] if len(args) > 4 else None,
                                 int(args[5]) if len(args) > 5 else None)
        print(f"✅ Dodano lek: {med.name}")
    elif sub == "low":
        low = mgr.get_low_stock()
        if low:
            print("📉 Niski stan leków:")
            for m in low: print(f"  [{m.id}] {m.name} — zostało {m.stock_remaining}")
        else:
            print("✅ Wszystkie leki mają zapas")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_exercise(args, session):
    mgr = HealthManager(session)
    if not args: print("Usage: life-cli exercise <log|week> [opcje]"); return
    sub = args[0]
    if sub == "log":
        if len(args) < 4: print("Usage: life-cli exercise log <typ> <minuty> <intensywność> [kalorie]"); return
        ex = mgr.log_exercise(args[1], int(args[2]), ExerciseIntensity(args[3]),
                              int(args[4]) if len(args) > 4 else None)
        print(f"🏃 Zalogowano: {ex.exercise_type} {ex.duration_minutes}min [{ex.intensity.value}]")
    elif sub == "week":
        s = mgr.get_weekly_exercise()
        print(f"📊 Treningi w tym tygodniu: {s['sessions']} sesji, {s['total_minutes']}min, {s['total_calories']}kcal")
        for t, mins in s.get("by_type", {}).items():
            print(f"    {t}: {mins}min")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_weight(args, session):
    mgr = HealthManager(session)
    if not args: print("Usage: life-cli weight <log|trend> [opcje]"); return
    sub = args[0]
    if sub == "log":
        if len(args) < 2: print("Usage: life-cli weight log <kg> [notatka]"); return
        wl = mgr.log_weight(float(args[1]), args[2] if len(args) > 2 else None)
        print(f"⚖️  Waga: {wl.weight_kg}kg ({wl.date})")
    elif sub == "trend":
        days = int(args[1]) if len(args) > 1 else 30
        trend = mgr.get_weight_trend(days)
        if trend:
            for e in trend: print(f"  {e['date']}: {e['weight_kg']}kg")
            if len(trend) >= 2:
                delta = trend[-1]["weight_kg"] - trend[0]["weight_kg"]
                print(f"  Zmiana: {'↓' if delta < 0 else '↑' if delta > 0 else '→'} {abs(delta):.1f}kg")
        else:
            print("Brak danych")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_sleep(args, session):
    mgr = HealthManager(session)
    if not args: print("Usage: life-cli sleep <log|avg> [opcje]"); return
    sub = args[0]
    if sub == "log":
        if len(args) < 3: print("Usage: life-cli sleep log <godzina_snu> <godzina_pobudki> [jakość]"); return
        sl = mgr.log_sleep(time.fromisoformat(args[1]), time.fromisoformat(args[2]),
                           int(args[3]) if len(args) > 3 else None)
        print(f"😴 Sen: {sl.duration_hours}h (łóżko: {args[1]}, pobudka: {args[2]})")
    elif sub == "avg":
        avg = mgr.get_sleep_weekly_avg()
        print(f"😴 Średni sen (7 dni): {avg}h" if avg else "Brak danych")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_meal(args, session):
    mgr = NutritionManager(session)
    if not args: print("Usage: life-cli meal <log|calories|macros|score> [opcje]"); return
    sub = args[0]
    if sub == "log":
        if len(args) < 3: print("Usage: life-cli meal log <typ> <opis> [kal] [b] [w] [t] [score]"); return
        meal = mgr.log_meal(MealType(args[1]), args[2],
                            int(args[3]) if len(args) > 3 else None,
                            float(args[4]) if len(args) > 4 else None,
                            float(args[5]) if len(args) > 5 else None,
                            float(args[6]) if len(args) > 6 else None,
                            int(args[7]) if len(args) > 7 else None)
        print(f"🍽️  {meal.meal_type.value} — {meal.description[:50]} ({meal.calories or '?'}kcal)")
    elif sub == "calories":
        print(f"🔥 Kalorie dziś: {mgr.get_daily_calories()} kcal")
    elif sub == "macros":
        m = mgr.get_daily_macros()
        print(f"📊 B: {m['protein_g']:.0f}g  W: {m['carbs_g']:.0f}g  T: {m['fat_g']:.0f}g  KCAL: {m['calories']}")
    elif sub == "score":
        avg = mgr.get_healthy_score_weekly_avg()
        print(f"🥗 Średni health score (7 dni): {avg}/5" if avg else "Brak danych")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_recipe(args, session):
    mgr = NutritionManager(session)
    if not args: print("Usage: life-cli recipe <add|favs|list> [opcje]"); return
    sub = args[0]
    if sub == "add":
        if len(args) < 4: print("Usage: life-cli recipe add <nazwa> <składniki> <instrukcje> [kal] [b] [czas] [tagi]"); return
        r = mgr.add_recipe(args[1], args[2], args[3],
                           int(args[4]) if len(args) > 4 else None,
                           float(args[5]) if len(args) > 5 else None,
                           int(args[6]) if len(args) > 6 else None,
                           args[7] if len(args) > 7 else None)
        print(f"📖 Dodano przepis: {r.name}")
    elif sub == "favs":
        favs = mgr.get_favorite_recipes()
        if favs:
            for r in favs: print(f"  ⭐ [{r.id}] {r.name} ({r.calories_per_serving or '?'}kcal)")
        else:
            print("Brak ulubionych przepisów")
    elif sub == "list":
        recipes = session.query(Recipe).all()
        if recipes:
            for r in recipes:
                fav = "⭐" if r.favorite else "  "
                print(f"  {fav} [{r.id}] {r.name} ({r.calories_per_serving or '?'}kcal)")
        else:
            print("Brak przepisów")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_thought(args, session):
    mgr = MentalManager(session)
    if not args: print("Usage: life-cli thought <log|unresolved|resolve|trend> [opcje]"); return
    sub = args[0]
    if sub == "log":
        if len(args) < 3: print("Usage: life-cli thought log <myśl> <intensywność> [kategoria]"); return
        t = mgr.log_thought(args[1], int(args[2]), args[3] if len(args) > 3 else None)
        print(f"🧠 Zarejestrowano myśl #{t.id} (intensywność: {args[2]}/10)")
    elif sub == "unresolved":
        thoughts = mgr.get_unresolved_thoughts()
        if thoughts:
            for t in thoughts: print(f"  [{t.id}] intensywność={t.intensity}/10: {t.thought[:80]}")
        else:
            print("✅ Brak nieprzepracowanych myśli!")
    elif sub == "resolve":
        if len(args) < 3: print("Usage: life-cli thought resolve <id> <odpowiedź>"); return
        t = mgr.resolve_thought(int(args[1]), args[2])
        print(f"✅ Myśl #{args[1]} przepracowana" if t else f"❌ Myśl #{args[1]} nie istnieje")
    elif sub == "trend":
        days = int(args[1]) if len(args) > 1 else 7
        for e in mgr.get_thought_trend(days):
            if e["count"] > 0: print(f"  {e['date']}: {e['count']} myśli, śr. intensywność {e['avg_intensity']}")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_urge(args, session):
    mgr = MentalManager(session)
    if not args: print("Usage: life-cli urge <log|stats> [opcje]"); return
    sub = args[0]
    if sub == "log":
        if len(args) < 4: print("Usage: life-cli urge log <trigger> <intensywność> <oparł_się?> [alternatywa]"); return
        resisted = args[3].lower() in ("yes", "tak", "true", "1")
        mgr.log_urge(args[1], int(args[2]), resisted, args[4] if len(args) > 4 else None)
        print(f"🍪 Odruch: {'OPARŁ SIĘ 💪' if resisted else 'ULEGŁ 😔'} — trigger: {args[1]}")
    elif sub == "stats":
        days = int(args[1]) if len(args) > 1 else 7
        s = mgr.get_urge_stats(days)
        print(f"🍪 Podjadanie ({days} dni): {s['total']} odruchów, {s['resisted']} opór ({s['success_rate']:.0f}%), {s['gave_in']} ulegnięć")
        for t in s.get("top_triggers", []): print(f"    {t['trigger']}: {t['count']}x")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_focus(args, session):
    mgr = MentalManager(session)
    if not args: print("Usage: life-cli focus <start|end|stats> [opcje]"); return
    sub = args[0]
    if sub == "start":
        if len(args) < 2: print("Usage: life-cli focus start <zadanie> [minuty]"); return
        fs = mgr.start_focus(args[1], int(args[2]) if len(args) > 2 else 25)
        print(f"🎯 Focus #{fs.id} rozpoczęty: {args[1][:50]} ({fs.planned_duration_minutes}min)")
    elif sub == "end":
        if len(args) < 2: print("Usage: life-cli focus end <id> [przerywania] [produktywność]"); return
        fs = mgr.end_focus(int(args[1]), int(args[2]) if len(args) > 2 else 0,
                           int(args[3]) if len(args) > 3 else None)
        print(f"✅ Focus zakończony" if fs else f"❌ Focus #{args[1]} nie istnieje")
    elif sub == "stats":
        days = int(args[1]) if len(args) > 1 else 7
        s = mgr.get_focus_stats(days)
        print(f"🎯 Focus ({days} dni): {s['completed']}/{s['total_sessions']} sesji, {s['total_focus_minutes']}min, prod={s['avg_productivity'] or '?'}/5")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_event(args, session):
    mgr = EventManager(session)
    if not args: print("Usage: life-cli event <add|upcoming|birthdays> [opcje]"); return
    sub = args[0]
    if sub == "add":
        if len(args) < 4: print("Usage: life-cli event add <tytuł> <data> <typ> [przypomnienie_dni]"); return
        e = mgr.add_event(args[1], date.fromisoformat(args[2]), args[3],
                          reminder_days_before=int(args[4]) if len(args) > 4 else 7)
        print(f"📅 Dodano: {e.title} ({e.event_date}, za {e.days_until} dni)")
    elif sub == "upcoming":
        days = int(args[1]) if len(args) > 1 else 30
        events = mgr.get_upcoming(days)
        if events:
            for e in events: print(f"  [{e.id}] {e.event_date} — {e.title} ({e.event_type}, za {e.days_until} dni)")
        else:
            print(f"Brak wydarzeń w ciągu {days} dni")
    elif sub == "birthdays":
        birthdays = mgr.get_birthdays_this_month()
        if birthdays:
            for e in birthdays: print(f"  🎂 {e.event_date.day:2d}.{e.event_date.month:02d} — {e.title}")
        else:
            print("Brak urodzin w tym miesiącu")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_hobby(args, session):
    mgr = HobbyManager(session)
    if not args: print("Usage: life-cli hobby <add|log|balance|list> [opcje]"); return
    sub = args[0]
    if sub == "add":
        if len(args) < 2: print("Usage: life-cli hobby add <nazwa> [kategoria] [godziny/tydzień]"); return
        h = mgr.add_hobby(args[1], args[2] if len(args) > 2 else None,
                          float(args[3]) if len(args) > 3 else None)
        print(f"🎨 Dodano hobby: {h.name}")
    elif sub == "log":
        if len(args) < 3: print("Usage: life-cli hobby log <id> <minuty> [przyjemność]"); return
        hs = mgr.log_session(int(args[1]), int(args[2]), int(args[3]) if len(args) > 3 else None)
        print(f"✅ Sesja hobby" if hs else f"❌ Hobby #{args[1]} nie istnieje")
    elif sub == "balance":
        balance = mgr.get_hobby_balance()
        if balance:
            for h in balance:
                status = "✅" if h["on_track"] else "⚠️"
                print(f"  {status} {h['name']:20s} {h['actual_hours']:.1f}/{h['target_hours']:.1f}h (deficyt: {h['deficit']:.1f}h)")
        else:
            print("Brak hobby")
    elif sub == "list":
        hobbies = session.query(Hobby).filter(Hobby.active == True).all()
        if hobbies:
            for h in hobbies: print(f"  [{h.id}] {h.name:20s} {h.category or '':15s} target: {h.target_hours_per_week or '?'}h/tydz")
        else:
            print("Brak hobby")
    else:
        print(f"Nieznana komenda: {sub}")


def cmd_briefing(args, session):
    result = DailyBriefing(session).generate()
    print(f"📋 DAILY BRIEFING — {result['date']}")
    print("=" * 50)

    meds = result["medications"]
    if meds["missed"]:
        print("\n💊 LEKI DO WZIĘCIA:")
        for m in meds["missed"]: print(f"  ⚠️  {m['name']} — {m['dosage']} ({m['frequency']}x/dzień)")
    if meds["low_stock"]:
        print("\n📉 NISKI STAN:")
        for m in meds["low_stock"]: print(f"  ⚠️  {m['name']} — zostało {m['remaining']}")

    people = result["people"]
    if people["overdue"]:
        print("\n👥 ZALEGŁE KONTAKTY:")
        for p in people["overdue"]: print(f"  ⚠️  {p['name']} — {p['days_overdue']} dni po terminie!")
    if people["next_to_contact"]:
        print("\n📞 NASTĘPNI DO KONTAKTU:")
        for p in people["next_to_contact"]: print(f"  • {p['name']} ({p['type']}) — due: {p['due']}")

    events = result["events"]
    if events["today"]:
        print("\n📅 DZIŚ:")
        for e in events["today"]: print(f"  • {e['title']} ({e['type']})")
    if events["upcoming_7d"]:
        print("\n📅 W CIĄGU 7 DNI:")
        for e in events["upcoming_7d"]: print(f"  • {e['date']} — {e['title']} (za {e['days_until']} dni)")

    mental = result["mental"]
    if mental["unresolved_thoughts"] > 0: print(f"\n🧠 Nieprzepracowane myśli: {mental['unresolved_thoughts']}")

    focus = result["focus"]
    if focus["total_sessions"] > 0: print(f"\n🎯 Focus: {focus['completed']}/{focus['total_sessions']} sesji, {focus['total_focus_minutes']}min")

    yesterday = result["yesterday_summary"]
    if yesterday:
        print(f"\n📊 WCZORAJ:")
        total = sum(yesterday.values())
        for cat, hours in sorted(yesterday.items(), key=lambda x: x[1], reverse=True):
            if hours > 0: print(f"  {cat}: {hours:.1f}h")
    print("\n" + "=" * 50)


COMMANDS = {
    "time": cmd_time, "people": cmd_people, "meds": cmd_meds,
    "exercise": cmd_exercise, "weight": cmd_weight, "sleep": cmd_sleep,
    "meal": cmd_meal, "recipe": cmd_recipe, "thought": cmd_thought,
    "urge": cmd_urge, "focus": cmd_focus, "event": cmd_event,
    "hobby": cmd_hobby, "briefing": cmd_briefing,
}


def main():
    if len(sys.argv) < 2:
        print("Life Management CLI v2 (SQLAlchemy)")
        print("Dostępne komendy:", ", ".join(sorted(COMMANDS.keys())))
        print("Użyj: life_cli_v2.py <komenda> [opcje]")
        return

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Nieznana komenda: {cmd}")
        print(f"Dostępne: {', '.join(sorted(COMMANDS.keys()))}")
        return

    engine, session = get_engine_and_session()
    try:
        COMMANDS[cmd](sys.argv[2:], session)
    except Exception as e:
        print(f"❌ Błąd: {e}")
        import traceback; traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
