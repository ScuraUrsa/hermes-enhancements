#!/usr/bin/env python3
"""Testy dla core.py — Life Management System."""

import unittest
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import (
    LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator,
    Person, TimeBlock, Event, HabitLog,
)


class TestLifeDB(unittest.TestCase):
    """Testy bazy danych."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_life_management.db")
        # Usuń starą testową bazę
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = LifeDB(cls.db_path)

    def test_tables_exist(self):
        """Wszystkie tabele powinny istnieć."""
        tables = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [t["name"] for t in tables]
        for expected in ["people", "time_blocks", "events", "habit_log"]:
            self.assertIn(expected, table_names)

    def test_insert_and_select(self):
        """Insert i select powinny działać."""
        person_id = self.db.insert("people", {
            "name": "Test Osoba",
            "category": "znajomi",
            "priority": 5,
            "contact_frequency_days": 14,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        self.assertIsNotNone(person_id)
        self.assertGreater(person_id, 0)

        row = self.db.execute_one("SELECT * FROM people WHERE id = ?", (person_id,))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "Test Osoba")

    def test_update(self):
        """Update powinien zmienić dane."""
        person_id = self.db.insert("people", {
            "name": "Do Update",
            "category": "znajomi",
            "priority": 3,
            "contact_frequency_days": 7,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        self.db.update("people", {"priority": 8}, "id = ?", (person_id,))
        row = self.db.execute_one("SELECT priority FROM people WHERE id = ?", (person_id,))
        self.assertEqual(row["priority"], 8)

    def test_delete(self):
        """Delete powinien usunąć wiersz."""
        person_id = self.db.insert("people", {
            "name": "Do Usunięcia",
            "category": "inni",
            "priority": 1,
            "contact_frequency_days": 30,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        self.db.delete("people", "id = ?", (person_id,))
        row = self.db.execute_one("SELECT * FROM people WHERE id = ?", (person_id,))
        self.assertIsNone(row)


class TestPeopleManager(unittest.TestCase):
    """Testy zarządzania osobami."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_life_management.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = LifeDB(cls.db_path)
        cls.pm = PeopleManager(cls.db)

    def test_add_and_get_person(self):
        """Dodanie i pobranie osoby."""
        p = self.pm.add_person(
            name="Jan Kowalski",
            category="znajomi_bliscy",
            priority=8,
            birthday="1990-05-15",
            phone="+48123456789",
            contact_frequency_days=7,
        )
        self.assertIsNotNone(p.id)
        self.assertEqual(p.name, "Jan Kowalski")
        self.assertEqual(p.category, "znajomi_bliscy")
        self.assertEqual(p.priority, 8)

        # Pobierz ponownie
        p2 = self.pm.get_person(p.id)
        self.assertIsNotNone(p2)
        self.assertEqual(p2.name, "Jan Kowalski")

    def test_get_all_people(self):
        """Pobranie wszystkich osób."""
        self.pm.add_person("Anna", "rodzina_blizsza", priority=10)
        self.pm.add_person("Bob", "znajomi", priority=3)
        self.pm.add_person("Charlie", "wspolpracownicy", priority=6)

        all_people = self.pm.get_all_people()
        self.assertGreaterEqual(len(all_people), 3)

        # Filtrowanie po kategorii
        family = self.pm.get_all_people(category="rodzina_blizsza")
        self.assertTrue(all(p.category == "rodzina_blizsza" for p in family))

    def test_update_person(self):
        """Aktualizacja osoby."""
        p = self.pm.add_person("Do Update", "znajomi", priority=3)
        updated = self.pm.update_person(p.id, priority=9, notes="Testowa notatka")
        self.assertEqual(updated.priority, 9)
        self.assertEqual(updated.notes, "Testowa notatka")

    def test_delete_person(self):
        """Usunięcie osoby."""
        p = self.pm.add_person("Do Usunięcia", "inni", priority=1)
        self.pm.delete_person(p.id)
        self.assertIsNone(self.pm.get_person(p.id))

    def test_upcoming_birthdays(self):
        """Nadchodzące urodziny."""
        today = date.today()
        # Urodziny za 5 dni
        bday_soon = (today + timedelta(days=5)).strftime("%Y-%m-%d")
        # Urodziny za 200 dni
        bday_late = (today + timedelta(days=200)).strftime("%Y-%m-%d")

        self.pm.add_person("Soon", "znajomi", birthday=bday_soon)
        self.pm.add_person("Late", "znajomi", birthday=bday_late)

        upcoming = self.pm.get_upcoming_birthdays(days_ahead=30)
        names = [u["name"] for u in upcoming]
        self.assertIn("Soon", names)
        self.assertNotIn("Late", names)

    def test_balance_report(self):
        """Raport balansu czasu."""
        p = self.pm.add_person("Test Balance", "znajomi", priority=5)
        tracker = TimeTracker(self.db)
        tracker.log_manual_block(
            "2026-07-19T10:00:00", "2026-07-19T11:00:00",
            "znajomi", person_id=p.id, description="Spotkanie"
        )

        balance = self.pm.get_balance_report()
        self.assertGreaterEqual(balance["total_people"], 1)

        # Znajdź naszą osobę
        test_person = next(
            (bp for bp in balance["people"] if bp["id"] == p.id), None
        )
        self.assertIsNotNone(test_person)
        self.assertGreater(test_person["minutes_last_30d"], 0)


class TestTimeTracker(unittest.TestCase):
    """Testy śledzenia czasu."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_life_management.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = LifeDB(cls.db_path)
        cls.tracker = TimeTracker(cls.db)

    def test_log_manual_block(self):
        """Ręczne logowanie bloku."""
        block = self.tracker.log_manual_block(
            "2026-07-19T08:00:00", "2026-07-19T09:00:00",
            "praca", description="Kodowanie"
        )
        self.assertIsNotNone(block.id)
        self.assertEqual(block.category, "praca")
        self.assertEqual(block.description, "Kodowanie")

    def test_get_blocks_with_filters(self):
        """Pobieranie bloków z filtrami."""
        self.tracker.log_manual_block(
            "2026-07-19T08:00:00", "2026-07-19T09:00:00", "praca"
        )
        self.tracker.log_manual_block(
            "2026-07-19T12:00:00", "2026-07-19T13:00:00", "jedzenie"
        )
        self.tracker.log_manual_block(
            "2026-07-18T08:00:00", "2026-07-18T09:00:00", "praca"
        )

        # Filtruj po dacie
        today_blocks = self.tracker.get_blocks(
            start_date="2026-07-19T00:00:00", end_date="2026-07-19T23:59:59"
        )
        self.assertEqual(len(today_blocks), 2)

        # Filtruj po kategorii
        work_blocks = self.tracker.get_blocks(category="praca")
        self.assertEqual(len(work_blocks), 2)

    def test_today_summary(self):
        """Podsumowanie dnia."""
        self.tracker.log_manual_block(
            "2026-07-19T08:00:00", "2026-07-19T09:00:00", "praca"
        )
        self.tracker.log_manual_block(
            "2026-07-19T09:00:00", "2026-07-19T10:30:00", "praca"
        )

        summary = self.tracker.get_today_summary()
        self.assertIn("total_minutes", summary)
        self.assertIn("by_category", summary)
        self.assertIn("praca", summary["by_category"])
        self.assertGreater(summary["by_category"]["praca"], 0)

    def test_weekly_report(self):
        """Raport tygodniowy."""
        self.tracker.log_manual_block(
            "2026-07-19T08:00:00", "2026-07-19T09:00:00", "praca"
        )

        report = self.tracker.get_weekly_report()
        self.assertIn("total_hours", report)
        self.assertIn("daily_average_hours", report)


class TestEventManager(unittest.TestCase):
    """Testy zarządzania wydarzeniami."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_life_management.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = LifeDB(cls.db_path)
        cls.em = EventManager(cls.db)

    def test_add_and_get_event(self):
        """Dodanie i pobranie wydarzenia."""
        e = self.em.add_event(
            title="Test Event",
            event_date="2026-07-25",
            event_type="deadline",
            reminder_days_before=3,
        )
        self.assertIsNotNone(e.id)
        self.assertEqual(e.title, "Test Event")

        e2 = self.em.get_event(e.id)
        self.assertEqual(e2.title, "Test Event")

    def test_upcoming_events(self):
        """Nadchodzące wydarzenia."""
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        next_month = (date.today() + timedelta(days=40)).isoformat()

        self.em.add_event("Jutro", tomorrow, "spotkanie")
        self.em.add_event("Za miesiąc", next_month, "deadline")

        upcoming = self.em.get_upcoming_events(days_ahead=7)
        titles = [e["title"] for e in upcoming]
        self.assertIn("Jutro", titles)
        self.assertNotIn("Za miesiąc", titles)

    def test_events_needing_reminder(self):
        """Wydarzenia potrzebujące przypomnienia."""
        today = date.today()
        soon = (today + timedelta(days=2)).isoformat()

        self.em.add_event(
            "Przypomnij", soon, "spotkanie", reminder_days_before=3
        )

        needing = self.em.get_events_needing_reminder()
        titles = [e["title"] for e in needing]
        self.assertIn("Przypomnij", titles)

    def test_mark_notified(self):
        """Oznaczenie jako powiadomione."""
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        e = self.em.add_event("Test Notify", tomorrow, "spotkanie", reminder_days_before=3)

        self.em.mark_notified(e.id)
        e2 = self.em.get_event(e.id)
        self.assertTrue(e2.notified)


class TestHabitTracker(unittest.TestCase):
    """Testy śledzenia nawyków."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_life_management.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = LifeDB(cls.db_path)
        cls.ht = HabitTracker(cls.db)

    def test_log_habit(self):
        """Logowanie nawyku."""
        h = self.ht.log("pills", "taken")
        self.assertIsNotNone(h.id)
        self.assertEqual(h.habit_type, "pills")
        self.assertEqual(h.value, "taken")

    def test_get_today_habits(self):
        """Dzisiejsze nawyki."""
        self.ht.log("pills", "taken")
        self.ht.log("exercise", "30min")
        self.ht.log("water", "250ml")

        today = self.ht.get_today_habits()
        self.assertIn("pills", today)
        self.assertIn("exercise", today)
        self.assertIn("water", today)

    def test_streak(self):
        """Seria dni."""
        # Loguj pigułki na dziś
        self.ht.log("pills", "taken")
        streak = self.ht.get_streak("pills")
        self.assertGreaterEqual(streak, 1)

    def test_weekly_report(self):
        """Raport tygodniowy."""
        self.ht.log("pills", "taken")
        self.ht.log("exercise", "30min")

        report = self.ht.get_weekly_habit_report()
        self.assertIn("habits", report)
        self.assertIn("pills", report["habits"])


class TestReportGenerator(unittest.TestCase):
    """Testy generatora raportów."""

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(Path(__file__).parent / "data" / "test_life_management.db")
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        cls.db = LifeDB(cls.db_path)
        cls.rg = ReportGenerator(cls.db)

    def test_daily_brief(self):
        """Daily brief powinien się wygenerować."""
        brief = self.rg.daily_brief()
        self.assertIsInstance(brief, str)
        self.assertIn("CZAS", brief)
        self.assertIn("WYDARZENIA", brief)
        self.assertIn("URODZINY", brief)
        self.assertIn("KONTAKT", brief)
        self.assertIn("NAWYKI", brief)

    def test_weekly_deep_dive(self):
        """Weekly deep dive powinien się wygenerować."""
        report = self.rg.weekly_deep_dive()
        self.assertIsInstance(report, str)
        self.assertIn("RAPORT TYGODNIOWY", report)


class TestCLI(unittest.TestCase):
    """Testy CLI (przez subprocess)."""

    def test_cli_help(self):
        """CLI bez argumentów pokazuje help."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "life_cli.py")],
            capture_output=True, text=True, timeout=5
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Life Management System", result.stdout)

    def test_cli_pill(self):
        """CLI pill komenda."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "life_cli.py"), "pill", "taken"],
            capture_output=True, text=True, timeout=5
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Pigułki", result.stdout)

    def test_cli_today(self):
        """CLI today komenda."""
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent / "life_cli.py"), "today"],
            capture_output=True, text=True, timeout=5
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
