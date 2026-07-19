#!/usr/bin/env python3
"""
Hermes Integration Module for Life Management System
=====================================================
- Cron job setup (daily brief, pill reminders, weekly report, check-ins)
- Notification bridge (birthday alerts, overdue contacts)
- Simple web dashboard (Flask)
- Seed data generator (50 people template)
"""

from __future__ import annotations

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from life_cli import (
    LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator,
)

LIFE_DIR = Path(__file__).parent
LIFE_CLI = LIFE_DIR / "life_cli.py"


# ── Cron Job Manager ─────────────────────────────────────────────────────────

class CronManager:
    """Zarządza cron jobs dla life management przez Hermes CLI."""

    JOBS = {
        "life-daily-brief": {
            "schedule": "0 8 * * *",
            "prompt": (
                "Uruchom python3 ~/workspace/hermes-enhancements/life-management/life_cli.py brief. "
                "Przedstaw wynik użytkownikowi w czytelnej formie. "
                "Jeśli są overdue kontakty — przypomnij konkretnie o każdej osobie. "
                "Jeśli są nadchodzące urodziny w ciągu 7 dni — wypisz je."
            ),
            "description": "Codzienny brief o 8:00",
        },
        "life-pill-morning": {
            "schedule": "0 9 * * *",
            "prompt": (
                "Przypomnij użytkownikowi: '💊 Dzień dobry! Czas na poranne pigułki. Wziąłeś?' "
                "Jeśli użytkownik potwierdzi, uruchom: "
                "python3 ~/workspace/hermes-enhancements/life-management/life_cli.py pill taken"
            ),
            "description": "Przypomnienie o porannych pigułkach (9:00)",
        },
        "life-pill-evening": {
            "schedule": "0 21 * * *",
            "prompt": (
                "Przypomnij użytkownikowi: '💊 Wieczorna pora! Czas na pigułki. Wziąłeś?' "
                "Jeśli użytkownik potwierdzi, uruchom: "
                "python3 ~/workspace/hermes-enhancements/life-management/life_cli.py pill taken"
            ),
            "description": "Przypomnienie o wieczornych pigułkach (21:00)",
        },
        "life-midday-checkin": {
            "schedule": "0 12 * * *",
            "prompt": (
                "Zapytaj użytkownika: '⏱️ Południe! Co robisz teraz? Chcesz zalogować blok czasu? "
                "Dostępne kategorie: praca, rodzina, znajomi, zdrowie, jedzenie, hobby, odpoczynek, nauka, administracja, transport, higiena, inne. "
                "Jeśli użytkownik poda kategorię, uruchom: "
                "python3 ~/workspace/hermes-enhancements/life-management/life_cli.py start <kategoria>'"
            ),
            "description": "Południowy check-in (12:00)",
        },
        "life-evening-checkin": {
            "schedule": "0 22 * * *",
            "prompt": (
                "Zapytaj użytkownika: '🌙 Wieczorne podsumowanie! Jak minął dzień? "
                "1. Energia (1-10)? 2. Focus (1-10)? 3. Czy były natarczywe myśli? (intensywność 1-10) "
                "4. Czy było podjadanie? (intensywność 1-10) "
                "Zaloguj odpowiedzi przez python3 life_cli.py.'"
            ),
            "description": "Wieczorny check-in (22:00)",
        },
        "life-weekly-report": {
            "schedule": "0 20 * * 0",  # Niedziela 20:00
            "prompt": (
                "Uruchom python3 ~/workspace/hermes-enhancements/life-management/life_cli.py week. "
                "Przedstaw użytkownikowi pełny raport tygodniowy: "
                "- Gdzie uciekał czas (kategorie + godziny) "
                "- Z kim spędzał czas (top 5 osób) "
                "- Kogo zaniedbuje (overdue kontakty) "
                "- Nawykowe trendy (pigułki streak, myśli, podjadanie) "
                "- Sugestie na następny tydzień"
            ),
            "description": "Raport tygodniowy (niedziela 20:00)",
        },
        "life-birthday-check": {
            "schedule": "0 7 * * *",
            "prompt": (
                "Uruchom python3 ~/workspace/hermes-enhancements/life-management/life_cli.py birthdays 7. "
                "Jeśli są urodziny dziś lub w ciągu 7 dni — przypomnij użytkownikowi. "
                "Dla dzisiejszych urodzin: zaproponuj wysłanie życzeń."
            ),
            "description": "Sprawdzenie urodzin codziennie o 7:00",
        },
    }

    @classmethod
    def setup_all(cls) -> list[str]:
        """Skonfiguruj wszystkie cron jobs. Zwraca listę stworzonych jobów."""
        created = []
        for job_id, config in cls.JOBS.items():
            try:
                result = subprocess.run(
                    [
                        "hermes", "cron", "create",
                        "--schedule", config["schedule"],
                        "--prompt", config["prompt"],
                        "--name", job_id,
                        "--deliver", "origin",
                    ],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode == 0:
                    created.append(job_id)
                    print(f"  ✅ {job_id}: {config['description']}")
                else:
                    print(f"  ⚠️ {job_id}: {result.stderr.strip()}")
            except Exception as e:
                print(f"  ❌ {job_id}: {e}")
        return created

    @classmethod
    def list_all(cls) -> None:
        """Wypisz wszystkie cron jobs."""
        subprocess.run(["hermes", "cron", "list"])

    @classmethod
    def remove_all(cls) -> None:
        """Usuń wszystkie life-management cron jobs."""
        for job_id in cls.JOBS:
            subprocess.run(
                ["hermes", "cron", "remove", job_id],
                capture_output=True,
            )


# ── Notification Bridge ──────────────────────────────────────────────────────

class NotificationBridge:
    """Generuje powiadomienia na podstawie stanu systemu."""

    def __init__(self, db: LifeDB):
        self.db = db
        self.people = PeopleManager(db)
        self.events = EventManager(db)
        self.habits = HabitTracker(db)

    def get_all_notifications(self) -> list[dict]:
        """Zbierz wszystkie powiadomienia do wysłania."""
        notifications = []

        # 1. Overdue kontakty
        needing = self.people.get_who_needs_attention(top_n=5)
        for p in needing:
            if p["overdue"]:
                notifications.append({
                    "type": "overdue_contact",
                    "priority": "high",
                    "message": f"🔴 {p['name']} ({p['category']}) — brak kontaktu od {p['days_since_contact']} dni!",
                    "action": f"Zadzwoń lub napisz do {p['name']}",
                })

        # 2. Nadchodzące urodziny (dziś lub jutro)
        birthdays = self.people.get_upcoming_birthdays(days_ahead=2)
        for b in birthdays:
            if b["days_until"] == 0:
                notifications.append({
                    "type": "birthday_today",
                    "priority": "critical",
                    "message": f"🎂 DZIŚ URODZINY: {b['name']} ({b['age']} lat)!",
                    "action": "Wyślij życzenia!",
                })
            elif b["days_until"] == 1:
                notifications.append({
                    "type": "birthday_tomorrow",
                    "priority": "high",
                    "message": f"🎂 JUTRO URODZINY: {b['name']} ({b['age']} lat)",
                    "action": "Kup prezent / przygotuj życzenia",
                })

        # 3. Nadchodzące wydarzenia (dziś lub jutro)
        upcoming = self.events.get_upcoming_events(days_ahead=2)
        for e in upcoming:
            event_date = date.fromisoformat(e["event_date"])
            days_until = (event_date - date.today()).days
            if days_until == 0:
                notifications.append({
                    "type": "event_today",
                    "priority": "high",
                    "message": f"📌 DZIŚ: {e['title']} ({e['event_type']})",
                    "action": "Przygotuj się!",
                })
            elif days_until == 1:
                notifications.append({
                    "type": "event_tomorrow",
                    "priority": "medium",
                    "message": f"📌 JUTRO: {e['title']} ({e['event_type']})",
                    "action": "Zaplanuj jutro",
                })

        # 4. Pigułki — czy wzięte dziś?
        today_habits = self.habits.get_today_habits()
        pills_today = today_habits.get("pills", [])
        if not pills_today:
            now = datetime.now()
            if now.hour >= 10:  # Po 10:00 — alarm
                notifications.append({
                    "type": "pills_missed",
                    "priority": "critical",
                    "message": "💊 UWAGA: Nie wziąłeś dziś pigułek!",
                    "action": "Weź pigułki natychmiast",
                })

        # 5. Streak info
        pill_streak = self.habits.get_streak("pills")
        if pill_streak >= 7:
            notifications.append({
                "type": "streak_milestone",
                "priority": "low",
                "message": f"🔥 Seria pigułek: {pill_streak} dni!",
                "action": "Tak trzymaj!",
            })

        return notifications

    def format_for_hermes(self) -> str:
        """Sformatuj powiadomienia jako tekst dla Hermesa."""
        notifs = self.get_all_notifications()
        if not notifs:
            return "✅ Wszystko w porządku, brak alertów."

        lines = ["🔔 ALERTY LIFE MANAGEMENT", "=" * 40, ""]

        # Sortuj po priorytecie
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        notifs.sort(key=lambda n: priority_order.get(n["priority"], 99))

        for n in notifs:
            lines.append(n["message"])
            lines.append(f"   → {n['action']}")
            lines.append("")

        return "\n".join(lines)


# ── Seed Data Generator ──────────────────────────────────────────────────────

class SeedGenerator:
    """Generuje przykładowe dane — 50 osób, bloki czasu, wydarzenia."""

    SAMPLE_PEOPLE = [
        # Rodzina bliższa (10)
        ("Mama", "rodzina_blizsza", 10, "1965-03-15", 3),
        ("Tata", "rodzina_blizsza", 9, "1963-08-22", 5),
        ("Siostra Ania", "rodzina_blizsza", 8, "1995-11-03", 7),
        ("Brat Tomek", "rodzina_blizsza", 7, "1993-06-18", 7),
        ("Babcia Zosia", "rodzina_blizsza", 9, "1940-12-01", 3),
        ("Dziadek Jan", "rodzina_blizsza", 8, "1938-04-10", 3),
        ("Ciocia Krysia", "rodzina_blizsza", 6, "1970-02-14", 14),
        ("Wujek Marek", "rodzina_blizsza", 6, "1968-09-30", 14),
        ("Kuzynka Ola", "rodzina_blizsza", 5, "2000-07-22", 30),
        ("Kuzyn Piotr", "rodzina_blizsza", 5, "1998-01-15", 30),

        # Rodzina dalsza (10)
        ("Ciocia Basia", "rodzina_dalsza", 4, "1970-01-05", 30),
        ("Wujek Staszek", "rodzina_dalsza", 4, "1965-05-20", 30),
        ("Kuzynka Magda", "rodzina_dalsza", 3, "2002-03-08", 60),
        ("Kuzyn Kuba", "rodzina_dalsza", 3, "1999-11-12", 60),
        ("Babcia Halina", "rodzina_dalsza", 5, "1942-08-30", 14),
        ("Dziadek Franek", "rodzina_dalsza", 5, "1940-06-25", 14),
        ("Ciocia Ela", "rodzina_dalsza", 3, "1972-04-18", 60),
        ("Wujek Rysiek", "rodzina_dalsza", 3, "1968-10-05", 60),
        ("Kuzynka Ewa", "rodzina_dalsza", 2, "2005-09-14", 90),
        ("Kuzyn Adam", "rodzina_dalsza", 2, "2003-12-28", 90),

        # Znajomi bliscy (10)
        ("Kumpel Marek", "znajomi_bliscy", 7, "1992-11-10", 7),
        ("Przyjaciółka Kasia", "znajomi_bliscy", 8, "1994-04-25", 5),
        ("Kumpel z pracy Tomek", "znajomi_bliscy", 6, "1990-08-15", 3),
        ("Przyjaciel Michał", "znajomi_bliscy", 7, "1991-02-28", 10),
        ("Kumpela Ania", "znajomi_bliscy", 6, "1993-07-07", 10),
        ("Sąsiad Paweł", "znajomi_bliscy", 5, "1988-12-20", 14),
        ("Znajoma z siłowni", "znajomi_bliscy", 5, "1995-06-12", 7),
        ("Kumpel z uczelni", "znajomi_bliscy", 5, "1992-09-03", 30),
        ("Przyjaciółka Ola", "znajomi_bliscy", 7, "1994-01-19", 7),
        ("Kumpel Rafał", "znajomi_bliscy", 6, "1990-05-30", 14),

        # Znajomi (10)
        ("Znajomy Janek", "znajomi", 4, "1993-03-22", 30),
        ("Znajoma Marta", "znajomi", 4, "1995-10-08", 30),
        ("Kolega z kursu", "znajomi", 3, "1991-07-14", 60),
        ("Koleżanka z eventów", "znajomi", 3, "1994-11-25", 60),
        ("Znajomy z klubu", "znajomi", 3, "1990-02-10", 60),
        ("Znajoma z podróży", "znajomi", 3, "1996-08-05", 90),
        ("Kolega z byłej pracy", "znajomi", 3, "1989-04-17", 90),
        ("Koleżanka ze studiów", "znajomi", 3, "1993-09-29", 90),
        ("Znajomy z konferencji", "znajomi", 2, "1992-06-11", 180),
        ("Znajoma z meetupu", "znajomi", 2, "1995-01-23", 180),

        # Współpracownicy (10)
        ("Szef Działu", "wspolpracownicy", 6, "1980-05-10", 1),
        ("PM Kasia", "wspolpracownicy", 5, "1988-11-20", 1),
        ("Dev Mateusz", "wspolpracownicy", 5, "1992-03-15", 1),
        ("Dev Ola", "wspolpracownicy", 5, "1994-07-08", 1),
        ("QA Tester", "wspolpracownicy", 4, "1990-12-01", 3),
        ("Designer UX", "wspolpracownicy", 4, "1993-09-18", 3),
        ("DevOps Krzysiek", "wspolpracownicy", 4, "1991-06-25", 3),
        ("HR Manager", "wspolpracownicy", 3, "1985-02-14", 7),
        ("Stażysta Janek", "wspolpracownicy", 3, "2001-10-30", 3),
        ("CEO", "wspolpracownicy", 5, "1975-08-05", 14),
    ]

    @classmethod
    def seed_people(cls, db: LifeDB) -> int:
        """Wypełnij bazę 50 przykładowymi osobami."""
        pm = PeopleManager(db)
        count = 0
        for name, category, priority, birthday, freq in cls.SAMPLE_PEOPLE:
            try:
                pm.add_person(
                    name=name,
                    category=category,
                    priority=priority,
                    birthday=birthday,
                    contact_frequency_days=freq,
                )
                count += 1
            except Exception as e:
                print(f"  ⚠️ Błąd dodawania {name}: {e}")
        return count

    @classmethod
    def seed_sample_data(cls, db: LifeDB) -> None:
        """Wypełnij bazę przykładowymi danymi (osoby + bloki czasu + eventy)."""
        pm = PeopleManager(db)
        tracker = TimeTracker(db)
        events = EventManager(db)
        habits = HabitTracker(db)

        # Dodaj osoby
        print(f"Dodawanie {len(cls.SAMPLE_PEOPLE)} osób...")
        for name, category, priority, birthday, freq in cls.SAMPLE_PEOPLE:
            pm.add_person(
                name=name, category=category, priority=priority,
                birthday=birthday, contact_frequency_days=freq,
            )

        # Pobierz ID dodanych osób
        all_people = pm.get_all_people()
        people_by_name = {p.name: p.id for p in all_people}

        # Dodaj przykładowe bloki czasu (ostatnie 7 dni)
        print("Dodawanie przykładowych bloków czasu...")
        today = date.today()
        for days_ago in range(7):
            d = today - timedelta(days=days_ago)
            day_str = d.isoformat()

            # Poranny blok pracy
            tracker.log_manual_block(
                f"{day_str}T08:00:00", f"{day_str}T09:00:00",
                "praca", description="Daily standup + planowanie"
            )
            # Deep work
            tracker.log_manual_block(
                f"{day_str}T09:00:00", f"{day_str}T12:00:00",
                "praca", description="Deep work session"
            )
            # Obiad
            tracker.log_manual_block(
                f"{day_str}T12:00:00", f"{day_str}T12:30:00",
                "jedzenie", description="Obiad"
            )
            # Popołudniowa praca
            tracker.log_manual_block(
                f"{day_str}T13:00:00", f"{day_str}T16:00:00",
                "praca", description="Meetingi + kodowanie"
            )
            # Siłownia (co drugi dzień)
            if days_ago % 2 == 0:
                tracker.log_manual_block(
                    f"{day_str}T17:00:00", f"{day_str}T18:30:00",
                    "zdrowie", description="Siłownia"
                )
            # Hobby
            tracker.log_manual_block(
                f"{day_str}T19:00:00", f"{day_str}T20:30:00",
                "hobby", description="Gitara / czytanie"
            )

            # Kontakt z rodziną (co 2-3 dni)
            if days_ago % 3 == 0:
                mama_id = people_by_name.get("Mama")
                if mama_id:
                    tracker.log_manual_block(
                        f"{day_str}T18:00:00", f"{day_str}T18:30:00",
                        "rodzina", person_id=mama_id, description="Telefon do Mamy"
                    )

            # Kontakt z przyjaciółmi (co kilka dni)
            if days_ago % 4 == 1:
                marek_id = people_by_name.get("Kumpel Marek")
                if marek_id:
                    tracker.log_manual_block(
                        f"{day_str}T16:00:00", f"{day_str}T16:30:00",
                        "znajomi", person_id=marek_id, description="Kawa z Markiem"
                    )

        # Dodaj wydarzenia
        print("Dodawanie wydarzeń...")
        mama_id = people_by_name.get("Mama")
        tata_id = people_by_name.get("Tata")

        if mama_id:
            events.add_event(
                "Urodziny Mamy", "2026-03-15", "urodziny",
                person_id=mama_id, recurring=True, reminder_days_before=7,
            )
        if tata_id:
            events.add_event(
                "Urodziny Taty", "2026-08-22", "urodziny",
                person_id=tata_id, recurring=True, reminder_days_before=7,
            )

        events.add_event(
            "Deadline projektu Q3", "2026-09-30", "deadline",
            reminder_days_before=14,
        )
        events.add_event(
            "Wizyta u dentysty", "2026-08-15", "zdrowie",
            reminder_days_before=3,
        )

        # Dodaj logi nawyków
        print("Dodawanie logów nawyków...")
        for days_ago in range(7):
            d = today - timedelta(days=days_ago)
            habits.log("pills", "taken")
            if days_ago % 2 == 0:
                habits.log("exercise", "60min siłownia")
            if days_ago % 3 == 0:
                habits.log("intrusive_thought", "occurred", intensity=5)
            if days_ago % 4 == 0:
                habits.log("snacking", "occurred", intensity=3)

        print("✅ Seed complete!")


# ── Simple Web Dashboard ─────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Life Management Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f23; color: #e0e0e0; padding: 20px; }
        h1 { color: #00ff88; margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .card { background: #1a1a2e; border-radius: 12px; padding: 20px; border: 1px solid #2a2a4a; }
        .card h2 { color: #00ff88; font-size: 1.1em; margin-bottom: 12px; }
        .stat { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #2a2a4a; }
        .stat:last-child { border-bottom: none; }
        .stat-label { color: #888; }
        .stat-value { font-weight: bold; }
        .bar { height: 20px; background: #2a2a4a; border-radius: 10px; margin: 4px 0; overflow: hidden; }
        .bar-fill { height: 100%; border-radius: 10px; transition: width 0.3s; }
        .alert { padding: 8px 12px; border-radius: 8px; margin: 4px 0; }
        .alert-critical { background: #ff444420; border-left: 3px solid #ff4444; }
        .alert-high { background: #ffaa0020; border-left: 3px solid #ffaa00; }
        .alert-medium { background: #00aaff20; border-left: 3px solid #00aaff; }
        .alert-low { background: #00ff8820; border-left: 3px solid #00ff88; }
        .person-row { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
        .person-overdue { color: #ff4444; }
        .person-ok { color: #00ff88; }
        .refresh { color: #888; font-size: 0.8em; text-align: right; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>🧬 Life Management Dashboard</h1>
    <div class="grid">
        <div class="card">
            <h2>⏱️ Dziś</h2>
            <div id="today-stats">Ładowanie...</div>
        </div>
        <div class="card">
            <h2>👥 Osoby (top 10)</h2>
            <div id="people-balance">Ładowanie...</div>
        </div>
        <div class="card">
            <h2>🔔 Alerty</h2>
            <div id="alerts">Ładowanie...</div>
        </div>
        <div class="card">
            <h2>💊 Nawykowe streaki</h2>
            <div id="streaks">Ładowanie...</div>
        </div>
        <div class="card">
            <h2>📅 Nadchodzące</h2>
            <div id="upcoming">Ładowanie...</div>
        </div>
        <div class="card">
            <h2>📊 Tydzień</h2>
            <div id="weekly">Ładowanie...</div>
        </div>
    </div>
    <div class="refresh" id="refresh-time"></div>

    <script>
        const COLORS = {
            praca: '#4a9eff', rodzina: '#ff6b6b', znajomi: '#ffd93d',
            zdrowie: '#6bcb77', jedzenie: '#ff8c42', hobby: '#a855f7',
            odpoczynek: '#4ecdc4', nauka: '#ff6b9d', administracja: '#95a5a6',
            transport: '#e67e22', higiena: '#1abc9c', inne: '#7f8c8d'
        };

        async function loadData() {
            try {
                const resp = await fetch('/api/dashboard');
                const data = await resp.json();
                renderToday(data.today);
                renderPeople(data.people);
                renderAlerts(data.alerts);
                renderStreaks(data.streaks);
                renderUpcoming(data.upcoming);
                renderWeekly(data.weekly);
                document.getElementById('refresh-time').textContent =
                    'Odświeżono: ' + new Date().toLocaleTimeString('pl-PL');
            } catch(e) {
                console.error(e);
            }
        }

        function renderToday(today) {
            const el = document.getElementById('today-stats');
            if (!today) { el.innerHTML = 'Brak danych'; return; }
            let html = `<div class="stat"><span class="stat-label">Śledzone</span><span class="stat-value">${today.total_hours}h (${today.coverage_pct}%)</span></div>`;
            for (const [cat, mins] of Object.entries(today.by_category || {})) {
                const hours = (mins / 60).toFixed(1);
                const pct = today.total_minutes > 0 ? (mins / today.total_minutes * 100).toFixed(0) : 0;
                html += `<div class="stat">
                    <span class="stat-label">${cat}</span>
                    <span class="stat-value">${hours}h</span>
                </div>
                <div class="bar"><div class="bar-fill" style="width:${pct}%;background:${COLORS[cat] || '#888'}"></div></div>`;
            }
            el.innerHTML = html;
        }

        function renderPeople(people) {
            const el = document.getElementById('people-balance');
            if (!people || !people.length) { el.innerHTML = 'Brak osób'; return; }
            let html = '';
            for (const p of people.slice(0, 10)) {
                const cls = p.overdue ? 'person-overdue' : 'person-ok';
                const icon = p.overdue ? '🔴' : '🟢';
                html += `<div class="person-row">
                    <span class="${cls}">${icon} ${p.name} <small>(${p.category})</small></span>
                    <span>${p.hours_last_30d}h | ${p.days_since_contact || '?'}d</span>
                </div>`;
            }
            el.innerHTML = html;
        }

        function renderAlerts(alerts) {
            const el = document.getElementById('alerts');
            if (!alerts || !alerts.length) { el.innerHTML = '✅ Brak alertów'; return; }
            let html = '';
            for (const a of alerts) {
                html += `<div class="alert alert-${a.priority}">${a.message}<br><small>→ ${a.action}</small></div>`;
            }
            el.innerHTML = html;
        }

        function renderStreaks(streaks) {
            const el = document.getElementById('streaks');
            if (!streaks) { el.innerHTML = 'Brak danych'; return; }
            let html = '';
            for (const [name, days] of Object.entries(streaks)) {
                const fire = days >= 7 ? '🔥'.repeat(Math.min(days, 5)) : '';
                html += `<div class="stat"><span class="stat-label">${name}</span><span class="stat-value">${days} dni ${fire}</span></div>`;
            }
            el.innerHTML = html || 'Brak streaków';
        }

        function renderUpcoming(upcoming) {
            const el = document.getElementById('upcoming');
            if (!upcoming) { el.innerHTML = 'Brak danych'; return; }
            let html = '';
            if (upcoming.birthdays && upcoming.birthdays.length) {
                html += '<strong>🎂 Urodziny:</strong><br>';
                for (const b of upcoming.birthdays.slice(0, 5)) {
                    html += `<div>${b.name} — za ${b.days_until} dni (${b.age} lat)</div>`;
                }
            }
            if (upcoming.events && upcoming.events.length) {
                html += '<br><strong>📌 Wydarzenia:</strong><br>';
                for (const e of upcoming.events.slice(0, 5)) {
                    html += `<div>${e.event_date} — ${e.title}</div>`;
                }
            }
            el.innerHTML = html || 'Brak nadchodzących';
        }

        function renderWeekly(weekly) {
            const el = document.getElementById('weekly');
            if (!weekly) { el.innerHTML = 'Brak danych'; return; }
            let html = `<div class="stat"><span class="stat-label">Średnio dziennie</span><span class="stat-value">${weekly.daily_average_hours}h</span></div>`;
            for (const [cat, hours] of Object.entries(weekly.by_category || {})) {
                html += `<div class="stat"><span class="stat-label">${cat}</span><span class="stat-value">${hours}h</span></div>`;
            }
            el.innerHTML = html;
        }

        loadData();
        setInterval(loadData, 60000);  // Odświeżaj co minutę
    </script>
</body>
</html>"""


def generate_dashboard_html(db: LifeDB) -> str:
    """Generuj plik dashboard.html z osadzonymi danymi."""
    tracker = TimeTracker(db)
    people = PeopleManager(db)
    events = EventManager(db)
    habits = HabitTracker(db)
    notifier = NotificationBridge(db)

    today = tracker.get_today_summary()
    balance = people.get_balance_report()
    alerts = notifier.get_all_notifications()
    birthdays = people.get_upcoming_birthdays(days_ahead=30)
    upcoming_events = events.get_upcoming_events(days_ahead=30)
    weekly = tracker.get_weekly_report()

    streaks = {
        "pigułki": habits.get_streak("pills"),
        "ćwiczenia": habits.get_streak("exercise"),
    }

    dashboard_data = {
        "today": today,
        "people": balance["people"],
        "alerts": alerts,
        "streaks": streaks,
        "upcoming": {
            "birthdays": birthdays,
            "events": [dict(e) for e in upcoming_events],
        },
        "weekly": weekly,
    }

    # Wstrzyknij dane do HTML
    html = DASHBOARD_HTML.replace(
        "async function loadData() {",
        f"const EMBEDDED_DATA = {json.dumps(dashboard_data)};\n"
        "async function loadData() {\n"
        "    renderToday(EMBEDDED_DATA.today);\n"
        "    renderPeople(EMBEDDED_DATA.people);\n"
        "    renderAlerts(EMBEDDED_DATA.alerts);\n"
        "    renderStreaks(EMBEDDED_DATA.streaks);\n"
        "    renderUpcoming(EMBEDDED_DATA.upcoming);\n"
        "    renderWeekly(EMBEDDED_DATA.weekly);\n"
        "    document.getElementById('refresh-time').textContent = 'Wygenerowano: ' + new Date().toLocaleTimeString('pl-PL');\n"
        "    return; }\n"
        "async function _loadData() {"
    )

    return html


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI do zarządzania integracją z Hermesem."""
    if len(sys.argv) < 2:
        print("Hermes Integration — CLI")
        print()
        print("Komendy:")
        print("  setup-cron          — skonfiguruj wszystkie cron jobs")
        print("  list-cron           — wypisz cron jobs")
        print("  remove-cron         — usuń wszystkie life-management cron jobs")
        print("  seed                — wypełnij bazę 50 przykładowymi osobami + danymi")
        print("  dashboard           — wygeneruj dashboard.html")
        print("  alerts              — pokaż wszystkie alerty/powiadomienia")
        return

    cmd = sys.argv[1]

    if cmd == "setup-cron":
        print("Konfiguracja cron jobs...")
        created = CronManager.setup_all()
        print(f"\n✅ Skonfigurowano {len(created)} jobów")

    elif cmd == "list-cron":
        CronManager.list_all()

    elif cmd == "remove-cron":
        print("Usuwanie life-management cron jobs...")
        CronManager.remove_all()
        print("✅ Usunięto")

    elif cmd == "seed":
        print("Generowanie danych testowych...")
        db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        db = LifeDB(db_path)
        SeedGenerator.seed_sample_data(db)

    elif cmd == "dashboard":
        db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
        if not os.path.exists(db_path):
            print("Najpierw uruchom 'seed' aby wygenerować dane testowe")
            return
        db = LifeDB(db_path)
        html = generate_dashboard_html(db)
        output_path = LIFE_DIR / "dashboard.html"
        output_path.write_text(html)
        print(f"✅ Dashboard wygenerowany: {output_path}")

    elif cmd == "alerts":
        db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
        if not os.path.exists(db_path):
            print("Najpierw uruchom 'seed' aby wygenerować dane testowe")
            return
        db = LifeDB(db_path)
        notifier = NotificationBridge(db)
        print(notifier.format_for_hermes())

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
