"""
Testy dla Life Management System.
Uruchom: PYTHONPATH=. python3 -m pytest tests/test_core.py -v
"""

import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.schema import init_db, get_db, SCHEMA_SQL
from src.time_tracker import TimeTracker, CATEGORIES, CATEGORY_LABELS
from src.people_crm import PeopleCRM, CATEGORIES as PEOPLE_CATS
from src.reporter import Reporter


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    yield tmp.name
    conn.close()
    os.unlink(tmp.name)
    if os.path.exists(tmp.name + "-wal"):
        os.unlink(tmp.name + "-wal")
    if os.path.exists(tmp.name + "-shm"):
        os.unlink(tmp.name + "-shm")


# ═══════════════════════════════════════════════════════════
# SCHEMA
# ═══════════════════════════════════════════════════════════

class TestSchema:
    def test_init_creates_tables(self, db):
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {t["name"] for t in tables}
        expected = {
            "people", "time_blocks", "events", "habits", "habit_log",
            "health_log", "interactions", "focus_sessions",
            "daily_journal", "weekly_summary",
        }
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"

    def test_init_idempotent(self, db):
        """init_db should be safe to call multiple times."""
        conn = sqlite3.connect(db)
        conn.executescript(SCHEMA_SQL)  # second call
        conn.executescript(SCHEMA_SQL)  # third call
        # Should not raise
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(tables) >= 10


# ═══════════════════════════════════════════════════════════
# TIME TRACKER
# ═══════════════════════════════════════════════════════════

class TestTimeTracker:
    def test_start_block(self, db):
        tracker = TimeTracker(db)
        block_id = tracker.start("work_deep", energy=8, planned=True)
        assert block_id > 0

        block = tracker.get_block(block_id)
        assert block["category"] == "work_deep"
        assert block["energy_level"] == 8
        assert block["planned"] == 1
        assert block["end_time"] is None  # still running
        tracker.close()

    def test_start_invalid_category(self, db):
        tracker = TimeTracker(db)
        with pytest.raises(ValueError, match="Invalid category"):
            tracker.start("invalid_category")
        tracker.close()

    def test_stop_block(self, db):
        tracker = TimeTracker(db)
        block_id = tracker.start("work_deep")
        result = tracker.stop(block_id, focus=9, satisfaction=8)

        assert result["id"] == block_id
        assert result["category"] == "work_deep"
        assert result["duration_minutes"] >= 5  # minimum 5 min block
        assert result["focus"] == 9
        assert result["satisfaction"] == 8

        # Verify in DB
        block = tracker.get_block(block_id)
        assert block["end_time"] is not None
        assert block["focus_level"] == 9
        tracker.close()

    def test_stop_already_stopped(self, db):
        tracker = TimeTracker(db)
        block_id = tracker.start("work_deep")
        tracker.stop(block_id)
        with pytest.raises(ValueError, match="already stopped"):
            tracker.stop(block_id)
        tracker.close()

    def test_stop_nonexistent(self, db):
        tracker = TimeTracker(db)
        with pytest.raises(ValueError, match="not found"):
            tracker.stop(99999)
        tracker.close()

    def test_get_active_block(self, db):
        tracker = TimeTracker(db)
        assert tracker.get_active_block() is None

        tracker.start("work_deep")
        active = tracker.get_active_block()
        assert active is not None
        assert active["category"] == "work_deep"

        tracker.stop(active["id"])
        assert tracker.get_active_block() is None
        tracker.close()

    def test_get_blocks_filtered(self, db):
        tracker = TimeTracker(db)
        today = date.today().isoformat()

        tracker.start("work_deep")
        tracker.start("health")
        tracker.start("people")

        # All blocks (still running)
        blocks = tracker.get_blocks(date=today)
        assert len(blocks) == 3

        blocks = tracker.get_blocks(category="health")
        assert len(blocks) == 1
        assert blocks[0]["category"] == "health"
        tracker.close()

    def test_summary_today(self, db):
        tracker = TimeTracker(db)
        b1 = tracker.start("work_deep")
        tracker.stop(b1)
        b2 = tracker.start("health")
        tracker.stop(b2)

        summary = tracker.summary_today()
        assert summary["total_minutes"] >= 10  # 2 blocks * 5 min
        assert summary["breakdown"]["work_deep"] >= 5
        assert summary["breakdown"]["health"] >= 5
        assert summary["active_block"] is None
        tracker.close()

    def test_summary_range(self, db):
        tracker = TimeTracker(db)
        b1 = tracker.start("work_deep")
        tracker.stop(b1)

        today = date.today().isoformat()
        summary = tracker.summary_range(today, today)
        assert summary["total_minutes"] >= 5
        tracker.close()

    def test_summary_this_week(self, db):
        tracker = TimeTracker(db)
        b1 = tracker.start("work_deep")
        tracker.stop(b1)

        summary = tracker.summary_this_week()
        assert summary["total_minutes"] >= 5
        tracker.close()

    def test_focus_session(self, db):
        tracker = TimeTracker(db)
        session_id = tracker.start_focus(duration=25, task="Test task")
        assert session_id > 0

        result = tracker.stop_focus(session_id, interruptions=2, focus_level=8)
        assert result["planned"] == 25
        assert result["interruptions"] == 2
        assert result["focus"] == 8
        tracker.close()

    def test_focus_session_nonexistent(self, db):
        tracker = TimeTracker(db)
        with pytest.raises(ValueError, match="not found"):
            tracker.stop_focus(99999)
        tracker.close()

    def test_stats(self, db):
        tracker = TimeTracker(db)
        b1 = tracker.start("work_deep")
        tracker.stop(b1)
        b2 = tracker.start("waste")
        tracker.stop(b2)

        stats = tracker.stats()
        assert "today" in stats
        assert "week" in stats
        assert "waste_ratio_pct" in stats
        assert "deep_work_ratio_pct" in stats
        tracker.close()

    def test_rounding_to_5min_blocks(self, db):
        """Duration should round to nearest 5-minute block."""
        tracker = TimeTracker(db)
        block_id = tracker.start("work_deep")
        result = tracker.stop(block_id)
        # Even if it took 1 second, minimum is 5 min
        assert result["duration_minutes"] >= 5
        assert result["duration_minutes"] % 5 == 0
        tracker.close()


# ═══════════════════════════════════════════════════════════
# PEOPLE CRM
# ═══════════════════════════════════════════════════════════

class TestPeopleCRM:
    def test_add_person(self, db):
        crm = PeopleCRM(db)
        person_id = crm.add_person(
            "Test Osoba", "family_close", priority=2,
            birthday="1990-05-15", phone="+48123456789",
        )
        assert person_id > 0

        person = crm.get_person(person_id)
        assert person["name"] == "Test Osoba"
        assert person["category"] == "family_close"
        assert person["priority"] == 2
        assert person["birthday"] == "1990-05-15"
        assert person["contact_frequency_days"] == 1  # family_close default
        crm.close()

    def test_add_person_invalid_category(self, db):
        crm = PeopleCRM(db)
        with pytest.raises(ValueError, match="Invalid category"):
            crm.add_person("Test", "invalid")
        crm.close()

    def test_get_all_people(self, db):
        crm = PeopleCRM(db)
        crm.add_person("A", "family_close", priority=1)
        crm.add_person("B", "friends", priority=5)
        crm.add_person("C", "work", priority=3)

        all_people = crm.get_all_people()
        assert len(all_people) == 3

        # Sorted by priority
        assert all_people[0]["name"] == "A"  # priority 1
        assert all_people[1]["name"] == "C"  # priority 3
        assert all_people[2]["name"] == "B"  # priority 5
        crm.close()

    def test_get_all_people_filtered(self, db):
        crm = PeopleCRM(db)
        crm.add_person("A", "family_close")
        crm.add_person("B", "friends")

        family = crm.get_all_people(category="family_close")
        assert len(family) == 1
        assert family[0]["name"] == "A"
        crm.close()

    def test_update_person(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "friends")
        crm.update_person(pid, name="Updated", priority=8)

        person = crm.get_person(pid)
        assert person["name"] == "Updated"
        assert person["priority"] == 8
        crm.close()

    def test_delete_person(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "friends")
        crm.delete_person(pid)
        assert crm.get_person(pid) is None
        crm.close()

    def test_log_interaction(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "friends")

        interaction_id = crm.log_interaction(
            pid, "call", duration_minutes=15, quality=8,
        )
        assert interaction_id > 0

        person = crm.get_person(pid)
        assert person["last_contact"] is not None
        assert person["total_interactions"] == 1
        assert person["total_time_minutes"] == 15
        crm.close()

    def test_get_interactions(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "friends")
        crm.log_interaction(pid, "call", duration_minutes=10)
        crm.log_interaction(pid, "message", duration_minutes=2)

        interactions = crm.get_interactions(person_id=pid)
        assert len(interactions) == 2
        assert interactions[0]["interaction_type"] == "message"  # most recent first
        crm.close()

    def test_get_neglected(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "family_close")  # threshold: 1 day
        # No interaction logged → neglected
        neglected = crm.get_neglected()
        assert len(neglected) >= 1
        assert neglected[0]["name"] == "Test"
        assert neglected[0]["days_since_contact"] == 999  # never contacted
        crm.close()

    def test_get_neglected_after_contact(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "family_close")  # threshold: 1 day
        crm.log_interaction(pid, "call", duration_minutes=5)

        neglected = crm.get_neglected()
        # Just contacted → not neglected
        assert all(n["name"] != "Test" for n in neglected)
        crm.close()

    def test_upcoming_birthdays(self, db):
        crm = PeopleCRM(db)
        today = date.today()
        tomorrow = today + timedelta(days=1)
        next_week = today + timedelta(days=7)

        crm.add_person("Tomorrow", "friends", birthday=tomorrow.isoformat())
        crm.add_person("NextWeek", "friends", birthday=next_week.isoformat())
        crm.add_person("Past", "friends", birthday="1990-01-01")

        birthdays = crm.get_upcoming_birthdays(days_ahead=10)
        assert len(birthdays) == 2
        assert birthdays[0]["name"] == "Tomorrow"
        assert birthdays[0]["days_until"] == 1
        crm.close()

    def test_calculate_balance(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "family_close", target_minutes_per_week=60)
        # No time logged → balance should be negative
        balances = crm.calculate_balance()
        test_balance = [b for b in balances if b["name"] == "Test"][0]
        assert test_balance["balance_score"] < 0
        assert test_balance["actual_minutes_this_week"] == 0
        crm.close()

    def test_balance_report(self, db):
        crm = PeopleCRM(db)
        crm.add_person("A", "family_close")
        crm.add_person("B", "friends")

        report = crm.balance_report()
        assert report["total_people"] == 2
        assert "neglected" in report
        assert "upcoming_birthdays" in report
        assert "category_breakdown" in report
        crm.close()

    def test_quick_contact(self, db):
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "friends")
        crm.quick_contact(pid)

        person = crm.get_person(pid)
        assert person["total_interactions"] == 1
        crm.close()

    def test_who_to_contact_today(self, db):
        crm = PeopleCRM(db)
        crm.add_person("A", "family_close")  # threshold 1 day, never contacted
        crm.add_person("B", "family_close")
        crm.log_interaction(2, "call")  # B contacted

        to_contact = crm.who_to_contact_today(limit=5)
        assert len(to_contact) >= 1
        assert to_contact[0]["name"] == "A"  # A is neglected
        crm.close()

    def test_import_sample_50(self, db):
        crm = PeopleCRM(db)
        count = crm.import_sample_50()
        assert count == 50

        all_people = crm.get_all_people()
        assert len(all_people) == 50

        # Check categories
        categories = set(p["category"] for p in all_people)
        assert "family_close" in categories
        assert "partner" in categories
        assert "friends_close" in categories
        crm.close()


# ═══════════════════════════════════════════════════════════
# REPORTER
# ═══════════════════════════════════════════════════════════

class TestReporter:
    def test_daily_briefing_empty(self, db):
        reporter = Reporter(db)
        briefing = reporter.daily_briefing()
        assert "date" in briefing
        assert "time" in briefing
        assert "people" in briefing
        assert "health" in briefing
        assert "alerts" in briefing
        reporter.close()

    def test_daily_briefing_with_data(self, db):
        # Setup: add people, track time, log health
        crm = PeopleCRM(db)
        crm.add_person("Test", "family_close")
        crm.close()

        tracker = TimeTracker(db)
        b1 = tracker.start("work_deep")
        tracker.stop(b1)
        tracker.close()

        # Log health
        conn = sqlite3.connect(db)
        today = date.today().isoformat()
        conn.execute(
            """INSERT INTO health_log (date, pills_taken, sleep_hours, mood, energy)
               VALUES (?, 1, 7.5, 7, 6)
               ON CONFLICT(date) DO UPDATE SET
               pills_taken=1, sleep_hours=7.5, mood=7, energy=6""",
            (today,),
        )
        conn.commit()
        conn.close()

        reporter = Reporter(db)
        briefing = reporter.daily_briefing()
        assert briefing["time"]["total_hours"] >= 0
        assert briefing["health"]["has_data"]
        assert briefing["health"]["pills_taken"]
        reporter.close()

    def test_weekly_summary(self, db):
        crm = PeopleCRM(db)
        crm.add_person("Test", "family_close")
        crm.close()

        tracker = TimeTracker(db)
        b1 = tracker.start("work_deep")
        tracker.stop(b1)
        tracker.close()

        reporter = Reporter(db)
        summary = reporter.weekly_summary()
        assert "week" in summary
        assert "time" in summary
        assert "people" in summary
        assert "alerts" in summary
        reporter.close()

    def test_balance_alert(self, db):
        crm = PeopleCRM(db)
        crm.add_person("A", "family_close")
        crm.add_person("B", "family_close")
        crm.log_interaction(2, "call")  # B contacted
        crm.close()

        reporter = Reporter(db)
        alert = reporter.balance_alert()
        assert "critical" in alert
        assert "warning" in alert
        assert alert["total_people"] == 2
        reporter.close()

    def test_alerts_generated(self, db):
        """Alerts should be generated for waste, neglected people, etc."""
        crm = PeopleCRM(db)
        # Add 4 people — all never contacted → triggers "osób wymaga kontaktu" alert (>3)
        for name in ["A", "B", "C", "D"]:
            crm.add_person(name, "family_close")
        crm.close()

        tracker = TimeTracker(db)
        # Create >60 min of waste (13 blocks × 5 min = 65 min)
        for _ in range(13):
            b = tracker.start("waste")
            tracker.stop(b)
        tracker.close()

        reporter = Reporter(db)
        briefing = reporter.daily_briefing()
        # Should have waste alert and people alert
        alert_messages = [a["message"] for a in briefing["alerts"]]
        assert any("zmarnowanego" in m for m in alert_messages)
        assert any("osób wymaga kontaktu" in m for m in alert_messages)
        reporter.close()


# ═══════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_database(self, db):
        """All operations should handle empty database gracefully."""
        tracker = TimeTracker(db)
        assert tracker.get_active_block() is None
        assert tracker.summary_today()["total_minutes"] == 0
        tracker.close()

        crm = PeopleCRM(db)
        assert crm.get_all_people() == []
        assert crm.get_neglected() == []
        assert crm.get_upcoming_birthdays() == []
        crm.close()

    def test_none_values(self, db):
        """Functions should handle None gracefully."""
        tracker = TimeTracker(db)
        block_id = tracker.start("work_deep")  # no optional params
        result = tracker.stop(block_id)  # no optional params
        assert result["focus"] is None
        assert result["satisfaction"] is None
        tracker.close()

    def test_multiple_active_blocks(self, db):
        """Starting a new block while one is active should work."""
        tracker = TimeTracker(db)
        tracker.start("work_deep")
        tracker.start("health")  # start another without stopping first

        active = tracker.get_active_block()
        assert active["category"] == "health"  # most recent
        tracker.close()

    def test_person_cascade_delete(self, db):
        """Deleting a person should cascade to interactions."""
        crm = PeopleCRM(db)
        pid = crm.add_person("Test", "friends")
        crm.log_interaction(pid, "call", duration_minutes=10)
        crm.delete_person(pid)

        # Interactions should be gone
        interactions = crm.get_interactions(person_id=pid)
        assert interactions == []
        crm.close()

    def test_birthday_edge_cases(self, db):
        """Birthdays with various formats."""
        crm = PeopleCRM(db)
        # Full date
        crm.add_person("Full", "friends", birthday="1990-05-15")
        # Just month-day (no year)
        crm.add_person("NoYear", "friends", birthday="0000-12-25")

        birthdays = crm.get_upcoming_birthdays(days_ahead=365)
        assert len(birthdays) >= 1  # at least the full date one
        crm.close()
