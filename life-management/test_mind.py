#!/usr/bin/env python3
"""
Testy dla mind.py — Mind & Habits Module.
"""

import unittest
import os
import sys
import json
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mind import (
    MindDB,
    IntrusiveThoughtTracker,
    SnackingTracker,
    FocusTracker,
    DailyGoalsManager,
    WeeklyReviewManager,
    MindReportGenerator,
    IntrusiveThought,
    SnackingLog,
    FocusSession,
    DailyGoal,
    WeeklyReview,
    CBT_PATTERNS,
    COPING_STRATEGIES,
    SNACKING_TRIGGERS,
    FEELING_AFTER,
)


class TestMindDB(unittest.TestCase):
    """Testy rozszerzonej bazy danych."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)

    def test_all_tables_exist(self):
        """Wszystkie tabele (core + mind) powinny istnieć."""
        tables = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t["name"] for t in tables]
        for expected in [
            "people", "time_blocks", "events", "habit_log",
            "intrusive_thoughts", "snacking_log", "focus_sessions",
            "daily_goals", "weekly_reviews",
        ]:
            self.assertIn(expected, table_names, f"Missing table: {expected}")

    def test_intrusive_thoughts_schema(self):
        """Tabela intrusive_thoughts powinna mieć wszystkie kolumny."""
        self.db.insert("intrusive_thoughts", {
            "timestamp": datetime.now().isoformat(),
            "thought_content": "test",
            "trigger": "test trigger",
            "cbt_pattern": "catastrophizing",
            "intensity": 7,
            "coping_strategy": "mindfulness",
            "coping_effectiveness": 8,
            "outcome": "felt better",
            "notes": "test note",
            "created_at": datetime.now().isoformat(),
        })
        row = self.db.execute_one("SELECT * FROM intrusive_thoughts WHERE thought_content = 'test'")
        self.assertIsNotNone(row)
        self.assertEqual(row["cbt_pattern"], "catastrophizing")
        self.assertEqual(row["coping_strategy"], "mindfulness")

    def test_snacking_log_schema(self):
        """Tabela snacking_log powinna mieć wszystkie kolumny."""
        self.db.insert("snacking_log", {
            "timestamp": datetime.now().isoformat(),
            "trigger_type": "stress",
            "trigger_detail": "deadline pressure",
            "food_eaten": "chips",
            "amount": "half bag",
            "intensity": 8,
            "feeling_after": "guilty",
            "alternative_action": "walk",
            "notes": "test",
            "created_at": datetime.now().isoformat(),
        })
        row = self.db.execute_one("SELECT * FROM snacking_log WHERE food_eaten = 'chips'")
        self.assertIsNotNone(row)
        self.assertEqual(row["trigger_type"], "stress")
        self.assertEqual(row["feeling_after"], "guilty")

    def test_focus_sessions_schema(self):
        """Tabela focus_sessions powinna mieć wszystkie kolumny."""
        self.db.insert("focus_sessions", {
            "start_time": datetime.now().isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_minutes": 25,
            "actual_duration_minutes": 23,
            "task_description": "coding",
            "distractions": json.dumps(["phone", "email"]),
            "distraction_count": 2,
            "productivity_score": 8,
            "focus_level": 7,
            "completed": 1,
            "notes": "test",
            "created_at": datetime.now().isoformat(),
        })
        row = self.db.execute_one("SELECT * FROM focus_sessions WHERE task_description = 'coding'")
        self.assertIsNotNone(row)
        self.assertEqual(row["productivity_score"], 8)
        self.assertEqual(row["distraction_count"], 2)

    def test_daily_goals_schema(self):
        """Tabela daily_goals powinna mieć wszystkie kolumny."""
        self.db.insert("daily_goals", {
            "goal_date": date.today().isoformat(),
            "priority_order": 1,
            "goal_text": "Finish project",
            "completed": 0,
            "notes": "",
            "created_at": datetime.now().isoformat(),
        })
        row = self.db.execute_one("SELECT * FROM daily_goals WHERE goal_text = 'Finish project'")
        self.assertIsNotNone(row)
        self.assertEqual(row["priority_order"], 1)
        self.assertEqual(row["completed"], 0)

    def test_weekly_reviews_schema(self):
        """Tabela weekly_reviews powinna mieć wszystkie kolumny."""
        self.db.insert("weekly_reviews", {
            "week_start": "2026-07-13",
            "week_end": "2026-07-19",
            "what_went_well": "productive week",
            "what_to_improve": "less snacking",
            "lessons_learned": "planning helps",
            "gratitude": "health",
            "energy_avg": 7,
            "mood_avg": 6,
            "goals_completed": 8,
            "goals_total": 12,
            "next_week_focus": "deep work",
            "created_at": datetime.now().isoformat(),
        })
        row = self.db.execute_one("SELECT * FROM weekly_reviews WHERE week_start = '2026-07-13'")
        self.assertIsNotNone(row)
        self.assertEqual(row["energy_avg"], 7)
        self.assertEqual(row["goals_completed"], 8)


class TestIntrusiveThoughtTracker(unittest.TestCase):
    """Testy analizy natarczywych myśli."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind_thoughts.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)
        cls.tracker = IntrusiveThoughtTracker(cls.db)

    def setUp(self):
        """Wyczyść dane przed każdym testem."""
        self.db.delete("intrusive_thoughts", "1=1")
        self.db.delete("habit_log", "1=1")

    def test_log_and_get_thought(self):
        """Logowanie i pobieranie myśli."""
        t = self.tracker.log_thought(
            thought_content="I'm going to fail this project",
            trigger="Received critical feedback",
            cbt_pattern="catastrophizing",
            intensity=8,
            coping_strategy="cognitive_restructuring",
            coping_effectiveness=7,
            outcome="Reframed: feedback is an opportunity to improve",
        )
        self.assertIsNotNone(t.id)
        self.assertEqual(t.cbt_pattern, "catastrophizing")
        self.assertEqual(t.intensity, 8)
        self.assertEqual(t.coping_strategy, "cognitive_restructuring")

        t2 = self.tracker.get_thought(t.id)
        self.assertIsNotNone(t2)
        self.assertEqual(t2.thought_content, "I'm going to fail this project")

    def test_log_thought_also_logs_to_habit_log(self):
        """Logowanie myśli powinno też dodać wpis w habit_log."""
        self.tracker.log_thought(
            thought_content="Nobody likes me",
            trigger="Social situation",
            cbt_pattern="mind_reading",
            intensity=6,
        )
        habit_rows = self.db.execute(
            "SELECT * FROM habit_log WHERE habit_type = 'intrusive_thought' ORDER BY timestamp DESC LIMIT 1"
        )
        self.assertEqual(len(habit_rows), 1)
        self.assertIn("mind_reading", habit_rows[0]["notes"])

    def test_get_thoughts_with_filters(self):
        """Pobieranie myśli z filtrami."""
        self.tracker.log_thought(
            thought_content="Thought A",
            trigger="trigger A",
            cbt_pattern="black_and_white",
            intensity=5,
        )
        self.tracker.log_thought(
            thought_content="Thought B",
            trigger="trigger B",
            cbt_pattern="catastrophizing",
            intensity=7,
        )
        self.tracker.log_thought(
            thought_content="Thought C",
            trigger="trigger C",
            cbt_pattern="black_and_white",
            intensity=4,
        )

        bw_thoughts = self.tracker.get_thoughts(cbt_pattern="black_and_white")
        self.assertEqual(len(bw_thoughts), 2)
        for t in bw_thoughts:
            self.assertEqual(t["cbt_pattern"], "black_and_white")

        since = (datetime.now() - timedelta(days=1)).isoformat()
        recent = self.tracker.get_thoughts(start_date=since)
        self.assertGreaterEqual(len(recent), 3)

    def test_cbt_pattern_breakdown(self):
        """Rozkład zniekształceń poznawczych."""
        self.tracker.log_thought(
            thought_content="T1", trigger="t1",
            cbt_pattern="catastrophizing", intensity=8,
            coping_effectiveness=5,
        )
        self.tracker.log_thought(
            thought_content="T2", trigger="t2",
            cbt_pattern="catastrophizing", intensity=6,
            coping_effectiveness=7,
        )
        self.tracker.log_thought(
            thought_content="T3", trigger="t3",
            cbt_pattern="mind_reading", intensity=5,
            coping_effectiveness=8,
        )

        breakdown = self.tracker.get_cbt_pattern_breakdown(days=30)
        self.assertIn("patterns", breakdown)
        self.assertIn("catastrophizing", breakdown["patterns"])
        self.assertIn("mind_reading", breakdown["patterns"])
        self.assertEqual(breakdown["patterns"]["catastrophizing"]["count"], 2)
        self.assertEqual(breakdown["patterns"]["mind_reading"]["count"], 1)
        self.assertEqual(breakdown["patterns"]["catastrophizing"]["avg_intensity"], 7.0)

    def test_top_triggers(self):
        """Najczęstsze triggery."""
        self.tracker.log_thought(
            thought_content="T1", trigger="work stress",
            cbt_pattern="catastrophizing", intensity=8,
        )
        self.tracker.log_thought(
            thought_content="T2", trigger="work stress",
            cbt_pattern="black_and_white", intensity=6,
        )
        self.tracker.log_thought(
            thought_content="T3", trigger="social anxiety",
            cbt_pattern="mind_reading", intensity=5,
        )

        triggers = self.tracker.get_top_triggers(days=30)
        self.assertGreaterEqual(len(triggers), 2)
        self.assertEqual(triggers[0]["trigger"], "work stress")
        self.assertEqual(triggers[0]["count"], 2)

    def test_coping_effectiveness_report(self):
        """Raport skuteczności strategii radzenia sobie."""
        self.tracker.log_thought(
            thought_content="T1", trigger="t1",
            cbt_pattern="catastrophizing", intensity=8,
            coping_strategy="mindfulness", coping_effectiveness=9,
        )
        self.tracker.log_thought(
            thought_content="T2", trigger="t2",
            cbt_pattern="black_and_white", intensity=6,
            coping_strategy="distraction", coping_effectiveness=4,
        )

        report = self.tracker.get_coping_effectiveness_report(days=30)
        self.assertIn("strategies", report)
        self.assertIn("mindfulness", report["strategies"])
        self.assertIn("distraction", report["strategies"])
        self.assertEqual(report["strategies"]["mindfulness"]["avg_effectiveness"], 9.0)
        self.assertEqual(report["strategies"]["distraction"]["avg_effectiveness"], 4.0)


class TestSnackingTracker(unittest.TestCase):
    """Testy mapowania trigger→response dla podjadania."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind_snacks.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)
        cls.tracker = SnackingTracker(cls.db)

    def setUp(self):
        """Wyczyść dane przed każdym testem."""
        self.db.delete("snacking_log", "1=1")
        self.db.delete("habit_log", "1=1")

    def test_log_and_get_snack(self):
        """Logowanie i pobieranie epizodu podjadania."""
        s = self.tracker.log_snack(
            trigger_type="stress",
            trigger_detail="Deadline pressure at work",
            food_eaten="chocolate bar",
            amount="1 large",
            intensity=8,
            feeling_after="guilty",
            alternative_action="Could have gone for a walk",
        )
        self.assertIsNotNone(s.id)
        self.assertEqual(s.trigger_type, "stress")
        self.assertEqual(s.food_eaten, "chocolate bar")
        self.assertEqual(s.feeling_after, "guilty")

        s2 = self.tracker.get_snack(s.id)
        self.assertIsNotNone(s2)
        self.assertEqual(s2.trigger_detail, "Deadline pressure at work")

    def test_log_snack_also_logs_to_habit_log(self):
        """Logowanie podjadania powinno też dodać wpis w habit_log."""
        self.tracker.log_snack(
            trigger_type="boredom",
            food_eaten="crisps",
            feeling_after="regretful",
            intensity=5,
        )
        habit_rows = self.db.execute(
            "SELECT * FROM habit_log WHERE habit_type = 'snacking' ORDER BY timestamp DESC LIMIT 1"
        )
        self.assertEqual(len(habit_rows), 1)
        self.assertIn("boredom", habit_rows[0]["notes"])

    def test_get_snacks_with_filters(self):
        """Pobieranie epizodów z filtrami."""
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="chips",
            feeling_after="guilty", intensity=7,
        )
        self.tracker.log_snack(
            trigger_type="boredom", food_eaten="cookies",
            feeling_after="neutral", intensity=4,
        )
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="ice cream",
            feeling_after="satisfied", intensity=6,
        )

        stress_snacks = self.tracker.get_snacks(trigger_type="stress")
        self.assertEqual(len(stress_snacks), 2)
        for s in stress_snacks:
            self.assertEqual(s["trigger_type"], "stress")

    def test_trigger_breakdown(self):
        """Rozkład triggerów podjadania."""
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="chips",
            feeling_after="guilty", intensity=8,
        )
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="chocolate",
            feeling_after="guilty", intensity=7,
        )
        self.tracker.log_snack(
            trigger_type="boredom", food_eaten="crackers",
            feeling_after="neutral", intensity=3,
        )

        breakdown = self.tracker.get_trigger_breakdown(days=30)
        self.assertIn("triggers", breakdown)
        self.assertIn("stress", breakdown["triggers"])
        self.assertIn("boredom", breakdown["triggers"])
        self.assertEqual(breakdown["triggers"]["stress"]["count"], 2)
        self.assertEqual(breakdown["triggers"]["boredom"]["count"], 1)
        self.assertEqual(breakdown["triggers"]["stress"]["avg_intensity"], 7.5)

    def test_feeling_after_breakdown(self):
        """Rozkład uczuć po podjadaniu."""
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="chips",
            feeling_after="guilty", intensity=7,
        )
        self.tracker.log_snack(
            trigger_type="boredom", food_eaten="cookies",
            feeling_after="guilty", intensity=4,
        )
        self.tracker.log_snack(
            trigger_type="celebration", food_eaten="cake",
            feeling_after="happy", intensity=3,
        )

        feelings = self.tracker.get_feeling_after_breakdown(days=30)
        self.assertIn("feelings", feelings)
        self.assertEqual(feelings["feelings"]["guilty"], 2)
        self.assertEqual(feelings["feelings"]["happy"], 1)

    def test_trigger_response_map(self):
        """Mapa trigger → response."""
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="chocolate",
            feeling_after="guilty", intensity=8,
        )
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="chocolate",
            feeling_after="guilty", intensity=7,
        )
        self.tracker.log_snack(
            trigger_type="stress", food_eaten="nuts",
            feeling_after="satisfied", intensity=5,
        )

        tmap = self.tracker.get_trigger_response_map(days=60)
        self.assertIn("trigger_response_map", tmap)
        self.assertIn("stress", tmap["trigger_response_map"])
        stress_responses = tmap["trigger_response_map"]["stress"]
        choc = [r for r in stress_responses if r["food"] == "chocolate"]
        self.assertEqual(len(choc), 1)
        self.assertEqual(choc[0]["count"], 2)
        self.assertEqual(choc[0]["feeling"], "guilty")


class TestFocusTracker(unittest.TestCase):
    """Testy śledzenia sesji focus / Pomodoro."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind_focus.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)
        cls.tracker = FocusTracker(cls.db)

    def setUp(self):
        """Wyczyść dane przed każdym testem."""
        self.db.delete("focus_sessions", "1=1")
        self.db.delete("habit_log", "1=1")

    def test_log_manual_session(self):
        """Ręczne logowanie sesji focus."""
        s = self.tracker.log_manual_session(
            start_time="2026-07-19T09:00:00",
            end_time="2026-07-19T09:25:00",
            task_description="Write tests",
            duration_minutes=25,
            distractions=["phone", "slack"],
            productivity_score=8,
            focus_level=7,
            completed=True,
        )
        self.assertIsNotNone(s.id)
        self.assertEqual(s.task_description, "Write tests")
        self.assertEqual(s.distraction_count, 2)
        self.assertEqual(s.productivity_score, 8)

    def test_get_sessions(self):
        """Pobieranie sesji z filtrami."""
        self.tracker.log_manual_session(
            start_time="2026-07-19T09:00:00",
            end_time="2026-07-19T09:25:00",
            task_description="Task A",
            duration_minutes=25,
            productivity_score=7,
        )
        self.tracker.log_manual_session(
            start_time="2026-07-19T10:00:00",
            end_time="2026-07-19T10:25:00",
            task_description="Task B",
            duration_minutes=25,
            productivity_score=9,
        )

        sessions = self.tracker.get_sessions(
            start_date="2026-07-19T00:00:00",
            end_date="2026-07-19T23:59:59",
        )
        self.assertEqual(len(sessions), 2)

    def test_today_focus_summary(self):
        """Podsumowanie dzisiejszych sesji."""
        today_start = date.today().isoformat() + "T09:00:00"
        today_end = date.today().isoformat() + "T09:25:00"

        self.tracker.log_manual_session(
            start_time=today_start,
            end_time=today_end,
            task_description="Today task",
            duration_minutes=25,
            productivity_score=8,
            focus_level=7,
            distractions=["email"],
            completed=True,
        )

        summary = self.tracker.get_today_focus_summary()
        self.assertGreaterEqual(summary["session_count"], 1)
        self.assertGreaterEqual(summary["total_minutes"], 25)
        self.assertGreaterEqual(summary["completed_count"], 1)

    def test_weekly_focus_report(self):
        """Raport tygodniowy sesji focus."""
        today_start = date.today().isoformat() + "T09:00:00"
        today_end = date.today().isoformat() + "T09:25:00"

        self.tracker.log_manual_session(
            start_time=today_start,
            end_time=today_end,
            task_description="Weekly task",
            duration_minutes=25,
            productivity_score=8,
        )

        report = self.tracker.get_weekly_focus_report()
        self.assertIn("total_sessions", report)
        self.assertIn("total_hours", report)
        self.assertIn("daily", report)
        self.assertGreaterEqual(report["total_sessions"], 1)

    def test_top_distractions(self):
        """Najczęstsze dystrakcje."""
        self.tracker.log_manual_session(
            start_time="2026-07-19T09:00:00",
            end_time="2026-07-19T09:25:00",
            task_description="Task 1",
            duration_minutes=25,
            distractions=["phone", "email", "phone"],
        )
        self.tracker.log_manual_session(
            start_time="2026-07-19T10:00:00",
            end_time="2026-07-19T10:25:00",
            task_description="Task 2",
            duration_minutes=25,
            distractions=["phone", "slack"],
        )

        dists = self.tracker.get_top_distractions(days=30)
        self.assertGreaterEqual(len(dists), 1)
        self.assertEqual(dists[0]["distraction"], "phone")
        self.assertEqual(dists[0]["count"], 3)

    def test_start_and_end_session(self):
        """Rozpoczęcie i zakończenie sesji (live tracking)."""
        session = self.tracker.start_session(
            task_description="Live coding session",
            duration_minutes=25,
        )
        self.assertEqual(session.task_description, "Live coding session")
        self.assertEqual(session.duration_minutes, 25)

        self.tracker.log_distraction("phone call")
        self.tracker.log_distraction("slack message")

        ended = self.tracker.end_session(
            completed=True,
            productivity_score=9,
            focus_level=8,
        )
        self.assertIsNotNone(ended)
        self.assertEqual(ended.task_description, "Live coding session")
        self.assertEqual(ended.distraction_count, 2)
        self.assertEqual(ended.productivity_score, 9)
        self.assertEqual(ended.completed, True)

    def test_end_session_without_start(self):
        """Zakończenie bez rozpoczęcia zwraca None."""
        db2 = MindDB(str(Path(__file__).parent / "data" / "test_mind_focus2.db"))
        if os.path.exists(db2.db_path):
            os.remove(db2.db_path)
        tracker2 = FocusTracker(db2)
        result = tracker2.end_session()
        self.assertIsNone(result)


class TestDailyGoalsManager(unittest.TestCase):
    """Testy zarządzania celami dziennymi."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind_goals.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)
        cls.manager = DailyGoalsManager(cls.db)

    def setUp(self):
        """Wyczyść dane przed każdym testem."""
        self.db.delete("daily_goals", "1=1")

    def test_set_and_get_goals(self):
        """Ustawianie i pobieranie celów."""
        goals = self.manager.set_goals([
            "Finish project report",
            "Go to the gym",
            "Read 30 pages",
        ])
        self.assertEqual(len(goals), 3)
        self.assertEqual(goals[0].priority_order, 1)
        self.assertEqual(goals[0].goal_text, "Finish project report")
        self.assertEqual(goals[1].goal_text, "Go to the gym")
        self.assertEqual(goals[2].goal_text, "Read 30 pages")

        today_goals = self.manager.get_today_goals()
        self.assertEqual(len(today_goals), 3)

    def test_set_goals_replaces_existing(self):
        """Ustawienie nowych celów zastępuje stare na ten sam dzień."""
        self.manager.set_goals(["Old goal 1", "Old goal 2"])
        self.manager.set_goals(["New goal A", "New goal B", "New goal C"])

        today_goals = self.manager.get_today_goals()
        self.assertEqual(len(today_goals), 3)
        texts = [g.goal_text for g in today_goals]
        self.assertIn("New goal A", texts)
        self.assertNotIn("Old goal 1", texts)

    def test_set_goals_max_three(self):
        """Maksymalnie 3 cele."""
        goals = self.manager.set_goals(["A", "B", "C", "D", "E"])
        self.assertEqual(len(goals), 3)

    def test_complete_and_uncomplete_goal(self):
        """Oznaczanie celu jako ukończony/nieukończony."""
        goals = self.manager.set_goals(["Test goal"])
        goal_id = goals[0].id

        completed = self.manager.complete_goal(goal_id)
        self.assertTrue(completed.completed)
        self.assertIsNotNone(completed.completed_at)

        uncompleted = self.manager.uncomplete_goal(goal_id)
        self.assertFalse(uncompleted.completed)
        self.assertIsNone(uncompleted.completed_at)

    def test_get_goals_for_date(self):
        """Pobieranie celów na konkretną datę."""
        self.manager.set_goals(["Goal for specific date"], goal_date="2026-07-15")
        goals = self.manager.get_goals_for_date("2026-07-15")
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].goal_text, "Goal for specific date")

    def test_completion_stats(self):
        """Statystyki ukończenia celów."""
        self.manager.set_goals(["Goal A", "Goal B", "Goal C"])
        today_goals = self.manager.get_today_goals()

        self.manager.complete_goal(today_goals[0].id)
        self.manager.complete_goal(today_goals[1].id)

        stats = self.manager.get_completion_stats(days=30)
        self.assertIn("completion_rate", stats)
        self.assertGreaterEqual(stats["total_goals"], 3)
        self.assertGreaterEqual(stats["total_completed"], 2)


class TestWeeklyReviewManager(unittest.TestCase):
    """Testy cotygodniowych przeglądów."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind_reviews.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)
        cls.manager = WeeklyReviewManager(cls.db)

    def setUp(self):
        """Wyczyść dane przed każdym testem."""
        self.db.delete("weekly_reviews", "1=1")
        self.db.delete("daily_goals", "1=1")

    def test_create_and_get_review(self):
        """Tworzenie i pobieranie przeglądu."""
        r = self.manager.create_review(
            what_went_well="Finished the project\nGood workouts",
            what_to_improve="Less snacking\nMore sleep",
            lessons_learned="Planning ahead reduces stress",
            gratitude="Health, family, good weather",
            energy_avg=7,
            mood_avg=6,
            next_week_focus="Deep work sessions",
        )
        self.assertIsNotNone(r.id)
        self.assertEqual(r.energy_avg, 7)
        self.assertEqual(r.mood_avg, 6)
        self.assertIn("Finished the project", r.what_went_well)
        self.assertIn("Less snacking", r.what_to_improve)

        r2 = self.manager.get_review(r.id)
        self.assertIsNotNone(r2)
        self.assertEqual(r2.lessons_learned, "Planning ahead reduces stress")

    def test_get_review_for_week(self):
        """Pobieranie przeglądu dla konkretnego tygodnia."""
        r = self.manager.create_review(
            what_went_well="Great week",
            week_start="2026-07-06",
        )
        r2 = self.manager.get_review_for_week("2026-07-06")
        self.assertIsNotNone(r2)
        self.assertEqual(r2.what_went_well, "Great week")

    def test_get_latest_review(self):
        """Pobieranie najnowszego przeglądu."""
        self.manager.create_review(
            what_went_well="Week A",
            week_start="2026-07-06",
        )
        self.manager.create_review(
            what_went_well="Week B",
            week_start="2026-07-13",
        )

        latest = self.manager.get_latest_review()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.what_went_well, "Week B")

    def test_get_all_reviews(self):
        """Pobieranie wszystkich przeglądów."""
        self.manager.create_review(what_went_well="R1", week_start="2026-06-01")
        self.manager.create_review(what_went_well="R2", week_start="2026-06-08")

        all_reviews = self.manager.get_all_reviews(limit=10)
        self.assertGreaterEqual(len(all_reviews), 2)

    def test_update_review(self):
        """Aktualizacja przeglądu."""
        r = self.manager.create_review(
            what_went_well="Original",
            week_start="2026-06-15",
        )
        updated = self.manager.update_review(
            r.id,
            what_went_well="Updated text",
            energy_avg=9,
        )
        self.assertEqual(updated.what_went_well, "Updated text")
        self.assertEqual(updated.energy_avg, 9)

    def test_lessons_timeline(self):
        """Oś czasu lessons learned."""
        self.manager.create_review(
            lessons_learned="Lesson A: planning works",
            week_start="2026-06-01",
        )
        self.manager.create_review(
            lessons_learned="Lesson B: sleep matters",
            week_start="2026-06-08",
        )

        timeline = self.manager.get_lessons_timeline(limit=10)
        self.assertGreaterEqual(len(timeline), 2)
        lessons_texts = [t["lessons"] for t in timeline]
        self.assertTrue(any("Lesson A" in l for l in lessons_texts))
        self.assertTrue(any("Lesson B" in l for l in lessons_texts))

    def test_review_auto_counts_goals(self):
        """Przegląd automatycznie zlicza cele z tygodnia."""
        goals_mgr = DailyGoalsManager(self.db)
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        goals_mgr.set_goals(["Goal 1", "Goal 2", "Goal 3"], goal_date=week_start)

        day_goals = goals_mgr.get_goals_for_date(week_start)
        goals_mgr.complete_goal(day_goals[0].id)
        goals_mgr.complete_goal(day_goals[1].id)

        r = self.manager.create_review(
            what_went_well="Test",
            week_start=week_start,
        )
        self.assertEqual(r.goals_total, 3)
        self.assertEqual(r.goals_completed, 2)


class TestMindReportGenerator(unittest.TestCase):
    """Testy generatora raportów Mind & Habits."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_mind_reports.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = MindDB(cls.db_path)
        cls.reports = MindReportGenerator(cls.db)

    def setUp(self):
        """Wyczyść dane przed każdym testem."""
        for table in ["intrusive_thoughts", "snacking_log", "focus_sessions",
                       "daily_goals", "weekly_reviews", "habit_log"]:
            self.db.delete(table, "1=1")

    def test_mind_daily_brief(self):
        """Daily brief powinien się wygenerować."""
        self.reports.thoughts.log_thought(
            thought_content="Test thought",
            trigger="test",
            cbt_pattern="catastrophizing",
            intensity=5,
        )
        self.reports.snacks.log_snack(
            trigger_type="stress",
            food_eaten="test food",
            feeling_after="guilty",
        )
        self.reports.focus.log_manual_session(
            start_time=datetime.now().isoformat(),
            end_time=(datetime.now() + timedelta(minutes=25)).isoformat(),
            task_description="Test focus",
            duration_minutes=25,
            productivity_score=8,
        )
        self.reports.goals.set_goals(["Test goal 1", "Test goal 2"])

        brief = self.reports.mind_daily_brief()
        self.assertIsInstance(brief, str)
        self.assertIn("MIND & HABITS", brief)
        self.assertIn("CELE DNIA", brief)
        self.assertIn("FOCUS", brief)
        self.assertIn("MYŚLI", brief)
        self.assertIn("PODJADANIE", brief)

    def test_mind_weekly_report(self):
        """Weekly report powinien się wygenerować."""
        self.reports.focus.log_manual_session(
            start_time=datetime.now().isoformat(),
            end_time=(datetime.now() + timedelta(minutes=25)).isoformat(),
            task_description="Weekly test",
            duration_minutes=25,
            productivity_score=7,
        )
        self.reports.thoughts.log_thought(
            thought_content="Weekly thought",
            trigger="weekly trigger",
            cbt_pattern="black_and_white",
            intensity=6,
        )
        self.reports.snacks.log_snack(
            trigger_type="boredom",
            food_eaten="weekly snack",
            feeling_after="neutral",
        )

        report = self.reports.mind_weekly_report()
        self.assertIsInstance(report, str)
        self.assertIn("MIND & HABITS — RAPORT TYGODNIOWY", report)
        self.assertIn("FOCUS", report)
        self.assertIn("CELE", report)
        self.assertIn("CBT PATTERNS", report)
        self.assertIn("PODJADANIE", report)


class TestConstants(unittest.TestCase):
    """Testy stałych i typów."""

    def test_cbt_patterns_defined(self):
        """Wszystkie CBT patterns powinny być zdefiniowane."""
        self.assertIn("catastrophizing", CBT_PATTERNS)
        self.assertIn("black_and_white", CBT_PATTERNS)
        self.assertIn("mind_reading", CBT_PATTERNS)
        self.assertGreater(len(CBT_PATTERNS), 5)

    def test_coping_strategies_defined(self):
        """Wszystkie strategie radzenia sobie powinny być zdefiniowane."""
        self.assertIn("mindfulness", COPING_STRATEGIES)
        self.assertIn("cognitive_restructuring", COPING_STRATEGIES)
        self.assertGreater(len(COPING_STRATEGIES), 5)

    def test_snacking_triggers_defined(self):
        """Wszystkie triggery podjadania powinny być zdefiniowane."""
        self.assertIn("stress", SNACKING_TRIGGERS)
        self.assertIn("boredom", SNACKING_TRIGGERS)
        self.assertIn("sadness", SNACKING_TRIGGERS)
        self.assertGreater(len(SNACKING_TRIGGERS), 5)

    def test_feeling_after_defined(self):
        """Wszystkie uczucia po podjadaniu powinny być zdefiniowane."""
        self.assertIn("guilty", FEELING_AFTER)
        self.assertIn("satisfied", FEELING_AFTER)
        self.assertIn("neutral", FEELING_AFTER)
        self.assertGreater(len(FEELING_AFTER), 3)


class TestDataClasses(unittest.TestCase):
    """Testy dataclass."""

    def test_intrusive_thought_defaults(self):
        """Domyślne wartości IntrusiveThought."""
        t = IntrusiveThought()
        self.assertEqual(t.intensity, 5)
        self.assertEqual(t.coping_effectiveness, 5)
        self.assertEqual(t.cbt_pattern, "")

    def test_snacking_log_defaults(self):
        """Domyślne wartości SnackingLog."""
        s = SnackingLog()
        self.assertEqual(s.intensity, 5)
        self.assertEqual(s.feeling_after, "")

    def test_focus_session_defaults(self):
        """Domyślne wartości FocusSession."""
        f = FocusSession()
        self.assertEqual(f.duration_minutes, 25)
        self.assertEqual(f.productivity_score, 5)
        self.assertFalse(f.completed)

    def test_daily_goal_defaults(self):
        """Domyślne wartości DailyGoal."""
        g = DailyGoal()
        self.assertEqual(g.priority_order, 1)
        self.assertFalse(g.completed)

    def test_weekly_review_defaults(self):
        """Domyślne wartości WeeklyReview."""
        r = WeeklyReview()
        self.assertEqual(r.energy_avg, 5)
        self.assertEqual(r.mood_avg, 5)


class TestMindCLI(unittest.TestCase):
    """Testy CLI (przez subprocess) — używają izolowanej testowej bazy."""

    @classmethod
    def setUpClass(cls):
        cls.test_db = str(Path(__file__).parent / "data" / "test_mind_cli.db")
        cls.mind_script = str(Path(__file__).parent / "mind.py")

    def setUp(self):
        """Usuń starą testową bazę przed każdym testem."""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def _run(self, *args):
        """Uruchom mind.py z testową bazą."""
        import subprocess
        env = os.environ.copy()
        env["MIND_DB_PATH"] = self.test_db
        return subprocess.run(
            ["python3", self.mind_script] + list(args),
            capture_output=True, text=True, timeout=10,
            env=env,
        )

    def test_cli_help(self):
        """CLI bez argumentów pokazuje help."""
        result = self._run()
        self.assertEqual(result.returncode, 0)
        self.assertIn("Mind & Habits", result.stdout)
        self.assertIn("thought-log", result.stdout)
        self.assertIn("snack-log", result.stdout)
        self.assertIn("focus-start", result.stdout)
        self.assertIn("goals-set", result.stdout)
        self.assertIn("review-create", result.stdout)
        self.assertIn("mind-brief", result.stdout)

    def test_cli_thought_log(self):
        """CLI thought-log komenda."""
        result = self._run(
            "thought-log", "test thought", "test trigger", "catastrophizing", "7"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Zalogowano myśl", result.stdout)

    def test_cli_snack_log(self):
        """CLI snack-log komenda."""
        result = self._run(
            "snack-log", "stress", "chocolate", "guilty", "8"
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Zalogowano podjadanie", result.stdout)

    def test_cli_goals_set_and_today(self):
        """CLI goals-set i goals-today."""
        result = self._run("goals-set", "Goal A | Goal B | Goal C")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Ustawiono", result.stdout)

        result2 = self._run("goals-today")
        self.assertEqual(result2.returncode, 0)
        self.assertIn("Goal A", result2.stdout)

    def test_cli_focus_today(self):
        """CLI focus-today."""
        result = self._run("focus-today")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Focus dziś", result.stdout)

    def test_cli_mind_brief(self):
        """CLI mind-brief."""
        result = self._run("mind-brief")
        self.assertEqual(result.returncode, 0)
        self.assertIn("MIND & HABITS", result.stdout)

    def test_cli_mind_week(self):
        """CLI mind-week."""
        result = self._run("mind-week")
        self.assertEqual(result.returncode, 0)
        self.assertIn("RAPORT TYGODNIOWY", result.stdout)

    def test_cli_thought_patterns(self):
        """CLI thought-patterns."""
        result = self._run("thought-patterns", "30")
        self.assertEqual(result.returncode, 0)
        self.assertIn("CBT Patterns", result.stdout)

    def test_cli_snack_triggers(self):
        """CLI snack-triggers."""
        result = self._run("snack-triggers", "30")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Triggery podjadania", result.stdout)

    def test_cli_goals_stats(self):
        """CLI goals-stats."""
        result = self._run("goals-stats", "30")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Cele", result.stdout)

    def test_cli_review_list(self):
        """CLI review-list."""
        result = self._run("review-list")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
