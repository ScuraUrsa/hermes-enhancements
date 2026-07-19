#!/usr/bin/env python3
"""
Life Management — Gamification Engine
=======================================
XP, poziomy, achievementy, daily quests, weekly challenges.
Motywuje do trzymania się systemu przez mechanikę gry.

Zasady XP:
- Zalogowanie bloku czasu: +5 XP
- Wzięcie pigułek: +10 XP (streak bonus: +2 XP za każdy dzień serii)
- Ćwiczenia: +15 XP
- Kontakt z osobą: +20 XP
- Daily brief przeczytany: +5 XP
- 100% pokrycia dnia: +50 XP
- 7-dniowy streak pigułek: +100 XP
- Tydzień bez overdue kontaktów: +200 XP

Poziomy:
- Level 1: 0 XP (Nowicjusz)
- Level 2: 100 XP (Praktykant)
- Level 3: 300 XP (Rzemieślnik)
- Level 5: 1000 XP (Mistrz)
- Level 10: 5000 XP (Arcymistrz)
- Level 20: 20000 XP (Legenda)
"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker

LIFE_DIR = Path(__file__).parent


# ── XP & Levels ──────────────────────────────────────────────────────────────

LEVELS = [
    (0, "🌱 Nowicjusz"),
    (100, "📗 Praktykant"),
    (300, "📘 Rzemieślnik"),
    (600, "📙 Adept"),
    (1000, "📕 Mistrz"),
    (2000, "💎 Ekspert"),
    (3500, "👑 Weteran"),
    (5000, "🌟 Arcymistrz"),
    (8000, "🔥 Feniks"),
    (12000, "⚡ Tytan"),
    (20000, "🌌 Legenda"),
    (35000, "🧬 Transcendencja"),
]

ACHIEVEMENTS = {
    "first_block": {"name": "Pierwszy krok", "desc": "Zaloguj pierwszy blok czasu", "xp": 25, "icon": "👣"},
    "first_pill": {"name": "Zdrowy nawyk", "desc": "Weź pigułki pierwszy raz", "xp": 25, "icon": "💊"},
    "pill_streak_7": {"name": "Tydzień zdrowia", "desc": "7 dni z rzędu z pigułkami", "xp": 100, "icon": "🔥"},
    "pill_streak_30": {"name": "Miesiąc zdrowia", "desc": "30 dni z rzędu z pigułkami", "xp": 500, "icon": "💪"},
    "pill_streak_90": {"name": "Żelazna dyscyplina", "desc": "90 dni z rzędu z pigułkami", "xp": 1500, "icon": "🏆"},
    "first_exercise": {"name": "Ruch to zdrowie", "desc": "Zaloguj pierwsze ćwiczenia", "xp": 25, "icon": "🏃"},
    "exercise_week": {"name": "Aktywny tydzień", "desc": "Ćwicz 5+ razy w tygodniu", "xp": 150, "icon": "💪"},
    "first_contact": {"name": "Towarzyski", "desc": "Zaloguj pierwszy kontakt z osobą", "xp": 25, "icon": "👋"},
    "no_overdue_week": {"name": "Niezawodny", "desc": "Tydzień bez overdue kontaktów", "xp": 200, "icon": "✅"},
    "no_overdue_month": {"name": "Filary społeczności", "desc": "30 dni bez overdue kontaktów", "xp": 750, "icon": "🌟"},
    "full_day": {"name": "Pełny dzień", "desc": "100% pokrycia dnia (24h śledzone)", "xp": 100, "icon": "📅"},
    "full_week": {"name": "Pełny tydzień", "desc": "7 dni z >80% pokrycia", "xp": 500, "icon": "📊"},
    "first_thought_logged": {"name": "Świadomość", "desc": "Zaloguj pierwszą natarczywą myśl", "xp": 25, "icon": "🧠"},
    "thought_free_day": {"name": "Spokojny umysł", "desc": "Dzień bez natarczywych myśli", "xp": 50, "icon": "☮️"},
    "no_snack_day": {"name": "Silna wola", "desc": "Dzień bez podjadania", "xp": 50, "icon": "🚫"},
    "focus_master": {"name": "Mistrz skupienia", "desc": "10 sesji deep work w tygodniu", "xp": 200, "icon": "🎯"},
    "social_butterfly": {"name": "Motyl społeczny", "desc": "Kontakt z 10+ różnymi osobami w tygodniu", "xp": 300, "icon": "🦋"},
    "balanced_life": {"name": "Balans", "desc": "Wszystkie 6 kategorii czasu w jednym dniu", "xp": 150, "icon": "⚖️"},
    "level_5": {"name": "Mistrz życia", "desc": "Osiągnij poziom 5", "xp": 0, "icon": "📕"},
    "level_10": {"name": "Arcymistrz życia", "desc": "Osiągnij poziom 10", "xp": 0, "icon": "🌟"},
}

DAILY_QUESTS = [
    {"id": "log_5_blocks", "name": "Rejestrator", "desc": "Zaloguj 5+ bloków czasu", "xp": 30, "target": 5},
    {"id": "pill_taken", "name": "Tabletkowy", "desc": "Weź pigułki", "xp": 20, "target": 1},
    {"id": "exercise_done", "name": "Aktywny", "desc": "Zrób ćwiczenia", "xp": 30, "target": 1},
    {"id": "contact_person", "name": "Społecznik", "desc": "Skontaktuj się z 1+ osobą", "xp": 25, "target": 1},
    {"id": "no_snacking", "name": "Czysta dieta", "desc": "Zero podjadania", "xp": 40, "target": 0},
    {"id": "water_2l", "name": "Nawodniony", "desc": "Wypij 2L wody", "xp": 20, "target": 8},  # 8x250ml
    {"id": "focus_session", "name": "Skupiony", "desc": "1+ sesja deep work", "xp": 25, "target": 1},
]

WEEKLY_CHALLENGES = [
    {"id": "perfect_pills", "name": "Perfekcyjny tydzień", "desc": "Pigułki 7/7 dni", "xp": 150},
    {"id": "exercise_5", "name": "Tydzień ruchu", "desc": "Ćwiczenia 5+ razy", "xp": 200},
    {"id": "contacts_10", "name": "Społeczny tydzień", "desc": "Kontakt z 10+ osobami", "xp": 250},
    {"id": "coverage_80", "name": "Świadomy tydzień", "desc": "Średnie pokrycie >80%", "xp": 300},
    {"id": "no_overdue", "name": "Niezawodny tydzień", "desc": "Zero overdue kontaktów", "xp": 200},
    {"id": "focus_10", "name": "Tydzień skupienia", "desc": "10+ sesji deep work", "xp": 250},
    {"id": "balanced_week", "name": "Balans tygodnia", "desc": "Wszystkie kategorie czasu", "xp": 200},
]


# ── Gamification Engine ──────────────────────────────────────────────────────

class Gamification:
    """Silnik gamifikacji — XP, poziomy, achievementy, questy."""

    def __init__(self, db: LifeDB):
        self.db = db
        self.tracker = TimeTracker(db)
        self.people = PeopleManager(db)
        self.events = EventManager(db)
        self.habits = HabitTracker(db)
        self._init_tables()

    def _init_tables(self):
        """Dodaj tabele gamifikacji do bazy."""
        with self.db._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS xp_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS achievements_unlocked (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    achievement_id TEXT NOT NULL,
                    unlocked_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(achievement_id)
                );

                CREATE TABLE IF NOT EXISTS daily_quests_completed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quest_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(quest_id, date)
                );

                CREATE TABLE IF NOT EXISTS weekly_challenges_completed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenge_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(challenge_id, week_start)
                );

                CREATE INDEX IF NOT EXISTS idx_xp_log_timestamp ON xp_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_achievements ON achievements_unlocked(achievement_id);
            """)

    # ── XP ───────────────────────────────────────────────────────────────

    def add_xp(self, source: str, amount: int, description: str = "") -> int:
        """Dodaj XP i zwróć nowy total."""
        now = datetime.now().isoformat()
        self.db.insert("xp_log", {
            "timestamp": now,
            "source": source,
            "amount": amount,
            "description": description,
            "created_at": now,
        })
        return self.get_total_xp()

    def get_total_xp(self) -> int:
        """Suma wszystkich XP."""
        row = self.db.execute_one("SELECT COALESCE(SUM(amount), 0) as total FROM xp_log")
        return row["total"] if row else 0

    def get_level(self) -> dict:
        """Aktualny poziom i progress."""
        xp = self.get_total_xp()
        current_level = 1
        current_name = LEVELS[0][1]
        next_level_xp = LEVELS[1][0] if len(LEVELS) > 1 else 999999
        xp_for_current = 0

        for i, (threshold, name) in enumerate(LEVELS):
            if xp >= threshold:
                current_level = i + 1
                current_name = name
                xp_for_current = threshold
                next_level_xp = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else threshold + 99999
            else:
                next_level_xp = threshold
                break

        progress = min(100, round((xp - xp_for_current) / max(1, next_level_xp - xp_for_current) * 100))

        return {
            "level": current_level,
            "name": current_name,
            "xp": xp,
            "xp_for_current": xp_for_current,
            "xp_to_next": next_level_xp,
            "xp_needed": next_level_xp - xp,
            "progress_pct": progress,
        }

    def get_xp_history(self, days: int = 7) -> list[dict]:
        """Historia XP z ostatnich N dni."""
        since = (date.today() - timedelta(days=days)).isoformat()
        return self.db.execute(
            "SELECT date(timestamp) as day, SUM(amount) as xp FROM xp_log WHERE timestamp >= ? GROUP BY day ORDER BY day",
            (since,),
        )

    # ── Achievements ─────────────────────────────────────────────────────

    def check_achievements(self) -> list[dict]:
        """Sprawdź i odblokuj nowe achievementy."""
        unlocked = self._get_unlocked_ids()
        new_unlocks = []

        for ach_id, ach in ACHIEVEMENTS.items():
            if ach_id in unlocked:
                continue
            if self._check_achievement(ach_id):
                now = datetime.now().isoformat()
                self.db.insert("achievements_unlocked", {
                    "achievement_id": ach_id,
                    "unlocked_at": now,
                    "created_at": now,
                })
                if ach["xp"] > 0:
                    self.add_xp("achievement", ach["xp"], f"🏆 {ach['name']}")
                new_unlocks.append({**ach, "id": ach_id})

        return new_unlocks

    def _get_unlocked_ids(self) -> set:
        rows = self.db.execute("SELECT achievement_id FROM achievements_unlocked")
        return {r["achievement_id"] for r in rows}

    def _check_achievement(self, ach_id: str) -> bool:
        """Sprawdź czy achievement jest spełniony."""
        today = date.today()

        if ach_id == "first_block":
            blocks = self.db.execute("SELECT COUNT(*) as c FROM time_blocks")
            return blocks[0]["c"] > 0

        if ach_id == "first_pill":
            pills = self.db.execute("SELECT COUNT(*) as c FROM habit_log WHERE habit_type='pills'")
            return pills[0]["c"] > 0

        if ach_id == "pill_streak_7":
            return self.habits.get_streak("pills") >= 7

        if ach_id == "pill_streak_30":
            return self.habits.get_streak("pills") >= 30

        if ach_id == "pill_streak_90":
            return self.habits.get_streak("pills") >= 90

        if ach_id == "first_exercise":
            ex = self.db.execute("SELECT COUNT(*) as c FROM habit_log WHERE habit_type='exercise'")
            return ex[0]["c"] > 0

        if ach_id == "exercise_week":
            week_ago = (today - timedelta(days=7)).isoformat()
            days = self.db.execute(
                "SELECT COUNT(DISTINCT date(timestamp)) as c FROM habit_log WHERE habit_type='exercise' AND timestamp >= ?",
                (week_ago,),
            )
            return days[0]["c"] >= 5

        if ach_id == "first_contact":
            contacts = self.db.execute("SELECT COUNT(*) as c FROM time_blocks WHERE person_id IS NOT NULL")
            return contacts[0]["c"] > 0

        if ach_id == "no_overdue_week":
            balance = self.people.get_balance_report()
            return balance["overdue_count"] == 0

        if ach_id == "no_overdue_month":
            # Sprawdź czy kiedykolwiek był overdue w ostatnich 30 dniach
            balance = self.people.get_balance_report()
            return balance["overdue_count"] == 0 and balance["total_people"] > 0

        if ach_id == "full_day":
            summary = self.tracker.get_today_summary()
            return summary["coverage_pct"] >= 95

        if ach_id == "full_week":
            # Sprawdź ostatnie 7 dni
            total_coverage = 0
            for d in range(7):
                day = today - timedelta(days=d)
                blocks = self.db.execute(
                    """SELECT COALESCE(SUM((julianday(end_time)-julianday(start_time))*24*60),0) as mins
                       FROM time_blocks WHERE date(start_time) = ?""",
                    (day.isoformat(),),
                )
                mins = blocks[0]["mins"]
                coverage = min(100, mins / 1440 * 100)
                total_coverage += coverage
            return (total_coverage / 7) >= 80

        if ach_id == "first_thought_logged":
            thoughts = self.db.execute("SELECT COUNT(*) as c FROM habit_log WHERE habit_type='intrusive_thought'")
            return thoughts[0]["c"] > 0

        if ach_id == "thought_free_day":
            today_habits = self.habits.get_today_habits()
            return "intrusive_thought" not in today_habits

        if ach_id == "no_snack_day":
            today_habits = self.habits.get_today_habits()
            return "snacking" not in today_habits

        if ach_id == "focus_master":
            week_ago = (today - timedelta(days=7)).isoformat()
            sessions = self.db.execute(
                "SELECT COUNT(*) as c FROM habit_log WHERE habit_type='focus_session' AND timestamp >= ?",
                (week_ago,),
            )
            return sessions[0]["c"] >= 10

        if ach_id == "social_butterfly":
            week_ago = (today - timedelta(days=7)).isoformat()
            people_count = self.db.execute(
                "SELECT COUNT(DISTINCT person_id) as c FROM time_blocks WHERE person_id IS NOT NULL AND start_time >= ?",
                (week_ago,),
            )
            return people_count[0]["c"] >= 10

        if ach_id == "balanced_life":
            today_str = today.isoformat()
            cats = self.db.execute(
                "SELECT COUNT(DISTINCT category) as c FROM time_blocks WHERE date(start_time) = ?",
                (today_str,),
            )
            return cats[0]["c"] >= 6

        if ach_id == "level_5":
            return self.get_level()["level"] >= 5

        if ach_id == "level_10":
            return self.get_level()["level"] >= 10

        return False

    def get_all_achievements(self) -> list[dict]:
        """Wszystkie achievementy z informacją o odblokowaniu."""
        unlocked = self._get_unlocked_ids()
        result = []
        for ach_id, ach in ACHIEVEMENTS.items():
            result.append({
                **ach,
                "id": ach_id,
                "unlocked": ach_id in unlocked,
            })
        return result

    # ── Daily Quests ─────────────────────────────────────────────────────

    def get_daily_quests(self) -> list[dict]:
        """Daily questy z postępem."""
        today = date.today().isoformat()
        completed = self._get_completed_quests(today)
        today_habits = self.habits.get_today_habits()

        result = []
        for q in DAILY_QUESTS:
            progress = self._quest_progress(q["id"], today_habits)
            done = q["id"] in completed or progress >= q["target"]
            result.append({**q, "progress": progress, "done": done})
        return result

    def _get_completed_quests(self, date_str: str) -> set:
        rows = self.db.execute(
            "SELECT quest_id FROM daily_quests_completed WHERE date = ?",
            (date_str,),
        )
        return {r["quest_id"] for r in rows}

    def _quest_progress(self, quest_id: str, today_habits: dict) -> int:
        """Policz postęp questa."""
        today = date.today().isoformat()

        if quest_id == "log_5_blocks":
            blocks = self.db.execute(
                "SELECT COUNT(*) as c FROM time_blocks WHERE date(start_time) = ?",
                (today,),
            )
            return blocks[0]["c"]

        if quest_id == "pill_taken":
            return len(today_habits.get("pills", []))

        if quest_id == "exercise_done":
            return len(today_habits.get("exercise", []))

        if quest_id == "contact_person":
            contacts = self.db.execute(
                "SELECT COUNT(DISTINCT person_id) as c FROM time_blocks WHERE person_id IS NOT NULL AND date(start_time) = ?",
                (today,),
            )
            return contacts[0]["c"]

        if quest_id == "no_snacking":
            return len(today_habits.get("snacking", []))

        if quest_id == "water_2l":
            water_logs = today_habits.get("water", [])
            return len(water_logs)

        if quest_id == "focus_session":
            return len(today_habits.get("focus_session", []))

        return 0

    def complete_quest(self, quest_id: str) -> dict | None:
        """Oznacz quest jako ukończony i przyznaj XP."""
        today = date.today().isoformat()
        completed = self._get_completed_quests(today)

        if quest_id in completed:
            return None

        quest = next((q for q in DAILY_QUESTS if q["id"] == quest_id), None)
        if not quest:
            return None

        now = datetime.now().isoformat()
        self.db.insert("daily_quests_completed", {
            "quest_id": quest_id,
            "date": today,
            "completed_at": now,
            "created_at": now,
        })

        self.add_xp("daily_quest", quest["xp"], f"📋 {quest['name']}")
        return quest

    # ── Weekly Challenges ─────────────────────────────────────────────────

    def get_weekly_challenges(self) -> list[dict]:
        """Weekly challenge'y z postępem."""
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        completed = self._get_completed_challenges(week_start)

        result = []
        for c in WEEKLY_CHALLENGES:
            progress = self._challenge_progress(c["id"])
            done = c["id"] in completed or progress >= 100
            result.append({**c, "progress": progress, "done": done})
        return result

    def _get_completed_challenges(self, week_start: str) -> set:
        rows = self.db.execute(
            "SELECT challenge_id FROM weekly_challenges_completed WHERE week_start = ?",
            (week_start,),
        )
        return {r["challenge_id"] for r in rows}

    def _challenge_progress(self, challenge_id: str) -> int:
        """Procentowy postęp challenge'u."""
        today = date.today()
        week_ago = (today - timedelta(days=7)).isoformat()

        if challenge_id == "perfect_pills":
            days_with_pills = self.db.execute(
                "SELECT COUNT(DISTINCT date(timestamp)) as c FROM habit_log WHERE habit_type='pills' AND timestamp >= ?",
                (week_ago,),
            )
            return min(100, round(days_with_pills[0]["c"] / 7 * 100))

        if challenge_id == "exercise_5":
            days = self.db.execute(
                "SELECT COUNT(DISTINCT date(timestamp)) as c FROM habit_log WHERE habit_type='exercise' AND timestamp >= ?",
                (week_ago,),
            )
            return min(100, round(days[0]["c"] / 5 * 100))

        if challenge_id == "contacts_10":
            people_count = self.db.execute(
                "SELECT COUNT(DISTINCT person_id) as c FROM time_blocks WHERE person_id IS NOT NULL AND start_time >= ?",
                (week_ago,),
            )
            return min(100, round(people_count[0]["c"] / 10 * 100))

        if challenge_id == "coverage_80":
            total_coverage = 0
            days_count = 0
            for d in range(7):
                day = today - timedelta(days=d)
                blocks = self.db.execute(
                    "SELECT COALESCE(SUM((julianday(end_time)-julianday(start_time))*24*60),0) as mins FROM time_blocks WHERE date(start_time) = ?",
                    (day.isoformat(),),
                )
                if blocks[0]["mins"] > 0:
                    days_count += 1
                    total_coverage += min(100, blocks[0]["mins"] / 1440 * 100)
            avg = total_coverage / max(1, days_count)
            return min(100, round(avg / 80 * 100))

        if challenge_id == "no_overdue":
            balance = self.people.get_balance_report()
            return 100 if balance["overdue_count"] == 0 else max(0, 100 - balance["overdue_count"] * 20)

        if challenge_id == "focus_10":
            sessions = self.db.execute(
                "SELECT COUNT(*) as c FROM habit_log WHERE habit_type='focus_session' AND timestamp >= ?",
                (week_ago,),
            )
            return min(100, round(sessions[0]["c"] / 10 * 100))

        if challenge_id == "balanced_week":
            cats = self.db.execute(
                "SELECT COUNT(DISTINCT category) as c FROM time_blocks WHERE start_time >= ?",
                (week_ago,),
            )
            return min(100, round(cats[0]["c"] / 6 * 100))

        return 0

    def complete_challenge(self, challenge_id: str) -> dict | None:
        """Oznacz challenge jako ukończony."""
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        completed = self._get_completed_challenges(week_start)

        if challenge_id in completed:
            return None

        challenge = next((c for c in WEEKLY_CHALLENGES if c["id"] == challenge_id), None)
        if not challenge:
            return None

        now = datetime.now().isoformat()
        self.db.insert("weekly_challenges_completed", {
            "challenge_id": challenge_id,
            "week_start": week_start,
            "completed_at": now,
            "created_at": now,
        })

        self.add_xp("weekly_challenge", challenge["xp"], f"🏆 {challenge['name']}")
        return challenge

    # ── Auto-check ───────────────────────────────────────────────────────

    def auto_check_all(self) -> dict:
        """Automatycznie sprawdź achievementy, questy i challenge'y."""
        new_achievements = self.check_achievements()

        # Auto-complete questy które są spełnione
        quests = self.get_daily_quests()
        completed_quests = []
        for q in quests:
            if q["progress"] >= q["target"] and not q["done"]:
                result = self.complete_quest(q["id"])
                if result:
                    completed_quests.append(result)

        # Auto-complete challenge'y
        challenges = self.get_weekly_challenges()
        completed_challenges = []
        for c in challenges:
            if c["progress"] >= 100 and not c["done"]:
                result = self.complete_challenge(c["id"])
                if result:
                    completed_challenges.append(result)

        level = self.get_level()

        return {
            "new_achievements": new_achievements,
            "completed_quests": completed_quests,
            "completed_challenges": completed_challenges,
            "level": level,
            "total_xp": level["xp"],
        }

    def get_status(self) -> dict:
        """Pełny status gamifikacji."""
        return {
            "level": self.get_level(),
            "achievements": self.get_all_achievements(),
            "daily_quests": self.get_daily_quests(),
            "weekly_challenges": self.get_weekly_challenges(),
            "xp_history_7d": self.get_xp_history(7),
        }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Life Gamification — CLI")
        print()
        print("Komendy:")
        print("  status          — pełny status (level, XP, achievementy, questy)")
        print("  level           — aktualny poziom i progress")
        print("  achievements    — lista achievementów")
        print("  quests          — daily questy")
        print("  challenges      — weekly challenge'y")
        print("  check           — auto-check i przyznaj nagrody")
        print("  xp <source> <amount> [desc] — ręcznie dodaj XP")
        return

    cmd = sys.argv[1]
    db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
    if not os.path.exists(db_path):
        db_path = str(LIFE_DIR / "data" / "bot_life.db")

    db = LifeDB(db_path)
    g = Gamification(db)

    if cmd == "status":
        status = g.get_status()
        lvl = status["level"]
        print(f"🧬 {lvl['name']} — Level {lvl['level']}")
        print(f"   XP: {lvl['xp']} / {lvl['xp_to_next']} ({lvl['progress_pct']}%)")
        print(f"   Do następnego: {lvl['xp_needed']} XP")
        print()

        unlocked = [a for a in status["achievements"] if a["unlocked"]]
        print(f"🏆 Achievementy: {len(unlocked)}/{len(status['achievements'])}")
        for a in unlocked[-5:]:
            print(f"   {a['icon']} {a['name']}")

        print()
        print("📋 Daily Questy:")
        for q in status["daily_quests"]:
            icon = "✅" if q["done"] else "⬜"
            print(f"   {icon} {q['name']}: {q['progress']}/{q['target']}")

        print()
        print("🏆 Weekly Challenge'y:")
        for c in status["weekly_challenges"]:
            icon = "✅" if c["done"] else "⬜"
            print(f"   {icon} {c['name']}: {c['progress']}%")

    elif cmd == "level":
        lvl = g.get_level()
        bar_len = 20
        filled = int(lvl["progress_pct"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"🧬 {lvl['name']} — Level {lvl['level']}")
        print(f"   [{bar}] {lvl['progress_pct']}%")
        print(f"   {lvl['xp']} / {lvl['xp_to_next']} XP ({lvl['xp_needed']} do następnego)")

    elif cmd == "achievements":
        all_ach = g.get_all_achievements()
        for a in all_ach:
            icon = a["icon"] if a["unlocked"] else "🔒"
            print(f"  {icon} {a['name']}: {a['desc']}")

    elif cmd == "quests":
        quests = g.get_daily_quests()
        for q in quests:
            icon = "✅" if q["done"] else "⬜"
            print(f"  {icon} {q['name']}: {q['progress']}/{q['target']} — {q['xp']} XP")

    elif cmd == "challenges":
        challenges = g.get_weekly_challenges()
        for c in challenges:
            icon = "✅" if c["done"] else "⬜"
            print(f"  {icon} {c['name']}: {c['progress']}% — {c['xp']} XP")

    elif cmd == "check":
        result = g.auto_check_all()
        print(f"🧬 Level {result['level']['level']} — {result['level']['name']}")
        print(f"   XP: {result['total_xp']}")

        if result["new_achievements"]:
            print(f"\n🏆 Nowe achievementy ({len(result['new_achievements'])}):")
            for a in result["new_achievements"]:
                print(f"   {a['icon']} {a['name']}: {a['desc']} (+{a['xp']} XP)")

        if result["completed_quests"]:
            print(f"\n📋 Ukończone questy ({len(result['completed_quests'])}):")
            for q in result["completed_quests"]:
                print(f"   ✅ {q['name']} (+{q['xp']} XP)")

        if result["completed_challenges"]:
            print(f"\n🏆 Ukończone challenge'y ({len(result['completed_challenges'])}):")
            for c in result["completed_challenges"]:
                print(f"   ✅ {c['name']} (+{c['xp']} XP)")

        if not any([result["new_achievements"], result["completed_quests"], result["completed_challenges"]]):
            print("\n   Brak nowych nagród. Działaj dalej!")

    elif cmd == "xp" and len(sys.argv) >= 4:
        source = sys.argv[2]
        amount = int(sys.argv[3])
        desc = sys.argv[4] if len(sys.argv) >= 5 else ""
        total = g.add_xp(source, amount, desc)
        print(f"✅ +{amount} XP ({source}) → Total: {total} XP")

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
