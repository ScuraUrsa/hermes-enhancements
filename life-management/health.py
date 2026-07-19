#!/usr/bin/env python3
"""
Health & Wellness Module — Life Management System
==================================================
Rozszerza core engine o szczegółowe śledzenie zdrowia:

- PillScheduler   — konfigurowalny harmonogram pigułek (pora dnia, dni tygodnia)
- MealTracker     — logowanie posiłków (kalorie, makro, zdjęcia)
- WaterTracker    — daily goal + logowanie szklanek
- ExerciseTracker — typ, duration, intensity, calories burned
- SleepTracker    — bedtime, wake time, quality (1-10)

Wszystkie dane w SQLite: life_management.db (nowe tabele obok istniejących)
Importuje LifeDB z life_cli.py — nie duplikuje core engine.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from pathlib import Path

# Import core engine
from life_cli import LifeDB

# ── Constants ───────────────────────────────────────────────────────────────

MealType = Literal["breakfast", "lunch", "dinner", "snack", "other"]
ExerciseType = Literal[
    "running", "cycling", "swimming", "walking", "gym",
    "yoga", "pilates", "hiit", "sports", "stretching", "other",
]

# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class PillSchedule:
    """Konfiguracja harmonogramu pigułek."""
    id: Optional[int] = None
    pill_name: str = ""
    time_of_day: str = "09:00"          # HH:MM
    days_of_week: str = "[1,2,3,4,5,6,7]"  # JSON array, 1=Monday
    dosage: str = ""                     # np. "1 tabletka", "10mg"
    notes: str = ""
    active: bool = True
    created_at: str = ""


@dataclass
class PillLog:
    """Log zażycia pigułki."""
    id: Optional[int] = None
    schedule_id: int = 0
    timestamp: str = ""
    status: Literal["taken", "skipped", "missed"] = "taken"
    notes: str = ""
    created_at: str = ""


@dataclass
class Meal:
    """Zalogowany posiłek."""
    id: Optional[int] = None
    timestamp: str = ""
    meal_type: MealType = "other"
    name: str = ""
    calories: int = 0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    photo_path: str = ""
    notes: str = ""
    created_at: str = ""


@dataclass
class WaterLog:
    """Log wypitej wody."""
    id: Optional[int] = None
    timestamp: str = ""
    amount_ml: int = 250
    created_at: str = ""


@dataclass
class WaterGoal:
    """Dzienny cel nawodnienia."""
    id: Optional[int] = None
    daily_goal_ml: int = 2500
    effective_from: str = ""
    created_at: str = ""


@dataclass
class ExerciseLog:
    """Log ćwiczeń."""
    id: Optional[int] = None
    timestamp: str = ""
    exercise_type: ExerciseType = "other"
    duration_minutes: int = 0
    intensity: int = 5          # 1-10
    calories_burned: int = 0
    notes: str = ""
    created_at: str = ""


@dataclass
class SleepLog:
    """Log snu."""
    id: Optional[int] = None
    sleep_date: str = ""         # data, do której przypisany jest sen (data pójścia spać)
    bedtime: str = ""            # ISO datetime
    wake_time: str = ""          # ISO datetime
    duration_minutes: int = 0
    quality: int = 5             # 1-10
    notes: str = ""
    created_at: str = ""


# ── HealthDB (extends LifeDB with health tables) ─────────────────────────────

class HealthDB(LifeDB):
    """Rozszerza LifeDB o tabele zdrowotne.

    Obsługuje zmienną środowiskową HEALTH_DB_PATH do nadpisywania ścieżki bazy.
    """

    def __init__(self, db_path: str = ""):
        if not db_path:
            db_path = os.environ.get("HEALTH_DB_PATH", "")
        super().__init__(db_path)

    def _init_tables(self) -> None:
        """Tworzy tabele core + health."""
        super()._init_tables()
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS pill_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pill_name TEXT NOT NULL,
                    time_of_day TEXT NOT NULL DEFAULT '09:00',
                    days_of_week TEXT NOT NULL DEFAULT '[1,2,3,4,5,6,7]',
                    dosage TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS pill_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'taken',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (schedule_id) REFERENCES pill_schedule(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS meals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    meal_type TEXT NOT NULL DEFAULT 'other',
                    name TEXT DEFAULT '',
                    calories INTEGER NOT NULL DEFAULT 0,
                    protein_g REAL NOT NULL DEFAULT 0.0,
                    carbs_g REAL NOT NULL DEFAULT 0.0,
                    fat_g REAL NOT NULL DEFAULT 0.0,
                    photo_path TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS water_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    amount_ml INTEGER NOT NULL DEFAULT 250,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS water_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    daily_goal_ml INTEGER NOT NULL DEFAULT 2500,
                    effective_from TEXT NOT NULL DEFAULT (date('now')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS exercise_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    exercise_type TEXT NOT NULL DEFAULT 'other',
                    duration_minutes INTEGER NOT NULL DEFAULT 0,
                    intensity INTEGER NOT NULL DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
                    calories_burned INTEGER NOT NULL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS sleep_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sleep_date TEXT NOT NULL,
                    bedtime TEXT NOT NULL,
                    wake_time TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL DEFAULT 0,
                    quality INTEGER NOT NULL DEFAULT 5 CHECK(quality BETWEEN 1 AND 10),
                    notes TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE INDEX IF NOT EXISTS idx_pill_schedule_active ON pill_schedule(active);
                CREATE INDEX IF NOT EXISTS idx_pill_log_timestamp ON pill_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_pill_log_schedule ON pill_log(schedule_id);
                CREATE INDEX IF NOT EXISTS idx_meals_timestamp ON meals(timestamp);
                CREATE INDEX IF NOT EXISTS idx_meals_type ON meals(meal_type);
                CREATE INDEX IF NOT EXISTS idx_water_log_timestamp ON water_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_exercise_log_timestamp ON exercise_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_exercise_log_type ON exercise_log(exercise_type);
                CREATE INDEX IF NOT EXISTS idx_sleep_log_date ON sleep_log(sleep_date);
            """)


# ── Pill Scheduler ───────────────────────────────────────────────────────────

class PillScheduler:
    """Zarządza harmonogramem pigułek i logowaniem zażyć."""

    def __init__(self, db: HealthDB):
        self.db = db

    def add_schedule(
        self,
        pill_name: str,
        time_of_day: str = "09:00",
        days_of_week: Optional[list[int]] = None,
        dosage: str = "",
        notes: str = "",
    ) -> PillSchedule:
        """Dodaj nowy harmonogram pigułek.

        Args:
            pill_name: Nazwa leku/suplementu
            time_of_day: Godzina w formacie HH:MM
            days_of_week: Lista dni tygodnia (1=poniedziałek, 7=niedziela).
                          None = codziennie.
            dosage: Dawkowanie (np. "1 tabletka", "10mg")
            notes: Dodatkowe notatki
        """
        if days_of_week is None:
            days_of_week = [1, 2, 3, 4, 5, 6, 7]

        now = datetime.now().isoformat()
        schedule_id = self.db.insert("pill_schedule", {
            "pill_name": pill_name,
            "time_of_day": time_of_day,
            "days_of_week": json.dumps(days_of_week),
            "dosage": dosage,
            "notes": notes,
            "active": 1,
            "created_at": now,
        })
        return self.get_schedule(schedule_id)  # type: ignore[return-value]

    def get_schedule(self, schedule_id: int) -> Optional[PillSchedule]:
        """Pobierz harmonogram po ID."""
        row = self.db.execute_one(
            "SELECT * FROM pill_schedule WHERE id = ?", (schedule_id,)
        )
        return PillSchedule(**row) if row else None

    def get_all_schedules(self, active_only: bool = True) -> list[PillSchedule]:
        """Pobierz wszystkie harmonogramy."""
        if active_only:
            rows = self.db.execute(
                "SELECT * FROM pill_schedule WHERE active = 1 ORDER BY time_of_day"
            )
        else:
            rows = self.db.execute(
                "SELECT * FROM pill_schedule ORDER BY time_of_day"
            )
        return [PillSchedule(**r) for r in rows]

    def update_schedule(self, schedule_id: int, **kwargs) -> Optional[PillSchedule]:
        """Zaktualizuj harmonogram."""
        if "days_of_week" in kwargs and isinstance(kwargs["days_of_week"], list):
            kwargs["days_of_week"] = json.dumps(kwargs["days_of_week"])
        self.db.update("pill_schedule", kwargs, "id = ?", (schedule_id,))
        return self.get_schedule(schedule_id)

    def deactivate_schedule(self, schedule_id: int) -> None:
        """Dezaktywuj harmonogram (zamiast usuwać)."""
        self.db.update("pill_schedule", {"active": 0}, "id = ?", (schedule_id,))

    def delete_schedule(self, schedule_id: int) -> None:
        """Usuń harmonogram (kaskadowo usuwa logi)."""
        self.db.delete("pill_schedule", "id = ?", (schedule_id,))

    def log_pill(
        self,
        schedule_id: int,
        status: Literal["taken", "skipped", "missed"] = "taken",
        notes: str = "",
    ) -> PillLog:
        """Zaloguj zażycie/pominięcie pigułki."""
        now = datetime.now().isoformat()
        log_id = self.db.insert("pill_log", {
            "schedule_id": schedule_id,
            "timestamp": now,
            "status": status,
            "notes": notes,
            "created_at": now,
        })
        return PillLog(
            id=log_id,
            schedule_id=schedule_id,
            timestamp=now,
            status=status,
            notes=notes,
            created_at=now,
        )

    def get_logs(
        self,
        schedule_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Pobierz logi pigułek z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if schedule_id is not None:
            conditions.append("pl.schedule_id = ?")
            params.append(schedule_id)
        if start_date:
            conditions.append("pl.timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("pl.timestamp <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"""SELECT pl.*, ps.pill_name, ps.time_of_day, ps.dosage
                FROM pill_log pl
                JOIN pill_schedule ps ON pl.schedule_id = ps.id
                WHERE {where}
                ORDER BY pl.timestamp DESC""",
            tuple(params),
        )

    def get_today_pills(self) -> list[dict]:
        """Pobierz dzisiejsze logi pigułek."""
        today = date.today().isoformat()
        return self.get_logs(start_date=today)

    def get_due_pills(self) -> list[PillSchedule]:
        """Zwróć pigułki, które powinny być zażyte o tej porze (do przypomnień).

        Sprawdza aktualną godzinę vs time_of_day i czy dzisiejszy dzień
        jest w days_of_week.
        """
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_weekday = now.isoweekday()  # 1=Monday

        schedules = self.get_all_schedules(active_only=True)
        due = []
        for s in schedules:
            try:
                days = json.loads(s.days_of_week)
            except (json.JSONDecodeError, TypeError):
                days = [1, 2, 3, 4, 5, 6, 7]

            if current_weekday not in days:
                continue

            # Sprawdź czy aktualna godzina jest w oknie ±30 min od time_of_day
            try:
                h, m = map(int, s.time_of_day.split(":"))
                scheduled_minutes = h * 60 + m
                current_minutes = now.hour * 60 + now.minute
                if abs(current_minutes - scheduled_minutes) <= 30:
                    # Sprawdź czy już dziś zalogowano
                    today = date.today().isoformat()
                    existing = self.db.execute_one(
                        """SELECT id FROM pill_log
                           WHERE schedule_id = ? AND date(timestamp) = ? AND status = 'taken'""",
                        (s.id, today),
                    )
                    if not existing:
                        due.append(s)
            except (ValueError, TypeError):
                continue

        return due

    def get_adherence(
        self, schedule_id: int, days: int = 7
    ) -> dict:
        """Policz adherence (procent zażytych dawek) dla harmonogramu."""
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        schedule = self.get_schedule(schedule_id)
        if not schedule:
            return {"schedule_id": schedule_id, "adherence_pct": 0, "error": "not found"}

        try:
            days_of_week = json.loads(schedule.days_of_week)
        except (json.JSONDecodeError, TypeError):
            days_of_week = [1, 2, 3, 4, 5, 6, 7]

        # Policz ile dni w okresie powinno mieć dawkę
        current = date.today()
        expected_doses = 0
        for i in range(days):
            d = current - timedelta(days=i)
            if d.isoweekday() in days_of_week:
                expected_doses += 1

        if expected_doses == 0:
            return {"schedule_id": schedule_id, "adherence_pct": 100.0, "expected": 0, "taken": 0}

        # Policz ile faktycznie zażyto
        rows = self.db.execute(
            """SELECT COUNT(*) as cnt FROM pill_log
               WHERE schedule_id = ? AND status = 'taken' AND date(timestamp) >= ?""",
            (schedule_id, start),
        )
        taken = rows[0]["cnt"] if rows else 0

        return {
            "schedule_id": schedule_id,
            "pill_name": schedule.pill_name,
            "adherence_pct": round(min(100, taken / expected_doses * 100), 1),
            "expected": expected_doses,
            "taken": taken,
            "days": days,
        }


# ── Meal Tracker ─────────────────────────────────────────────────────────────

class MealTracker:
    """Logowanie posiłków z kaloriami, makro i zdjęciami."""

    def __init__(self, db: HealthDB):
        self.db = db

    def log_meal(
        self,
        meal_type: MealType = "other",
        name: str = "",
        calories: int = 0,
        protein_g: float = 0.0,
        carbs_g: float = 0.0,
        fat_g: float = 0.0,
        photo_path: str = "",
        notes: str = "",
        timestamp: Optional[str] = None,
    ) -> Meal:
        """Zaloguj posiłek.

        Args:
            meal_type: Typ posiłku (breakfast, lunch, dinner, snack, other)
            name: Nazwa posiłku
            calories: Kalorie (kcal)
            protein_g: Białko w gramach
            carbs_g: Węglowodany w gramach
            fat_g: Tłuszcz w gramach
            photo_path: Ścieżka do zdjęcia (opcjonalnie)
            notes: Notatki
            timestamp: ISO datetime (domyślnie: teraz)
        """
        now = datetime.now().isoformat()
        ts = timestamp or now

        meal_id = self.db.insert("meals", {
            "timestamp": ts,
            "meal_type": meal_type,
            "name": name,
            "calories": calories,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "photo_path": photo_path,
            "notes": notes,
            "created_at": now,
        })
        return Meal(
            id=meal_id,
            timestamp=ts,
            meal_type=meal_type,
            name=name,
            calories=calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            photo_path=photo_path,
            notes=notes,
            created_at=now,
        )

    def get_meals(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        meal_type: Optional[MealType] = None,
    ) -> list[dict]:
        """Pobierz posiłki z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)
        if meal_type:
            conditions.append("meal_type = ?")
            params.append(meal_type)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM meals WHERE {where} ORDER BY timestamp DESC",
            tuple(params),
        )

    def get_today_meals(self) -> list[dict]:
        """Pobierz dzisiejsze posiłki."""
        today = date.today().isoformat()
        return self.get_meals(start_date=today)

    def get_daily_summary(self, day: Optional[str] = None) -> dict:
        """Podsumowanie dnia: kalorie, makro, liczba posiłków.

        Args:
            day: Data w formacie YYYY-MM-DD (domyślnie: dziś)
        """
        if day is None:
            day = date.today().isoformat()

        rows = self.db.execute(
            """SELECT
                   COUNT(*) as meal_count,
                   COALESCE(SUM(calories), 0) as total_calories,
                   COALESCE(SUM(protein_g), 0) as total_protein,
                   COALESCE(SUM(carbs_g), 0) as total_carbs,
                   COALESCE(SUM(fat_g), 0) as total_fat
               FROM meals
               WHERE date(timestamp) = ?""",
            (day,),
        )
        r = rows[0] if rows else {}
        return {
            "date": day,
            "meal_count": r.get("meal_count", 0),
            "total_calories": round(r.get("total_calories", 0)),
            "total_protein_g": round(r.get("total_protein", 0), 1),
            "total_carbs_g": round(r.get("total_carbs", 0), 1),
            "total_fat_g": round(r.get("total_fat", 0), 1),
        }

    def get_weekly_nutrition_report(self) -> dict:
        """Raport tygodniowy odżywiania."""
        week_ago = (date.today() - timedelta(days=6)).isoformat()

        rows = self.db.execute(
            """SELECT date(timestamp) as day,
                      COUNT(*) as meals,
                      SUM(calories) as calories,
                      SUM(protein_g) as protein,
                      SUM(carbs_g) as carbs,
                      SUM(fat_g) as fat
               FROM meals
               WHERE date(timestamp) >= ?
               GROUP BY day
               ORDER BY day""",
            (week_ago,),
        )

        daily = []
        total_cals = 0
        for r in rows:
            daily.append({
                "day": r["day"],
                "meals": r["meals"],
                "calories": round(r["calories"]),
                "protein_g": round(r["protein"], 1),
                "carbs_g": round(r["carbs"], 1),
                "fat_g": round(r["fat"], 1),
            })
            total_cals += r["calories"]

        days_with_data = len(daily) or 1
        return {
            "week_start": week_ago,
            "daily": daily,
            "avg_daily_calories": round(total_cals / days_with_data),
            "total_calories": round(total_cals),
        }

    def delete_meal(self, meal_id: int) -> None:
        """Usuń posiłek."""
        self.db.delete("meals", "id = ?", (meal_id,))


# ── Water Tracker ────────────────────────────────────────────────────────────

class WaterTracker:
    """Śledzenie nawodnienia — daily goal + logowanie szklanek."""

    def __init__(self, db: HealthDB):
        self.db = db

    def set_daily_goal(self, goal_ml: int) -> WaterGoal:
        """Ustaw dzienny cel nawodnienia (domyślnie 2500ml)."""
        today = date.today().isoformat()
        now = datetime.now().isoformat()

        # Dezaktywuj poprzednie cele na dziś
        self.db.update(
            "water_goals",
            {"effective_from": today},
            "effective_from = ?",
            (today,),
        )

        goal_id = self.db.insert("water_goals", {
            "daily_goal_ml": goal_ml,
            "effective_from": today,
            "created_at": now,
        })
        return WaterGoal(
            id=goal_id,
            daily_goal_ml=goal_ml,
            effective_from=today,
            created_at=now,
        )

    def get_daily_goal(self, day: Optional[str] = None) -> int:
        """Pobierz dzienny cel nawodnienia dla danego dnia."""
        if day is None:
            day = date.today().isoformat()

        row = self.db.execute_one(
            """SELECT daily_goal_ml FROM water_goals
               WHERE effective_from <= ?
               ORDER BY effective_from DESC, id DESC
               LIMIT 1""",
            (day,),
        )
        return row["daily_goal_ml"] if row else 2500

    def log_water(self, amount_ml: int = 250, timestamp: Optional[str] = None) -> WaterLog:
        """Zaloguj wypitą wodę.

        Args:
            amount_ml: Ilość w ml (domyślnie 250ml = standardowa szklanka)
            timestamp: ISO datetime (domyślnie: teraz)
        """
        now = datetime.now().isoformat()
        ts = timestamp or now

        log_id = self.db.insert("water_log", {
            "timestamp": ts,
            "amount_ml": amount_ml,
            "created_at": now,
        })
        return WaterLog(
            id=log_id,
            timestamp=ts,
            amount_ml=amount_ml,
            created_at=now,
        )

    def log_glass(self, timestamp: Optional[str] = None) -> WaterLog:
        """Szybkie logowanie szklanki wody (250ml)."""
        return self.log_water(amount_ml=250, timestamp=timestamp)

    def get_today_water(self) -> dict:
        """Dzisiejsze podsumowanie nawodnienia."""
        today = date.today().isoformat()
        goal = self.get_daily_goal(today)

        rows = self.db.execute(
            """SELECT COALESCE(SUM(amount_ml), 0) as total_ml,
                      COUNT(*) as glasses
               FROM water_log
               WHERE date(timestamp) = ?""",
            (today,),
        )
        r = rows[0] if rows else {}
        total = r.get("total_ml", 0)

        return {
            "date": today,
            "goal_ml": goal,
            "drank_ml": total,
            "remaining_ml": max(0, goal - total),
            "progress_pct": round(min(100, total / goal * 100), 1) if goal > 0 else 0,
            "glasses": r.get("glasses", 0),
        }

    def get_water_logs(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> list[dict]:
        """Pobierz logi wody z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM water_log WHERE {where} ORDER BY timestamp DESC",
            tuple(params),
        )

    def get_weekly_water_report(self) -> dict:
        """Raport tygodniowy nawodnienia."""
        week_ago = (date.today() - timedelta(days=6)).isoformat()

        rows = self.db.execute(
            """SELECT date(timestamp) as day,
                      SUM(amount_ml) as total_ml,
                      COUNT(*) as glasses
               FROM water_log
               WHERE date(timestamp) >= ?
               GROUP BY day
               ORDER BY day""",
            (week_ago,),
        )

        daily = []
        total_ml = 0
        for r in rows:
            goal = self.get_daily_goal(r["day"])
            daily.append({
                "day": r["day"],
                "total_ml": r["total_ml"],
                "goal_ml": goal,
                "progress_pct": round(min(100, r["total_ml"] / goal * 100), 1) if goal > 0 else 0,
                "glasses": r["glasses"],
            })
            total_ml += r["total_ml"]

        days_with_data = len(daily) or 1
        return {
            "week_start": week_ago,
            "daily": daily,
            "avg_daily_ml": round(total_ml / days_with_data),
            "total_ml": total_ml,
        }

    def delete_water_log(self, log_id: int) -> None:
        """Usuń log wody."""
        self.db.delete("water_log", "id = ?", (log_id,))


# ── Exercise Tracker ─────────────────────────────────────────────────────────

class ExerciseTracker:
    """Śledzenie ćwiczeń — typ, duration, intensity, calories burned."""

    def __init__(self, db: HealthDB):
        self.db = db

    def log_exercise(
        self,
        exercise_type: ExerciseType = "other",
        duration_minutes: int = 0,
        intensity: int = 5,
        calories_burned: int = 0,
        notes: str = "",
        timestamp: Optional[str] = None,
    ) -> ExerciseLog:
        """Zaloguj ćwiczenie.

        Args:
            exercise_type: Typ ćwiczenia
            duration_minutes: Czas trwania w minutach
            intensity: Intensywność 1-10
            calories_burned: Spalone kalorie (szacunkowo)
            notes: Notatki
            timestamp: ISO datetime (domyślnie: teraz)
        """
        now = datetime.now().isoformat()
        ts = timestamp or now

        log_id = self.db.insert("exercise_log", {
            "timestamp": ts,
            "exercise_type": exercise_type,
            "duration_minutes": duration_minutes,
            "intensity": intensity,
            "calories_burned": calories_burned,
            "notes": notes,
            "created_at": now,
        })
        return ExerciseLog(
            id=log_id,
            timestamp=ts,
            exercise_type=exercise_type,
            duration_minutes=duration_minutes,
            intensity=intensity,
            calories_burned=calories_burned,
            notes=notes,
            created_at=now,
        )

    def get_exercises(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        exercise_type: Optional[ExerciseType] = None,
    ) -> list[dict]:
        """Pobierz ćwiczenia z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)
        if exercise_type:
            conditions.append("exercise_type = ?")
            params.append(exercise_type)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM exercise_log WHERE {where} ORDER BY timestamp DESC",
            tuple(params),
        )

    def get_today_exercises(self) -> list[dict]:
        """Pobierz dzisiejsze ćwiczenia."""
        today = date.today().isoformat()
        return self.get_exercises(start_date=today)

    def get_daily_summary(self, day: Optional[str] = None) -> dict:
        """Podsumowanie ćwiczeń w danym dniu."""
        if day is None:
            day = date.today().isoformat()

        rows = self.db.execute(
            """SELECT COUNT(*) as sessions,
                      COALESCE(SUM(duration_minutes), 0) as total_minutes,
                      COALESCE(SUM(calories_burned), 0) as total_calories,
                      COALESCE(AVG(intensity), 0) as avg_intensity
               FROM exercise_log
               WHERE date(timestamp) = ?""",
            (day,),
        )
        r = rows[0] if rows else {}
        return {
            "date": day,
            "sessions": r.get("sessions", 0),
            "total_minutes": r.get("total_minutes", 0),
            "total_calories_burned": r.get("total_calories", 0),
            "avg_intensity": round(r.get("avg_intensity", 0), 1),
        }

    def get_weekly_exercise_report(self) -> dict:
        """Raport tygodniowy ćwiczeń."""
        week_ago = (date.today() - timedelta(days=6)).isoformat()

        rows = self.db.execute(
            """SELECT date(timestamp) as day,
                      COUNT(*) as sessions,
                      SUM(duration_minutes) as minutes,
                      SUM(calories_burned) as calories,
                      AVG(intensity) as avg_intensity
               FROM exercise_log
               WHERE date(timestamp) >= ?
               GROUP BY day
               ORDER BY day""",
            (week_ago,),
        )

        daily = []
        total_minutes = 0
        total_cals = 0
        for r in rows:
            daily.append({
                "day": r["day"],
                "sessions": r["sessions"],
                "minutes": r["minutes"],
                "calories": r["calories"],
                "avg_intensity": round(r["avg_intensity"], 1),
            })
            total_minutes += r["minutes"]
            total_cals += r["calories"]

        days_with_data = len(daily) or 1
        return {
            "week_start": week_ago,
            "daily": daily,
            "total_minutes": total_minutes,
            "total_calories_burned": total_cals,
            "avg_daily_minutes": round(total_minutes / days_with_data),
            "active_days": len([d for d in daily if d["minutes"] > 0]),
        }

    def get_exercise_streak(self) -> int:
        """Policz dni z rzędu z ćwiczeniami."""
        rows = self.db.execute(
            "SELECT DISTINCT date(timestamp) as d FROM exercise_log ORDER BY d DESC"
        )
        dates = [r["d"] for r in rows]
        if not dates:
            return 0

        streak = 0
        today = date.today()
        expected = today

        for d_str in dates:
            d = date.fromisoformat(d_str)
            if d == expected:
                streak += 1
                expected = d - timedelta(days=1)
            elif d < expected:
                break

        return streak

    def delete_exercise(self, log_id: int) -> None:
        """Usuń log ćwiczenia."""
        self.db.delete("exercise_log", "id = ?", (log_id,))


# ── Sleep Tracker ────────────────────────────────────────────────────────────

class SleepTracker:
    """Śledzenie snu — bedtime, wake time, quality."""

    def __init__(self, db: HealthDB):
        self.db = db

    def log_sleep(
        self,
        bedtime: str,
        wake_time: str,
        quality: int = 5,
        notes: str = "",
        sleep_date: Optional[str] = None,
    ) -> SleepLog:
        """Zaloguj sen.

        Args:
            bedtime: ISO datetime pójścia spać
            wake_time: ISO datetime pobudki
            quality: Jakość snu 1-10
            notes: Notatki (np. sny, powód złego snu)
            sleep_date: Data snu (domyślnie: data z bedtime)
        """
        now = datetime.now().isoformat()

        # Oblicz duration
        try:
            bt = datetime.fromisoformat(bedtime)
            wt = datetime.fromisoformat(wake_time)
            duration = int((wt - bt).total_seconds() / 60)
            if duration < 0:
                # Zakładamy, że wake_time jest następnego dnia
                duration += 24 * 60
        except (ValueError, TypeError):
            duration = 0

        if sleep_date is None:
            sleep_date = bedtime[:10]  # YYYY-MM-DD

        log_id = self.db.insert("sleep_log", {
            "sleep_date": sleep_date,
            "bedtime": bedtime,
            "wake_time": wake_time,
            "duration_minutes": duration,
            "quality": quality,
            "notes": notes,
            "created_at": now,
        })
        return SleepLog(
            id=log_id,
            sleep_date=sleep_date,
            bedtime=bedtime,
            wake_time=wake_time,
            duration_minutes=duration,
            quality=quality,
            notes=notes,
            created_at=now,
        )

    def get_sleep_logs(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Pobierz logi snu z filtrami."""
        conditions = ["1=1"]
        params: list = []

        if start_date:
            conditions.append("sleep_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("sleep_date <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        return self.db.execute(
            f"SELECT * FROM sleep_log WHERE {where} ORDER BY sleep_date DESC",
            tuple(params),
        )

    def get_last_sleep(self) -> Optional[dict]:
        """Pobierz ostatni zarejestrowany sen."""
        row = self.db.execute_one(
            "SELECT * FROM sleep_log ORDER BY sleep_date DESC, id DESC LIMIT 1"
        )
        return dict(row) if row else None

    def get_weekly_sleep_report(self) -> dict:
        """Raport tygodniowy snu."""
        week_ago = (date.today() - timedelta(days=6)).isoformat()

        rows = self.db.execute(
            """SELECT sleep_date,
                      duration_minutes,
                      quality,
                      bedtime,
                      wake_time
               FROM sleep_log
               WHERE sleep_date >= ?
               ORDER BY sleep_date""",
            (week_ago,),
        )

        logs = []
        total_duration = 0
        total_quality = 0
        for r in rows:
            logs.append({
                "sleep_date": r["sleep_date"],
                "duration_minutes": r["duration_minutes"],
                "duration_hours": round(r["duration_minutes"] / 60, 1),
                "quality": r["quality"],
                "bedtime": r["bedtime"],
                "wake_time": r["wake_time"],
            })
            total_duration += r["duration_minutes"]
            total_quality += r["quality"]

        count = len(logs) or 1
        return {
            "week_start": week_ago,
            "logs": logs,
            "nights_tracked": len(logs),
            "avg_duration_hours": round(total_duration / count / 60, 1),
            "avg_quality": round(total_quality / count, 1),
            "total_sleep_hours": round(total_duration / 60, 1),
        }

    def get_sleep_debt(self) -> dict:
        """Oblicz dług senny — różnica między średnią a celem 8h."""
        report = self.get_weekly_sleep_report()
        target_minutes = 8 * 60  # 480 min
        avg_minutes = report["avg_duration_hours"] * 60

        return {
            "target_hours": 8.0,
            "avg_hours_last_7d": report["avg_duration_hours"],
            "debt_hours": round(max(0, target_minutes - avg_minutes) / 60, 1),
            "nights_tracked": report["nights_tracked"],
        }

    def delete_sleep_log(self, log_id: int) -> None:
        """Usuń log snu."""
        self.db.delete("sleep_log", "id = ?", (log_id,))


# ── Health Report Generator ──────────────────────────────────────────────────

class HealthReport:
    """Generuje raporty zdrowotne łącząc wszystkie trackery."""

    def __init__(self, db: HealthDB):
        self.db = db
        self.pills = PillScheduler(db)
        self.meals = MealTracker(db)
        self.water = WaterTracker(db)
        self.exercise = ExerciseTracker(db)
        self.sleep = SleepTracker(db)

    def daily_health_brief(self) -> str:
        """Codzienny raport zdrowotny."""
        today = date.today()
        water_summary = self.water.get_today_water()
        meal_summary = self.meals.get_daily_summary()
        exercise_summary = self.exercise.get_daily_summary()
        last_sleep = self.sleep.get_last_sleep()
        due_pills = self.pills.get_due_pills()

        lines = [
            f"💚 HEALTH BRIEF — {today.strftime('%A, %d.%m.%Y')}",
            "=" * 40,
            "",
        ]

        # Pigułki
        lines.append("💊 PIGUŁKI:")
        if due_pills:
            for p in due_pills:
                lines.append(f"   ⚠️ {p.pill_name} — {p.time_of_day} ({p.dosage})")
        else:
            lines.append("   ✅ Wszystko zażyte lub brak na tę porę")

        # Posiłki
        lines.extend([
            "",
            "🍽️ POSIŁKI:",
            f"   Kalorie: {meal_summary['total_calories']} kcal",
            f"   Białko: {meal_summary['total_protein_g']}g | Węgle: {meal_summary['total_carbs_g']}g | Tłuszcz: {meal_summary['total_fat_g']}g",
            f"   Liczba posiłków: {meal_summary['meal_count']}",
        ])

        # Woda
        lines.extend([
            "",
            "💧 WODA:",
            f"   Wypite: {water_summary['drank_ml']}ml / {water_summary['goal_ml']}ml ({water_summary['progress_pct']}%)",
            f"   Szklanki: {water_summary['glasses']}",
            f"   Pozostało: {water_summary['remaining_ml']}ml",
        ])

        # Ćwiczenia
        lines.extend([
            "",
            "🏃 ĆWICZENIA:",
            f"   Sesje: {exercise_summary['sessions']}",
            f"   Czas: {exercise_summary['total_minutes']} min",
            f"   Spalone: {exercise_summary['total_calories_burned']} kcal",
            f"   Śr. intensywność: {exercise_summary['avg_intensity']}/10",
        ])

        # Sen
        lines.append("")
        lines.append("😴 SEN:")
        if last_sleep:
            lines.append(f"   Ostatni: {last_sleep['duration_minutes']//60}h {last_sleep['duration_minutes']%60}min")
            lines.append(f"   Jakość: {last_sleep['quality']}/10")
            lines.append(f"   Bedtime: {last_sleep['bedtime'][:16]}")
            lines.append(f"   Wake: {last_sleep['wake_time'][:16]}")
        else:
            lines.append("   Brak danych")

        return "\n".join(lines)

    def weekly_health_report(self) -> str:
        """Tygodniowy raport zdrowotny."""
        water_report = self.water.get_weekly_water_report()
        meal_report = self.meals.get_weekly_nutrition_report()
        exercise_report = self.exercise.get_weekly_exercise_report()
        sleep_report = self.sleep.get_weekly_sleep_report()
        sleep_debt = self.sleep.get_sleep_debt()

        lines = [
            "📊 HEALTH WEEKLY REPORT",
            "=" * 40,
            "",
            "💧 WODA:",
            f"   Średnio dziennie: {water_report['avg_daily_ml']}ml",
            f"   Łącznie: {water_report['total_ml']}ml",
            "",
            "🍽️ ODŻYWIANIE:",
            f"   Śr. kalorie/dzień: {meal_report['avg_daily_calories']} kcal",
            f"   Łącznie kalorii: {meal_report['total_calories']} kcal",
            "",
            "🏃 ĆWICZENIA:",
            f"   Aktywne dni: {exercise_report['active_days']}/7",
            f"   Łącznie minut: {exercise_report['total_minutes']}",
            f"   Śr. dziennie: {exercise_report['avg_daily_minutes']} min",
            f"   Spalone kalorie: {exercise_report['total_calories_burned']}",
            "",
            "😴 SEN:",
            f"   Śr. długość: {sleep_report['avg_duration_hours']}h",
            f"   Śr. jakość: {sleep_report['avg_quality']}/10",
            f"   Dług senny: {sleep_debt['debt_hours']}h (cel: 8h)",
            f"   Noce śledzone: {sleep_report['nights_tracked']}",
        ]

        return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI dla modułu Health & Wellness."""
    import sys

    db = HealthDB()
    pills = PillScheduler(db)
    meals = MealTracker(db)
    water = WaterTracker(db)
    exercise = ExerciseTracker(db)
    sleep = SleepTracker(db)
    report = HealthReport(db)

    if len(sys.argv) < 2:
        print("Health & Wellness — CLI")
        print()
        print("Komendy:")
        print("  ── Pigułki ──")
        print("  pill-schedule-add <nazwa> <HH:MM> [dawka]  — dodaj harmonogram")
        print("  pill-schedule-list                            — lista harmonogramów")
        print("  pill-schedule-deactivate <id>                 — dezaktywuj harmonogram")
        print("  pill-log <schedule_id> [taken|skipped]        — zaloguj zażycie")
        print("  pill-due                                      — pigułki do zażycia teraz")
        print("  pill-adherence <schedule_id> [dni]            — adherence %")
        print("  ── Posiłki ──")
        print("  meal-log <typ> <nazwa> <kcal> [B] [W] [T]    — zaloguj posiłek")
        print("  meal-today                                    — dzisiejsze posiłki")
        print("  meal-summary [data]                           — podsumowanie dnia")
        print("  ── Woda ──")
        print("  water-goal <ml>                               — ustaw dzienny cel")
        print("  water-log [ml]                                — zaloguj wodę (domyślnie 250ml)")
        print("  water-glass                                   — szybko: szklanka 250ml")
        print("  water-today                                   — dzisiejsze podsumowanie")
        print("  ── Ćwiczenia ──")
        print("  exercise-log <typ> <minuty> [intensywność] [kcal]  — zaloguj ćwiczenie")
        print("  exercise-today                                — dzisiejsze ćwiczenia")
        print("  exercise-streak                               — seria dni z ćwiczeniami")
        print("  ── Sen ──")
        print("  sleep-log <bedtime> <waketime> [quality]      — zaloguj sen (ISO format)")
        print("  sleep-last                                    — ostatni sen")
        print("  sleep-debt                                    — dług senny")
        print("  ── Raporty ──")
        print("  health-brief                                  — daily health brief")
        print("  health-weekly                                 — weekly health report")
        return

    cmd = sys.argv[1]

    # ── Pill commands ──
    if cmd == "pill-schedule-add" and len(sys.argv) >= 4:
        name = sys.argv[2]
        time_of_day = sys.argv[3]
        dosage = sys.argv[4] if len(sys.argv) >= 5 else ""
        s = pills.add_schedule(pill_name=name, time_of_day=time_of_day, dosage=dosage)
        print(f"💊 Dodano harmonogram: {s.pill_name} o {s.time_of_day} (ID: {s.id})")

    elif cmd == "pill-schedule-list":
        schedules = pills.get_all_schedules(active_only=False)
        for s in schedules:
            status = "✅" if s.active else "❌"
            print(f"  [{s.id}] {status} {s.pill_name} — {s.time_of_day} | {s.dosage}")

    elif cmd == "pill-schedule-deactivate" and len(sys.argv) >= 3:
        sid = int(sys.argv[2])
        pills.deactivate_schedule(sid)
        print(f"💊 Harmonogram {sid} dezaktywowany")

    elif cmd == "pill-log" and len(sys.argv) >= 3:
        sid = int(sys.argv[2])
        status = sys.argv[3] if len(sys.argv) >= 4 else "taken"
        log = pills.log_pill(schedule_id=sid, status=status)  # type: ignore[arg-type]
        print(f"💊 Zalogowano: {status} (ID: {log.id})")

    elif cmd == "pill-due":
        due = pills.get_due_pills()
        if due:
            for p in due:
                print(f"  ⚠️ {p.pill_name} — {p.time_of_day} ({p.dosage})")
        else:
            print("✅ Brak pigułek do zażycia w tej chwili")

    elif cmd == "pill-adherence" and len(sys.argv) >= 3:
        sid = int(sys.argv[2])
        days = int(sys.argv[3]) if len(sys.argv) >= 4 else 7
        adh = pills.get_adherence(sid, days)
        print(f"💊 {adh.get('pill_name', '?')}: {adh['adherence_pct']}% ({adh['taken']}/{adh['expected']} dawek w {days} dni)")

    # ── Meal commands ──
    elif cmd == "meal-log" and len(sys.argv) >= 5:
        meal_type = sys.argv[2]
        name = sys.argv[3]
        calories = int(sys.argv[4])
        protein = float(sys.argv[5]) if len(sys.argv) >= 6 else 0.0
        carbs = float(sys.argv[6]) if len(sys.argv) >= 7 else 0.0
        fat = float(sys.argv[7]) if len(sys.argv) >= 8 else 0.0
        m = meals.log_meal(
            meal_type=meal_type,  # type: ignore[arg-type]
            name=name,
            calories=calories,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
        )
        print(f"🍽️ Zalogowano: {m.name} ({m.calories} kcal) — ID: {m.id}")

    elif cmd == "meal-today":
        today_meals = meals.get_today_meals()
        for m in today_meals:
            print(f"  [{m['id']}] {m['meal_type']}: {m['name']} — {m['calories']} kcal | B:{m['protein_g']}g W:{m['carbs_g']}g T:{m['fat_g']}g")

    elif cmd == "meal-summary":
        day = sys.argv[2] if len(sys.argv) >= 3 else None
        summary = meals.get_daily_summary(day)
        print(f"🍽️ {summary['date']}: {summary['total_calories']} kcal | B:{summary['total_protein_g']}g W:{summary['total_carbs_g']}g T:{summary['total_fat_g']}g | {summary['meal_count']} posiłków")

    # ── Water commands ──
    elif cmd == "water-goal" and len(sys.argv) >= 3:
        goal_ml = int(sys.argv[2])
        g = water.set_daily_goal(goal_ml)
        print(f"💧 Cel dzienny: {g.daily_goal_ml}ml")

    elif cmd == "water-log":
        amount = int(sys.argv[2]) if len(sys.argv) >= 3 else 250
        w = water.log_water(amount_ml=amount)
        print(f"💧 Zalogowano: {w.amount_ml}ml (ID: {w.id})")

    elif cmd == "water-glass":
        w = water.log_glass()
        print(f"💧 Szklanka: {w.amount_ml}ml (ID: {w.id})")

    elif cmd == "water-today":
        summary = water.get_today_water()
        bar_len = 20
        filled = int(summary["progress_pct"] / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"💧 {summary['date']}: [{bar}] {summary['progress_pct']}%")
        print(f"   {summary['drank_ml']}ml / {summary['goal_ml']}ml | {summary['glasses']} szklanek | zostało: {summary['remaining_ml']}ml")

    # ── Exercise commands ──
    elif cmd == "exercise-log" and len(sys.argv) >= 4:
        ex_type = sys.argv[2]
        duration = int(sys.argv[3])
        intensity = int(sys.argv[4]) if len(sys.argv) >= 5 else 5
        calories = int(sys.argv[5]) if len(sys.argv) >= 6 else 0
        e = exercise.log_exercise(
            exercise_type=ex_type,  # type: ignore[arg-type]
            duration_minutes=duration,
            intensity=intensity,
            calories_burned=calories,
        )
        print(f"🏃 Zalogowano: {e.exercise_type} — {e.duration_minutes}min, intensywność {e.intensity}/10, {e.calories_burned} kcal (ID: {e.id})")

    elif cmd == "exercise-today":
        today_ex = exercise.get_today_exercises()
        for e in today_ex:
            print(f"  [{e['id']}] {e['exercise_type']}: {e['duration_minutes']}min | intensywność {e['intensity']}/10 | {e['calories_burned']} kcal")

    elif cmd == "exercise-streak":
        streak = exercise.get_exercise_streak()
        print(f"🔥 Seria ćwiczeń: {streak} dni")

    # ── Sleep commands ──
    elif cmd == "sleep-log" and len(sys.argv) >= 4:
        bedtime = sys.argv[2]
        wake_time = sys.argv[3]
        quality = int(sys.argv[4]) if len(sys.argv) >= 5 else 5
        s = sleep.log_sleep(bedtime=bedtime, wake_time=wake_time, quality=quality)
        print(f"😴 Zalogowano sen: {s.duration_minutes//60}h {s.duration_minutes%60}min | jakość {s.quality}/10 (ID: {s.id})")

    elif cmd == "sleep-last":
        last = sleep.get_last_sleep()
        if last:
            print(f"😴 Ostatni sen: {last['sleep_date']}")
            print(f"   Bedtime: {last['bedtime'][:16]}")
            print(f"   Wake: {last['wake_time'][:16]}")
            print(f"   Długość: {last['duration_minutes']//60}h {last['duration_minutes']%60}min")
            print(f"   Jakość: {last['quality']}/10")
        else:
            print("😴 Brak danych o śnie")

    elif cmd == "sleep-debt":
        debt = sleep.get_sleep_debt()
        print(f"😴 Dług senny: {debt['debt_hours']}h")
        print(f"   Średnia (7d): {debt['avg_hours_last_7d']}h | Cel: {debt['target_hours']}h")
        print(f"   Noce śledzone: {debt['nights_tracked']}")

    # ── Report commands ──
    elif cmd == "health-brief":
        print(report.daily_health_brief())

    elif cmd == "health-weekly":
        print(report.weekly_health_report())

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
