#!/usr/bin/env python3
"""
Testy dla health.py — Health & Wellness Module.
"""

import unittest
import os
import sys
import json
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from health import (
    HealthDB,
    PillScheduler, PillSchedule, PillLog,
    MealTracker, Meal,
    WaterTracker, WaterLog, WaterGoal,
    ExerciseTracker, ExerciseLog,
    SleepTracker, SleepLog,
    HealthReport,
)


class TestHealthDB(unittest.TestCase):
    """Testy bazy danych HealthDB."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)

    def test_core_tables_exist(self):
        """Core tabele powinny istnieć (dziedziczone z LifeDB)."""
        tables = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t["name"] for t in tables]
        for expected in ["people", "time_blocks", "events", "habit_log"]:
            self.assertIn(expected, table_names)

    def test_health_tables_exist(self):
        """Nowe tabele health powinny istnieć."""
        tables = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t["name"] for t in tables]
        for expected in [
            "pill_schedule", "pill_log", "meals",
            "water_log", "water_goals", "exercise_log", "sleep_log",
        ]:
            self.assertIn(expected, table_names)


# ── Pill Scheduler Tests ─────────────────────────────────────────────────────

class TestPillScheduler(unittest.TestCase):
    """Testy harmonogramu pigułek."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)
        cls.ps = PillScheduler(cls.db)

    def test_add_schedule(self):
        """Dodanie harmonogramu pigułek."""
        s = self.ps.add_schedule(
            pill_name="Witamina D",
            time_of_day="09:00",
            dosage="2000 IU",
        )
        self.assertIsNotNone(s.id)
        self.assertEqual(s.pill_name, "Witamina D")
        self.assertEqual(s.time_of_day, "09:00")
        self.assertEqual(s.dosage, "2000 IU")
        self.assertTrue(s.active)

    def test_add_schedule_with_days(self):
        """Dodanie harmonogramu z wybranymi dniami."""
        s = self.ps.add_schedule(
            pill_name="Magnez",
            time_of_day="21:00",
            days_of_week=[1, 3, 5],  # pon, śr, pt
            dosage="400mg",
        )
        self.assertIsNotNone(s.id)
        days = json.loads(s.days_of_week)
        self.assertEqual(days, [1, 3, 5])

    def test_get_schedule(self):
        """Pobranie harmonogramu po ID."""
        s = self.ps.add_schedule("Test", "08:00")
        fetched = self.ps.get_schedule(s.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.pill_name, "Test")

    def test_get_all_schedules(self):
        """Pobranie wszystkich harmonogramów."""
        self.ps.add_schedule("A", "08:00")
        self.ps.add_schedule("B", "12:00")
        self.ps.add_schedule("C", "20:00")

        all_s = self.ps.get_all_schedules(active_only=True)
        self.assertGreaterEqual(len(all_s), 3)

    def test_deactivate_schedule(self):
        """Dezaktywacja harmonogramu."""
        s = self.ps.add_schedule("Do Deactivate", "10:00")
        self.ps.deactivate_schedule(s.id)

        fetched = self.ps.get_schedule(s.id)
        self.assertFalse(fetched.active)

        # Nie powinien być w active_only
        active = self.ps.get_all_schedules(active_only=True)
        active_ids = [a.id for a in active]
        self.assertNotIn(s.id, active_ids)

    def test_delete_schedule(self):
        """Usunięcie harmonogramu."""
        s = self.ps.add_schedule("Do Delete", "11:00")
        self.ps.delete_schedule(s.id)
        self.assertIsNone(self.ps.get_schedule(s.id))

    def test_log_pill_taken(self):
        """Logowanie zażycia pigułki."""
        s = self.ps.add_schedule("Test Pill", "09:00")
        log = self.ps.log_pill(s.id, status="taken")
        self.assertIsNotNone(log.id)
        self.assertEqual(log.schedule_id, s.id)
        self.assertEqual(log.status, "taken")

    def test_log_pill_skipped(self):
        """Logowanie pominięcia pigułki."""
        s = self.ps.add_schedule("Test Pill 2", "10:00")
        log = self.ps.log_pill(s.id, status="skipped", notes="Zapomniałem")
        self.assertEqual(log.status, "skipped")
        self.assertEqual(log.notes, "Zapomniałem")

    def test_get_logs(self):
        """Pobieranie logów pigułek."""
        s = self.ps.add_schedule("Log Test", "08:00")
        self.ps.log_pill(s.id, status="taken")
        self.ps.log_pill(s.id, status="taken")

        logs = self.ps.get_logs(schedule_id=s.id)
        self.assertEqual(len(logs), 2)

    def test_get_today_pills(self):
        """Dzisiejsze logi pigułek."""
        s = self.ps.add_schedule("Today Pill", "09:00")
        self.ps.log_pill(s.id, status="taken")

        today_logs = self.ps.get_today_pills()
        self.assertGreaterEqual(len(today_logs), 1)

    def test_get_due_pills(self):
        """Pigułki do zażycia teraz (w oknie ±30min)."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_weekday = now.isoweekday()

        s = self.ps.add_schedule(
            "Due Pill",
            time_of_day=current_time,
            days_of_week=[current_weekday],
        )
        due = self.ps.get_due_pills()
        # Powinna być w due (chyba że już zalogowana)
        due_ids = [d.id for d in due]
        self.assertIn(s.id, due_ids)

    def test_get_due_pills_already_logged(self):
        """Pigułka już zalogowana nie powinna być w due."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_weekday = now.isoweekday()

        s = self.ps.add_schedule(
            "Already Taken",
            time_of_day=current_time,
            days_of_week=[current_weekday],
        )
        self.ps.log_pill(s.id, status="taken")

        due = self.ps.get_due_pills()
        due_ids = [d.id for d in due]
        self.assertNotIn(s.id, due_ids)

    def test_adherence(self):
        """Obliczanie adherence."""
        s = self.ps.add_schedule(
            "Adherence Test",
            time_of_day="09:00",
            days_of_week=[1, 2, 3, 4, 5, 6, 7],  # codziennie
        )
        # Zaloguj na dziś
        self.ps.log_pill(s.id, status="taken")

        adh = self.ps.get_adherence(s.id, days=7)
        self.assertIn("adherence_pct", adh)
        self.assertGreaterEqual(adh["adherence_pct"], 0)
        self.assertEqual(adh["expected"], 7)

    def test_update_schedule(self):
        """Aktualizacja harmonogramu."""
        s = self.ps.add_schedule("Update Me", "08:00")
        updated = self.ps.update_schedule(
            s.id, time_of_day="10:00", dosage="2 tabletki"
        )
        self.assertEqual(updated.time_of_day, "10:00")
        self.assertEqual(updated.dosage, "2 tabletki")

    def test_update_schedule_days(self):
        """Aktualizacja dni tygodnia."""
        s = self.ps.add_schedule("Days Update", "08:00")
        updated = self.ps.update_schedule(
            s.id, days_of_week=[1, 5]
        )
        days = json.loads(updated.days_of_week)
        self.assertEqual(days, [1, 5])


# ── Meal Tracker Tests ───────────────────────────────────────────────────────

class TestMealTracker(unittest.TestCase):
    """Testy trackera posiłków."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)
        cls.mt = MealTracker(cls.db)

    def test_log_meal(self):
        """Logowanie posiłku."""
        m = self.mt.log_meal(
            meal_type="lunch",
            name="Kurczak z ryżem",
            calories=650,
            protein_g=45.0,
            carbs_g=60.0,
            fat_g=15.0,
        )
        self.assertIsNotNone(m.id)
        self.assertEqual(m.meal_type, "lunch")
        self.assertEqual(m.name, "Kurczak z ryżem")
        self.assertEqual(m.calories, 650)
        self.assertEqual(m.protein_g, 45.0)
        self.assertEqual(m.carbs_g, 60.0)
        self.assertEqual(m.fat_g, 15.0)

    def test_log_meal_minimal(self):
        """Minimalne logowanie posiłku."""
        m = self.mt.log_meal(meal_type="snack", name="Jabłko", calories=95)
        self.assertIsNotNone(m.id)
        self.assertEqual(m.calories, 95)
        self.assertEqual(m.protein_g, 0.0)

    def test_log_meal_with_photo(self):
        """Logowanie posiłku ze zdjęciem."""
        m = self.mt.log_meal(
            meal_type="dinner",
            name="Sałatka",
            calories=350,
            photo_path="/photos/salad.jpg",
        )
        self.assertEqual(m.photo_path, "/photos/salad.jpg")

    def test_get_meals(self):
        """Pobieranie posiłków."""
        self.mt.log_meal("breakfast", "Śniadanie", 400)
        self.mt.log_meal("lunch", "Obiad", 700)

        meals = self.mt.get_meals()
        self.assertGreaterEqual(len(meals), 2)

    def test_get_meals_by_type(self):
        """Filtrowanie posiłków po typie."""
        self.mt.log_meal("breakfast", "Tosty", 300)
        self.mt.log_meal("lunch", "Zupa", 250)

        breakfasts = self.mt.get_meals(meal_type="breakfast")
        for m in breakfasts:
            self.assertEqual(m["meal_type"], "breakfast")

    def test_get_today_meals(self):
        """Dzisiejsze posiłki."""
        self.mt.log_meal("snack", "Orzechy", 180)
        today = self.mt.get_today_meals()
        self.assertGreaterEqual(len(today), 1)

    def test_daily_summary(self):
        """Podsumowanie dnia."""
        self.mt.log_meal("breakfast", "Jajecznica", 350, protein_g=25, carbs_g=5, fat_g=25)
        self.mt.log_meal("lunch", "Obiad", 700, protein_g=40, carbs_g=70, fat_g=20)

        summary = self.mt.get_daily_summary()
        self.assertIn("total_calories", summary)
        self.assertIn("total_protein_g", summary)
        self.assertIn("total_carbs_g", summary)
        self.assertIn("total_fat_g", summary)
        self.assertIn("meal_count", summary)
        self.assertGreater(summary["total_calories"], 0)
        self.assertGreater(summary["meal_count"], 0)

    def test_weekly_nutrition_report(self):
        """Raport tygodniowy."""
        self.mt.log_meal("lunch", "Test", 500, protein_g=30, carbs_g=50, fat_g=15)
        report = self.mt.get_weekly_nutrition_report()
        self.assertIn("avg_daily_calories", report)
        self.assertIn("daily", report)

    def test_delete_meal(self):
        """Usunięcie posiłku."""
        m = self.mt.log_meal("snack", "Do usunięcia", 100)
        self.mt.delete_meal(m.id)

        meals = self.mt.get_meals()
        meal_ids = [meal["id"] for meal in meals]
        self.assertNotIn(m.id, meal_ids)


# ── Water Tracker Tests ──────────────────────────────────────────────────────

class TestWaterTracker(unittest.TestCase):
    """Testy trackera wody."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)
        cls.wt = WaterTracker(cls.db)

    def test_default_goal(self):
        """Domyślny cel nawodnienia."""
        goal = self.wt.get_daily_goal()
        self.assertEqual(goal, 2500)

    def test_set_daily_goal(self):
        """Ustawienie dziennego celu."""
        g = self.wt.set_daily_goal(3000)
        self.assertEqual(g.daily_goal_ml, 3000)

        goal = self.wt.get_daily_goal()
        self.assertEqual(goal, 3000)

    def test_log_water(self):
        """Logowanie wody."""
        w = self.wt.log_water(amount_ml=500)
        self.assertIsNotNone(w.id)
        self.assertEqual(w.amount_ml, 500)

    def test_log_glass(self):
        """Szybkie logowanie szklanki."""
        w = self.wt.log_glass()
        self.assertEqual(w.amount_ml, 250)

    def test_get_today_water(self):
        """Dzisiejsze podsumowanie wody."""
        self.wt.set_daily_goal(2000)
        self.wt.log_water(250)
        self.wt.log_water(500)

        summary = self.wt.get_today_water()
        self.assertIn("goal_ml", summary)
        self.assertIn("drank_ml", summary)
        self.assertIn("progress_pct", summary)
        self.assertIn("remaining_ml", summary)
        self.assertIn("glasses", summary)
        self.assertEqual(summary["drank_ml"], 750)
        self.assertEqual(summary["goal_ml"], 2000)
        self.assertEqual(summary["remaining_ml"], 1250)
        self.assertEqual(summary["glasses"], 2)

    def test_progress_pct(self):
        """Procent postępu."""
        self.wt.set_daily_goal(1000)
        self.wt.log_water(500)

        summary = self.wt.get_today_water()
        self.assertEqual(summary["progress_pct"], 50.0)

    def test_get_water_logs(self):
        """Pobieranie logów wody."""
        self.wt.log_water(250)
        self.wt.log_water(500)

        logs = self.wt.get_water_logs()
        self.assertGreaterEqual(len(logs), 2)

    def test_weekly_water_report(self):
        """Raport tygodniowy wody."""
        self.wt.log_water(500)
        report = self.wt.get_weekly_water_report()
        self.assertIn("avg_daily_ml", report)
        self.assertIn("daily", report)

    def test_delete_water_log(self):
        """Usunięcie logu wody."""
        w = self.wt.log_water(100)
        self.wt.delete_water_log(w.id)

        logs = self.wt.get_water_logs()
        log_ids = [l["id"] for l in logs]
        self.assertNotIn(w.id, log_ids)


# ── Exercise Tracker Tests ───────────────────────────────────────────────────

class TestExerciseTracker(unittest.TestCase):
    """Testy trackera ćwiczeń."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)
        cls.et = ExerciseTracker(cls.db)

    def test_log_exercise(self):
        """Logowanie ćwiczenia."""
        e = self.et.log_exercise(
            exercise_type="running",
            duration_minutes=30,
            intensity=7,
            calories_burned=350,
            notes="Poranny bieg",
        )
        self.assertIsNotNone(e.id)
        self.assertEqual(e.exercise_type, "running")
        self.assertEqual(e.duration_minutes, 30)
        self.assertEqual(e.intensity, 7)
        self.assertEqual(e.calories_burned, 350)
        self.assertEqual(e.notes, "Poranny bieg")

    def test_log_exercise_minimal(self):
        """Minimalne logowanie ćwiczenia."""
        e = self.et.log_exercise(exercise_type="walking", duration_minutes=45)
        self.assertIsNotNone(e.id)
        self.assertEqual(e.intensity, 5)  # default
        self.assertEqual(e.calories_burned, 0)  # default

    def test_get_exercises(self):
        """Pobieranie ćwiczeń."""
        self.et.log_exercise("running", 30)
        self.et.log_exercise("yoga", 60)

        exercises = self.et.get_exercises()
        self.assertGreaterEqual(len(exercises), 2)

    def test_get_exercises_by_type(self):
        """Filtrowanie ćwiczeń po typie."""
        self.et.log_exercise("swimming", 45)
        self.et.log_exercise("running", 20)

        runs = self.et.get_exercises(exercise_type="running")
        for e in runs:
            self.assertEqual(e["exercise_type"], "running")

    def test_get_today_exercises(self):
        """Dzisiejsze ćwiczenia."""
        self.et.log_exercise("gym", 60)
        today = self.et.get_today_exercises()
        self.assertGreaterEqual(len(today), 1)

    def test_daily_summary(self):
        """Podsumowanie dnia ćwiczeń."""
        self.et.log_exercise("running", 30, intensity=8, calories_burned=400)
        self.et.log_exercise("stretching", 15, intensity=3, calories_burned=50)

        summary = self.et.get_daily_summary()
        self.assertIn("sessions", summary)
        self.assertIn("total_minutes", summary)
        self.assertIn("total_calories_burned", summary)
        self.assertIn("avg_intensity", summary)
        self.assertGreaterEqual(summary["sessions"], 2)
        self.assertGreaterEqual(summary["total_minutes"], 45)
        self.assertGreaterEqual(summary["total_calories_burned"], 450)

    def test_weekly_exercise_report(self):
        """Raport tygodniowy ćwiczeń."""
        self.et.log_exercise("cycling", 60, calories_burned=500)
        report = self.et.get_weekly_exercise_report()
        self.assertIn("active_days", report)
        self.assertIn("total_minutes", report)
        self.assertIn("avg_daily_minutes", report)

    def test_exercise_streak(self):
        """Seria dni z ćwiczeniami."""
        self.et.log_exercise("running", 30)
        streak = self.et.get_exercise_streak()
        self.assertGreaterEqual(streak, 1)

    def test_delete_exercise(self):
        """Usunięcie ćwiczenia."""
        e = self.et.log_exercise("walking", 20)
        self.et.delete_exercise(e.id)

        exercises = self.et.get_exercises()
        ex_ids = [ex["id"] for ex in exercises]
        self.assertNotIn(e.id, ex_ids)


# ── Sleep Tracker Tests ──────────────────────────────────────────────────────

class TestSleepTracker(unittest.TestCase):
    """Testy trackera snu."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)
        cls.st = SleepTracker(cls.db)

    def test_log_sleep(self):
        """Logowanie snu."""
        s = self.st.log_sleep(
            bedtime="2026-07-18T23:00:00",
            wake_time="2026-07-19T07:00:00",
            quality=8,
            notes="Dobry sen",
        )
        self.assertIsNotNone(s.id)
        self.assertEqual(s.duration_minutes, 480)  # 8h
        self.assertEqual(s.quality, 8)
        self.assertEqual(s.notes, "Dobry sen")
        self.assertEqual(s.sleep_date, "2026-07-18")

    def test_log_sleep_custom_date(self):
        """Logowanie snu z własną datą."""
        s = self.st.log_sleep(
            bedtime="2026-07-15T22:30:00",
            wake_time="2026-07-16T06:30:00",
            quality=7,
            sleep_date="2026-07-15",
        )
        self.assertEqual(s.sleep_date, "2026-07-15")
        self.assertEqual(s.duration_minutes, 480)

    def test_log_sleep_overnight(self):
        """Sen przechodzący przez północ."""
        s = self.st.log_sleep(
            bedtime="2026-07-18T23:30:00",
            wake_time="2026-07-19T06:30:00",
            quality=6,
        )
        self.assertEqual(s.duration_minutes, 420)  # 7h

    def test_get_sleep_logs(self):
        """Pobieranie logów snu."""
        self.st.log_sleep("2026-07-17T23:00:00", "2026-07-18T07:00:00", 7)
        self.st.log_sleep("2026-07-18T23:00:00", "2026-07-19T07:00:00", 8)

        logs = self.st.get_sleep_logs()
        self.assertGreaterEqual(len(logs), 2)

    def test_get_sleep_logs_date_range(self):
        """Filtrowanie logów snu po dacie."""
        self.st.log_sleep("2026-07-10T23:00:00", "2026-07-11T07:00:00", 6)
        self.st.log_sleep("2026-07-18T23:00:00", "2026-07-19T07:00:00", 8)

        recent = self.st.get_sleep_logs(start_date="2026-07-15")
        self.assertGreaterEqual(len(recent), 1)
        for r in recent:
            self.assertGreaterEqual(r["sleep_date"], "2026-07-15")

    def test_get_last_sleep(self):
        """Ostatni sen."""
        self.st.log_sleep("2026-07-19T22:00:00", "2026-07-20T06:00:00", 9)
        last = self.st.get_last_sleep()
        self.assertIsNotNone(last)
        self.assertEqual(last["quality"], 9)

    def test_weekly_sleep_report(self):
        """Raport tygodniowy snu."""
        self.st.log_sleep("2026-07-18T23:00:00", "2026-07-19T07:00:00", 7)
        report = self.st.get_weekly_sleep_report()
        self.assertIn("avg_duration_hours", report)
        self.assertIn("avg_quality", report)
        self.assertIn("nights_tracked", report)

    def test_sleep_debt(self):
        """Dług senny."""
        self.st.log_sleep("2026-07-18T23:00:00", "2026-07-19T06:00:00", 5)  # 7h
        debt = self.st.get_sleep_debt()
        self.assertIn("debt_hours", debt)
        self.assertIn("avg_hours_last_7d", debt)
        self.assertIn("target_hours", debt)
        self.assertEqual(debt["target_hours"], 8.0)

    def test_delete_sleep_log(self):
        """Usunięcie logu snu."""
        s = self.st.log_sleep("2026-07-18T23:00:00", "2026-07-19T07:00:00", 5)
        self.st.delete_sleep_log(s.id)

        logs = self.st.get_sleep_logs()
        log_ids = [l["id"] for l in logs]
        self.assertNotIn(s.id, log_ids)


# ── Health Report Tests ──────────────────────────────────────────────────────

class TestHealthReport(unittest.TestCase):
    """Testy generatora raportów zdrowotnych."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_health.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = HealthDB(cls.db_path)
        cls.hr = HealthReport(cls.db)

    def test_daily_health_brief(self):
        """Daily health brief powinien się wygenerować."""
        # Dodaj trochę danych
        self.hr.meals.log_meal("breakfast", "Test", 300)
        self.hr.water.set_daily_goal(2500)
        self.hr.water.log_water(500)
        self.hr.exercise.log_exercise("running", 30)

        brief = self.hr.daily_health_brief()
        self.assertIsInstance(brief, str)
        self.assertIn("HEALTH BRIEF", brief)
        self.assertIn("PIGUŁKI", brief)
        self.assertIn("POSIŁKI", brief)
        self.assertIn("WODA", brief)
        self.assertIn("ĆWICZENIA", brief)
        self.assertIn("SEN", brief)

    def test_weekly_health_report(self):
        """Weekly health report powinien się wygenerować."""
        self.hr.meals.log_meal("lunch", "Test", 500)
        self.hr.water.log_water(1000)
        self.hr.exercise.log_exercise("gym", 60)
        self.hr.sleep.log_sleep("2026-07-18T23:00:00", "2026-07-19T07:00:00", 7)

        report = self.hr.weekly_health_report()
        self.assertIsInstance(report, str)
        self.assertIn("HEALTH WEEKLY REPORT", report)
        self.assertIn("WODA", report)
        self.assertIn("ODŻYWIANIE", report)
        self.assertIn("ĆWICZENIA", report)
        self.assertIn("SEN", report)


# ── CLI Tests ────────────────────────────────────────────────────────────────

class TestHealthCLI(unittest.TestCase):
    """Testy CLI health.py (przez subprocess)."""

    def test_cli_help(self):
        """CLI bez argumentów pokazuje help."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py")],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Health & Wellness", result.stdout)

    def test_cli_water_glass(self):
        """CLI water-glass."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"), "water-glass"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Szklanka", result.stdout)

    def test_cli_water_today(self):
        """CLI water-today."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"), "water-today"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)

    def test_cli_health_brief(self):
        """CLI health-brief."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"), "health-brief"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("HEALTH BRIEF", result.stdout)

    def test_cli_health_weekly(self):
        """CLI health-weekly."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"), "health-weekly"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("HEALTH WEEKLY REPORT", result.stdout)

    def test_cli_pill_schedule_add(self):
        """CLI pill-schedule-add."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"),
             "pill-schedule-add", "TestCLI", "10:00", "1 tab"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Dodano harmonogram", result.stdout)

    def test_cli_exercise_streak(self):
        """CLI exercise-streak."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"), "exercise-streak"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Seria", result.stdout)

    def test_cli_sleep_debt(self):
        """CLI sleep-debt."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "health.py"), "sleep-debt"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Dług senny", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
