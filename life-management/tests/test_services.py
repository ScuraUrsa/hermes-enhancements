"""
Life Management System — Comprehensive Tests
==============================================
Tests for all services: TimeTracker, PeopleManager, HealthManager,
NutritionManager, MentalManager, EventManager, HobbyManager, DailyBriefing.

Uses in-memory SQLite for fast, isolated tests.

Author: Hermes Agent (Coder profile)
"""

import pytest
from datetime import date, time, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.models import (
    Base, TimeBlock, TimeCategory,
    Person, RelationshipType, Interaction, InteractionType,
    Medication, MedicationLog, Exercise, ExerciseIntensity,
    WeightLog, SleepLog,
    Meal, MealType, Recipe,
    IntrusiveThought, SnackingUrge, FocusSession,
    Event, Hobby, HobbySession,
)
from core.services import (
    TimeTracker, PeopleManager, HealthManager,
    NutritionManager, MentalManager, EventManager, HobbyManager,
    DailyBriefing,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """In-memory SQLite engine."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    """New session per test."""
    with Session(engine) as sess:
        yield sess


# ═══════════════════════════════════════════════════════════════════════════════
# TimeTracker Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimeTracker:
    """Testy dla TimeTracker."""

    def test_start_block_creates_5min_block(self, session):
        tracker = TimeTracker(session)
        block = tracker.start_block(
            category=TimeCategory.WORK,
            subcategory="coding",
            description="Working on life management system",
        )

        assert block.id is not None
        assert block.category == TimeCategory.WORK
        assert block.subcategory == "coding"
        assert block.duration_minutes >= 4  # może być 4-5 z powodu opóźnień
        assert block.duration_minutes <= 6

    def test_end_block_updates_end_time(self, session):
        tracker = TimeTracker(session)
        block = tracker.start_block(category=TimeCategory.WORK)

        # Symuluj upływ czasu
        block.start_time = datetime.now() - timedelta(minutes=25)
        session.commit()

        ended = tracker.end_block(block.id, energy_level=7, focus_level=8)
        assert ended is not None
        assert ended.energy_level == 7
        assert ended.focus_level == 8
        assert ended.duration_minutes >= 24

    def test_end_block_nonexistent_returns_none(self, session):
        tracker = TimeTracker(session)
        result = tracker.end_block(99999)
        assert result is None

    def test_get_blocks_for_day(self, session):
        tracker = TimeTracker(session)
        today = date.today()

        # Create blocks for today
        for i in range(3):
            block = tracker.start_block(category=TimeCategory.WORK)
            block.start_time = datetime.combine(today, time(9 + i, 0))
            block.end_time = datetime.combine(today, time(9 + i, 5))
            session.commit()

        blocks = tracker.get_blocks_for_day(today)
        assert len(blocks) == 3

    def test_get_daily_summary(self, session):
        tracker = TimeTracker(session)
        today = date.today()

        # 2h work, 1h health
        for _ in range(24):  # 24 * 5min = 2h
            block = tracker.start_block(category=TimeCategory.WORK)
            block.start_time = datetime.combine(today, time(9, 0))
            block.end_time = datetime.combine(today, time(9, 5))
            session.commit()

        for _ in range(12):  # 12 * 5min = 1h
            block = tracker.start_block(category=TimeCategory.HEALTH)
            block.start_time = datetime.combine(today, time(17, 0))
            block.end_time = datetime.combine(today, time(17, 5))
            session.commit()

        summary = tracker.get_daily_summary(today)
        assert summary["work"] == pytest.approx(2.0, abs=0.1)
        assert summary["health"] == pytest.approx(1.0, abs=0.1)

    def test_get_weekly_summary(self, session):
        tracker = TimeTracker(session)
        today = date.today()

        # One block per day for 7 days
        for days_ago in range(7):
            day = today - timedelta(days=days_ago)
            block = tracker.start_block(category=TimeCategory.WORK)
            block.start_time = datetime.combine(day, time(9, 0))
            block.end_time = datetime.combine(day, time(9, 5))
            session.commit()

        summary = tracker.get_weekly_summary()
        assert summary["work"] == pytest.approx(7 * 5 / 60, abs=0.1)

    def test_get_heatmap_data(self, session):
        tracker = TimeTracker(session)
        data = tracker.get_heatmap_data(days=7)
        assert len(data) == 7 * len(TimeCategory)
        for entry in data:
            assert "date" in entry
            assert "category" in entry
            assert "hours" in entry


# ═══════════════════════════════════════════════════════════════════════════════
# PeopleManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPeopleManager:
    """Testy dla PeopleManager."""

    def test_add_person(self, session):
        mgr = PeopleManager(session)
        person = mgr.add_person(
            name="Test User",
            relationship_type=RelationshipType.CLOSE_FRIEND,
            priority=8,
            birthday=date(1990, 5, 15),
        )

        assert person is not None
        assert person.name == "Test User"
        assert person.relationship_type == RelationshipType.CLOSE_FRIEND
        assert person.priority == 8
        assert person.contact_frequency_days == 7  # CLOSE_FRIEND default

    def test_add_person_max_limit(self, session):
        mgr = PeopleManager(session)
        # Add 50 people
        for i in range(50):
            mgr.add_person(
                name=f"Person {i}",
                relationship_type=RelationshipType.FRIEND,
            )

        # 51st should fail
        result = mgr.add_person(
            name="Person 51",
            relationship_type=RelationshipType.FRIEND,
        )
        assert result is None

    def test_get_all_active(self, session):
        mgr = PeopleManager(session)
        mgr.add_person("Active 1", RelationshipType.FRIEND)
        mgr.add_person("Active 2", RelationshipType.CLOSE_FAMILY)

        # Add inactive
        p = mgr.add_person("Inactive", RelationshipType.ACQUAINTANCE)
        p.active = False
        session.commit()

        active = mgr.get_all_active()
        assert len(active) == 2

    def test_get_overdue(self, session):
        mgr = PeopleManager(session)
        p = mgr.add_person("Overdue Person", RelationshipType.FRIEND)
        p.next_contact_due = date.today() - timedelta(days=5)
        session.commit()

        overdue = mgr.get_overdue()
        assert len(overdue) == 1
        assert overdue[0].name == "Overdue Person"

    def test_log_interaction_updates_contact_dates(self, session):
        mgr = PeopleManager(session)
        p = mgr.add_person("Test", RelationshipType.CLOSE_FRIEND)

        interaction = mgr.log_interaction(
            person_id=p.id,
            interaction_type=InteractionType.CALL,
            duration_minutes=30,
            quality=4,
        )

        assert interaction is not None
        assert interaction.duration_minutes == 30
        assert interaction.quality == 4

        # Refresh person
        session.refresh(p)
        assert p.last_contact == date.today()
        assert p.next_contact_due == date.today() + timedelta(days=7)

    def test_log_interaction_nonexistent_person(self, session):
        mgr = PeopleManager(session)
        result = mgr.log_interaction(99999, InteractionType.CALL)
        assert result is None

    def test_get_next_to_contact(self, session):
        mgr = PeopleManager(session)
        # Create people with different due dates
        p1 = mgr.add_person("Urgent", RelationshipType.CLOSE_FAMILY, priority=10)
        p1.next_contact_due = date.today() - timedelta(days=3)
        p2 = mgr.add_person("Soon", RelationshipType.FRIEND, priority=5)
        p2.next_contact_due = date.today() + timedelta(days=1)
        p3 = mgr.add_person("Later", RelationshipType.ACQUAINTANCE, priority=2)
        p3.next_contact_due = date.today() + timedelta(days=30)
        session.commit()

        next_up = mgr.get_next_to_contact(limit=2)
        assert len(next_up) == 2
        assert next_up[0].name == "Urgent"  # Most overdue first
        assert next_up[1].name == "Soon"

    def test_get_balance_score(self, session):
        mgr = PeopleManager(session)
        p1 = mgr.add_person("Friend 1", RelationshipType.FRIEND)
        p2 = mgr.add_person("Family 1", RelationshipType.CLOSE_FAMILY)

        # Log interactions
        mgr.log_interaction(p1.id, InteractionType.IN_PERSON, duration_minutes=60)
        mgr.log_interaction(p2.id, InteractionType.CALL, duration_minutes=30)

        balance = mgr.get_balance_score()
        assert "friend" in balance
        assert "close_family" in balance
        # 60 min friend, 30 min family = 66.7% friend, 33.3% family
        assert balance["friend"] == pytest.approx(66.7, abs=0.5)
        assert balance["close_family"] == pytest.approx(33.3, abs=0.5)

    def test_get_person_stats(self, session):
        mgr = PeopleManager(session)
        p = mgr.add_person("Stats Person", RelationshipType.FRIEND)
        mgr.log_interaction(p.id, InteractionType.CALL, duration_minutes=30, quality=4)
        mgr.log_interaction(p.id, InteractionType.IN_PERSON, duration_minutes=60, quality=5)

        stats = mgr.get_person_stats(p.id)
        assert stats is not None
        assert stats["interactions_30d"] == 2
        assert stats["total_minutes_30d"] == 90
        assert stats["avg_quality"] == 4.5

    def test_get_person_stats_nonexistent(self, session):
        mgr = PeopleManager(session)
        assert mgr.get_person_stats(99999) is None


# ═══════════════════════════════════════════════════════════════════════════════
# HealthManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthManager:
    """Testy dla HealthManager."""

    def test_add_medication(self, session):
        mgr = HealthManager(session)
        med = mgr.add_medication(
            name="Witamina D",
            dosage="4000 IU",
            frequency_per_day=1,
            time_of_day="08:00",
            stock_remaining=60,
        )

        assert med.id is not None
        assert med.name == "Witamina D"
        assert med.dosage == "4000 IU"
        assert med.stock_remaining == 60

    def test_log_medication_taken(self, session):
        mgr = HealthManager(session)
        med = mgr.add_medication("Test Med", stock_remaining=30)

        log = mgr.log_medication(med.id, skipped=False)
        assert log is not None
        assert log.skipped == False

        session.refresh(med)
        assert med.stock_remaining == 29

    def test_log_medication_skipped(self, session):
        mgr = HealthManager(session)
        med = mgr.add_medication("Test Med", stock_remaining=30)

        log = mgr.log_medication(med.id, skipped=True)
        assert log.skipped == True

        session.refresh(med)
        assert med.stock_remaining == 30  # Nie zmniejsza się przy pominięciu

    def test_log_medication_nonexistent(self, session):
        mgr = HealthManager(session)
        assert mgr.log_medication(99999) is None

    def test_get_missed_medications(self, session):
        mgr = HealthManager(session)
        med = mgr.add_medication("Test Med", frequency_per_day=2)

        # No logs yet — should be missed
        missed = mgr.get_missed_medications()
        assert len(missed) == 1
        assert missed[0].name == "Test Med"

        # Log one dose
        mgr.log_medication(med.id, skipped=False)
        missed = mgr.get_missed_medications()
        assert len(missed) == 1  # Still 1 missed (need 2 doses)

        # Log second dose
        mgr.log_medication(med.id, skipped=False)
        missed = mgr.get_missed_medications()
        assert len(missed) == 0  # All taken

    def test_get_low_stock(self, session):
        mgr = HealthManager(session)
        mgr.add_medication("Low Stock", stock_remaining=3)
        mgr.add_medication("OK Stock", stock_remaining=30)

        low = mgr.get_low_stock(threshold=7)
        assert len(low) == 1
        assert low[0].name == "Low Stock"

    def test_log_exercise(self, session):
        mgr = HealthManager(session)
        ex = mgr.log_exercise(
            exercise_type="Bieganie",
            duration_minutes=30,
            intensity=ExerciseIntensity.HIGH,
            calories_burned=350,
        )

        assert ex.id is not None
        assert ex.exercise_type == "Bieganie"
        assert ex.duration_minutes == 30
        assert ex.intensity == ExerciseIntensity.HIGH
        assert ex.calories_burned == 350

    def test_get_weekly_exercise(self, session):
        mgr = HealthManager(session)
        mgr.log_exercise("Bieganie", 30, ExerciseIntensity.HIGH, 350)
        mgr.log_exercise("Siłownia", 60, ExerciseIntensity.MEDIUM, 400)

        stats = mgr.get_weekly_exercise()
        assert stats["sessions"] == 2
        assert stats["total_minutes"] == 90
        assert stats["total_calories"] == 750

    def test_log_weight(self, session):
        mgr = HealthManager(session)
        wl = mgr.log_weight(80.5, notes="Rano, przed śniadaniem")

        assert wl.weight_kg == 80.5
        assert wl.date == date.today()

    def test_get_weight_trend(self, session):
        mgr = HealthManager(session)
        today = date.today()
        for days_ago in range(5):
            wl = WeightLog(
                date=today - timedelta(days=days_ago),
                weight_kg=80.0 - days_ago * 0.5,
            )
            session.add(wl)
        session.commit()

        trend = mgr.get_weight_trend(days=7)
        assert len(trend) >= 5

    def test_log_sleep(self, session):
        mgr = HealthManager(session)
        sl = mgr.log_sleep(
            bed_time=time(23, 0),
            wake_time=time(7, 0),
            quality=4,
        )

        assert sl.bed_time == time(23, 0)
        assert sl.wake_time == time(7, 0)
        assert sl.duration_hours == 8.0
        assert sl.quality == 4

    def test_sleep_duration_across_midnight(self, session):
        mgr = HealthManager(session)
        sl = mgr.log_sleep(
            bed_time=time(23, 30),
            wake_time=time(6, 30),
        )
        assert sl.duration_hours == 7.0

    def test_get_sleep_weekly_avg(self, session):
        mgr = HealthManager(session)
        today = date.today()
        for days_ago in range(7):
            sl = SleepLog(
                date=today - timedelta(days=days_ago),
                bed_time=time(23, 0),
                wake_time=time(7, 0),
                quality=4,
            )
            session.add(sl)
        session.commit()

        avg = mgr.get_sleep_weekly_avg()
        assert avg == 8.0


# ═══════════════════════════════════════════════════════════════════════════════
# NutritionManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestNutritionManager:
    """Testy dla NutritionManager."""

    def test_log_meal(self, session):
        mgr = NutritionManager(session)
        meal = mgr.log_meal(
            meal_type=MealType.BREAKFAST,
            description="Owsianka",
            calories=450,
            protein_g=15.0,
            carbs_g=60.0,
            fat_g=12.0,
            healthy_score=4,
        )

        assert meal.id is not None
        assert meal.meal_type == MealType.BREAKFAST
        assert meal.calories == 450
        assert meal.protein_g == 15.0

    def test_get_daily_calories(self, session):
        mgr = NutritionManager(session)
        mgr.log_meal(MealType.BREAKFAST, "A", calories=400)
        mgr.log_meal(MealType.LUNCH, "B", calories=600)
        mgr.log_meal(MealType.DINNER, "C", calories=500)

        total = mgr.get_daily_calories()
        assert total == 1500

    def test_get_daily_macros(self, session):
        mgr = NutritionManager(session)
        mgr.log_meal(MealType.BREAKFAST, "A", protein_g=20, carbs_g=50, fat_g=10, calories=400)
        mgr.log_meal(MealType.LUNCH, "B", protein_g=40, carbs_g=60, fat_g=15, calories=600)

        macros = mgr.get_daily_macros()
        assert macros["protein_g"] == 60.0
        assert macros["carbs_g"] == 110.0
        assert macros["fat_g"] == 25.0
        assert macros["calories"] == 1000

    def test_add_recipe(self, session):
        mgr = NutritionManager(session)
        recipe = mgr.add_recipe(
            name="Zdrowe curry",
            ingredients="Kurczak, mleko kokosowe, curry, ryż",
            instructions="1. Smaż kurczaka...",
            calories_per_serving=550,
            protein_g=35.0,
            prep_time_minutes=30,
            tags="obiad,fit,curry",
        )

        assert recipe.id is not None
        assert recipe.name == "Zdrowe curry"
        assert recipe.calories_per_serving == 550

    def test_get_favorite_recipes(self, session):
        mgr = NutritionManager(session)
        r1 = mgr.add_recipe("Fav 1", "ingredients", "instructions")
        r1.favorite = True
        r2 = mgr.add_recipe("Not Fav", "ingredients", "instructions")
        session.commit()

        favs = mgr.get_favorite_recipes()
        assert len(favs) == 1
        assert favs[0].name == "Fav 1"

    def test_get_healthy_score_weekly_avg(self, session):
        mgr = NutritionManager(session)
        mgr.log_meal(MealType.BREAKFAST, "A", healthy_score=4)
        mgr.log_meal(MealType.LUNCH, "B", healthy_score=5)

        avg = mgr.get_healthy_score_weekly_avg()
        assert avg == 4.5


# ═══════════════════════════════════════════════════════════════════════════════
# MentalManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestMentalManager:
    """Testy dla MentalManager."""

    def test_log_thought(self, session):
        mgr = MentalManager(session)
        thought = mgr.log_thought(
            thought="Martwię się o deadline",
            intensity=7,
            category="work",
        )

        assert thought.id is not None
        assert thought.thought == "Martwię się o deadline"
        assert thought.intensity == 7
        assert thought.resolved == False

    def test_resolve_thought(self, session):
        mgr = MentalManager(session)
        thought = mgr.log_thought("Test thought", 5)

        resolved = mgr.resolve_thought(thought.id, response="Przepracowałem to — deadline przesunięty")
        assert resolved is not None
        assert resolved.resolved == True
        assert resolved.response == "Przepracowałem to — deadline przesunięty"

    def test_resolve_thought_nonexistent(self, session):
        mgr = MentalManager(session)
        assert mgr.resolve_thought(99999, "response") is None

    def test_get_unresolved_thoughts(self, session):
        mgr = MentalManager(session)
        mgr.log_thought("Thought 1", 5)
        mgr.log_thought("Thought 2", 8)
        t3 = mgr.log_thought("Thought 3", 3)
        mgr.resolve_thought(t3.id, "Done")

        unresolved = mgr.get_unresolved_thoughts()
        assert len(unresolved) == 2
        # Sorted by intensity desc
        assert unresolved[0].intensity == 8

    def test_get_thought_trend(self, session):
        mgr = MentalManager(session)
        mgr.log_thought("T1", 5)
        mgr.log_thought("T2", 7)

        trend = mgr.get_thought_trend(days=7)
        assert len(trend) == 7
        today_entry = trend[-1]
        assert today_entry["count"] == 2
        assert today_entry["avg_intensity"] == 6.0

    def test_log_urge_resisted(self, session):
        mgr = MentalManager(session)
        urge = mgr.log_urge(
            trigger="stres",
            intensity=6,
            resisted=True,
            alternative_action="Wypiłem szklankę wody",
        )

        assert urge.id is not None
        assert urge.trigger == "stres"
        assert urge.resisted == True
        assert urge.alternative_action == "Wypiłem szklankę wody"

    def test_log_urge_gave_in(self, session):
        mgr = MentalManager(session)
        urge = mgr.log_urge(
            trigger="nuda",
            intensity=8,
            resisted=False,
        )

        assert urge.resisted == False

    def test_get_urge_stats(self, session):
        mgr = MentalManager(session)
        mgr.log_urge("stres", 5, True)
        mgr.log_urge("nuda", 7, False)
        mgr.log_urge("stres", 4, True)

        stats = mgr.get_urge_stats(days=7)
        assert stats["total"] == 3
        assert stats["resisted"] == 2
        assert stats["gave_in"] == 1
        assert stats["success_rate"] == pytest.approx(66.7, abs=0.5)
        assert stats["top_triggers"][0]["trigger"] == "stres"
        assert stats["top_triggers"][0]["count"] == 2

    def test_start_and_end_focus(self, session):
        mgr = MentalManager(session)
        fs = mgr.start_focus(task="Implementacja API", planned_minutes=25)

        assert fs.id is not None
        assert fs.task == "Implementacja API"
        assert fs.planned_duration_minutes == 25
        assert fs.end_time is None

        ended = mgr.end_focus(fs.id, interruptions=2, productivity_score=4)
        assert ended is not None
        assert ended.end_time is not None
        assert ended.interruptions == 2
        assert ended.productivity_score == 4

    def test_end_focus_nonexistent(self, session):
        mgr = MentalManager(session)
        assert mgr.end_focus(99999) is None

    def test_get_focus_stats(self, session):
        mgr = MentalManager(session)
        fs1 = mgr.start_focus("Task 1", 25)
        mgr.end_focus(fs1.id, interruptions=1, productivity_score=4)

        fs2 = mgr.start_focus("Task 2", 25)
        mgr.end_focus(fs2.id, interruptions=0, productivity_score=5)

        stats = mgr.get_focus_stats(days=7)
        assert stats["total_sessions"] == 2
        assert stats["completed"] == 2
        assert stats["avg_productivity"] == 4.5
        assert stats["total_interruptions"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# EventManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEventManager:
    """Testy dla EventManager."""

    def test_add_event(self, session):
        mgr = EventManager(session)
        event = mgr.add_event(
            title="Urodziny Mamy",
            event_date=date.today() + timedelta(days=10),
            event_type="birthday",
            recurring=True,
            reminder_days_before=7,
        )

        assert event.id is not None
        assert event.title == "Urodziny Mamy"
        assert event.days_until == 10
        assert event.recurring == True

    def test_get_upcoming(self, session):
        mgr = EventManager(session)
        today = date.today()

        mgr.add_event("Tomorrow", today + timedelta(days=1), "appointment")
        mgr.add_event("Next week", today + timedelta(days=7), "event")
        mgr.add_event("Next month", today + timedelta(days=35), "birthday")

        upcoming = mgr.get_upcoming(days=30)
        assert len(upcoming) == 2  # Tomorrow + Next week
        assert upcoming[0].title == "Tomorrow"

    def test_get_birthdays_this_month(self, session):
        mgr = EventManager(session)
        today = date.today()

        mgr.add_event(
            "Birthday this month",
            date(today.year, today.month, 15),
            "birthday",
        )
        mgr.add_event(
            "Birthday next month",
            date(today.year, today.month + 1 if today.month < 12 else 1, 1),
            "birthday",
        )

        birthdays = mgr.get_birthdays_this_month()
        assert len(birthdays) == 1
        assert birthdays[0].title == "Birthday this month"

    def test_needs_reminder(self, session):
        mgr = EventManager(session)
        today = date.today()

        # Event in 3 days, reminder 7 days before — should trigger
        event = mgr.add_event(
            "Soon event",
            today + timedelta(days=3),
            "appointment",
            reminder_days_before=7,
        )
        assert event.needs_reminder == True

        # Event in 30 days, reminder 7 days before — should NOT trigger
        event2 = mgr.add_event(
            "Far event",
            today + timedelta(days=30),
            "appointment",
            reminder_days_before=7,
        )
        assert event2.needs_reminder == False


# ═══════════════════════════════════════════════════════════════════════════════
# HobbyManager Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestHobbyManager:
    """Testy dla HobbyManager."""

    def test_add_hobby(self, session):
        mgr = HobbyManager(session)
        hobby = mgr.add_hobby(
            name="Gitara",
            category="muzyka",
            target_hours_per_week=3.0,
            notes="Nauka akordów",
        )

        assert hobby.id is not None
        assert hobby.name == "Gitara"
        assert hobby.target_hours_per_week == 3.0

    def test_log_session(self, session):
        mgr = HobbyManager(session)
        hobby = mgr.add_hobby("Bieganie", "sport", 4.0)

        hs = mgr.log_session(
            hobby_id=hobby.id,
            duration_minutes=45,
            enjoyment=4,
            notes="5km w parku",
        )

        assert hs is not None
        assert hs.duration_minutes == 45
        assert hs.enjoyment == 4

    def test_log_session_nonexistent_hobby(self, session):
        mgr = HobbyManager(session)
        assert mgr.log_session(99999, 30) is None

    def test_get_weekly_hobby_time(self, session):
        mgr = HobbyManager(session)
        h1 = mgr.add_hobby("Gitara", "muzyka", 3.0)
        h2 = mgr.add_hobby("Bieganie", "sport", 4.0)

        mgr.log_session(h1.id, 60)  # 1h
        mgr.log_session(h2.id, 30)  # 0.5h

        weekly = mgr.get_weekly_hobby_time()
        assert weekly["Gitara"] == 1.0
        assert weekly["Bieganie"] == 0.5

    def test_get_hobby_balance(self, session):
        mgr = HobbyManager(session)
        h1 = mgr.add_hobby("Gitara", "muzyka", 3.0)
        mgr.log_session(h1.id, 60)  # 1h, target 3h → deficit 2h

        balance = mgr.get_hobby_balance()
        assert len(balance) == 1
        assert balance[0]["name"] == "Gitara"
        assert balance[0]["actual_hours"] == 1.0
        assert balance[0]["target_hours"] == 3.0
        assert balance[0]["deficit"] == 2.0
        assert balance[0]["on_track"] == False


# ═══════════════════════════════════════════════════════════════════════════════
# DailyBriefing Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyBriefing:
    """Testy dla DailyBriefing."""

    def test_generate_returns_all_sections(self, session):
        # Seed minimal data
        pmgr = PeopleManager(session)
        hmgr = HealthManager(session)
        hmgr.add_medication("Test Med", frequency_per_day=1)
        pmgr.add_person("Test Person", RelationshipType.FRIEND)

        briefing = DailyBriefing(session)
        result = briefing.generate()

        assert "date" in result
        assert "medications" in result
        assert "people" in result
        assert "events" in result
        assert "mental" in result
        assert "focus" in result
        assert "hobbies" in result
        assert "yesterday_summary" in result

    def test_generate_detects_missed_medications(self, session):
        hmgr = HealthManager(session)
        hmgr.add_medication("Witamina D", frequency_per_day=1)

        briefing = DailyBriefing(session)
        result = briefing.generate()

        assert len(result["medications"]["missed"]) == 1
        assert result["medications"]["missed"][0]["name"] == "Witamina D"

    def test_generate_detects_overdue_people(self, session):
        pmgr = PeopleManager(session)
        p = pmgr.add_person("Overdue", RelationshipType.FRIEND)
        p.next_contact_due = date.today() - timedelta(days=3)
        session.commit()

        briefing = DailyBriefing(session)
        result = briefing.generate()

        assert len(result["people"]["overdue"]) == 1
        assert result["people"]["overdue"][0]["name"] == "Overdue"


# ═══════════════════════════════════════════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestModels:
    """Testy dla modeli."""

    def test_person_days_since_last_contact(self, session):
        p = Person(
            name="Test",
            relationship_type=RelationshipType.FRIEND,
            last_contact=date.today() - timedelta(days=5),
        )
        session.add(p)
        session.commit()

        assert p.days_since_last_contact == 5

    def test_person_is_overdue(self, session):
        p = Person(
            name="Test",
            relationship_type=RelationshipType.FRIEND,
            next_contact_due=date.today() - timedelta(days=1),
        )
        session.add(p)
        session.commit()

        assert p.is_overdue == True

    def test_person_not_overdue(self, session):
        p = Person(
            name="Test",
            relationship_type=RelationshipType.FRIEND,
            next_contact_due=date.today() + timedelta(days=5),
        )
        session.add(p)
        session.commit()

        assert p.is_overdue == False

    def test_event_days_until(self, session):
        e = Event(
            title="Test",
            event_date=date.today() + timedelta(days=10),
            event_type="birthday",
        )
        session.add(e)
        session.commit()

        assert e.days_until == 10

    def test_focus_session_completion_rate(self, session):
        fs = FocusSession(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now(),
            planned_duration_minutes=25,
            task="Test task",
        )
        session.add(fs)
        session.commit()

        assert fs.completion_rate == pytest.approx(0.8, abs=0.1)

    def test_sleep_log_duration(self, session):
        sl = SleepLog(
            date=date.today(),
            bed_time=time(23, 0),
            wake_time=time(6, 30),
        )
        session.add(sl)
        session.commit()

        assert sl.duration_hours == 7.5
