"""
Life Management System — Database Initialization & Seed Data
=============================================================
Creates the SQLite database and populates it with realistic seed data
for testing and demonstration.

Author: Hermes Agent (Coder profile)
"""

import sys
import os
from datetime import date, time, datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.models import (
    init_db, get_session, create_engine_sqlite,
    TimeCategory, RelationshipType, InteractionType,
    MealType, ExerciseIntensity,
    TimeBlock, Interaction,
)
from core.services import (
    TimeTracker, PeopleManager, HealthManager,
    NutritionManager, MentalManager, EventManager, HobbyManager,
)


DB_PATH = os.environ.get("LIFE_MANAGEMENT_DB", str(Path(__file__).parent / "life_management.db"))


def seed_people(mgr: PeopleManager) -> list:
    """Seed 50 osób z różnymi typami relacji."""
    people_data = [
        # ── CLOSE FAMILY (5) ──────────────────────────────────────────
        ("Mama", RelationshipType.CLOSE_FAMILY, 10, date(1965, 3, 15)),
        ("Tata", RelationshipType.CLOSE_FAMILY, 10, date(1963, 8, 22)),
        ("Kasia (siostra)", RelationshipType.CLOSE_FAMILY, 9, date(1995, 11, 3)),
        ("Babcia Zosia", RelationshipType.CLOSE_FAMILY, 8, date(1940, 5, 10)),
        ("Dziadek Janek", RelationshipType.CLOSE_FAMILY, 8, date(1938, 12, 1)),

        # ── EXTENDED FAMILY (8) ───────────────────────────────────────
        ("Wujek Marek", RelationshipType.EXTENDED_FAMILY, 6, date(1970, 7, 14)),
        ("Ciocia Basia", RelationshipType.EXTENDED_FAMILY, 6, date(1972, 4, 8)),
        ("Kuzyn Tomek", RelationshipType.EXTENDED_FAMILY, 5, date(1998, 9, 20)),
        ("Kuzynka Ania", RelationshipType.EXTENDED_FAMILY, 5, date(2000, 2, 14)),
        ("Ciocia Krysia", RelationshipType.EXTENDED_FAMILY, 5, date(1968, 6, 30)),
        ("Wujek Staszek", RelationshipType.EXTENDED_FAMILY, 4, date(1966, 1, 25)),
        ("Babcia Hela", RelationshipType.EXTENDED_FAMILY, 6, date(1942, 10, 5)),
        ("Dziadek Franek", RelationshipType.EXTENDED_FAMILY, 5, date(1941, 3, 18)),

        # ── CLOSE FRIENDS (7) ─────────────────────────────────────────
        ("Michał", RelationshipType.CLOSE_FRIEND, 9, date(1993, 5, 22)),
        ("Ola", RelationshipType.CLOSE_FRIEND, 8, date(1994, 12, 7)),
        ("Kuba", RelationshipType.CLOSE_FRIEND, 8, date(1992, 8, 11)),
        ("Magda", RelationshipType.CLOSE_FRIEND, 7, date(1995, 3, 28)),
        ("Piotrek", RelationshipType.CLOSE_FRIEND, 7, date(1993, 11, 15)),
        ("Agnieszka", RelationshipType.CLOSE_FRIEND, 7, date(1994, 7, 3)),
        ("Łukasz", RelationshipType.CLOSE_FRIEND, 8, date(1992, 1, 19)),

        # ── FRIENDS (15) ──────────────────────────────────────────────
        ("Karolina", RelationshipType.FRIEND, 6, date(1996, 4, 12)),
        ("Bartek", RelationshipType.FRIEND, 6, date(1994, 9, 8)),
        ("Ewa", RelationshipType.FRIEND, 5, date(1995, 6, 25)),
        ("Marcin", RelationshipType.FRIEND, 5, date(1993, 2, 14)),
        ("Natalia", RelationshipType.FRIEND, 5, date(1997, 10, 30)),
        ("Rafał", RelationshipType.FRIEND, 5, date(1992, 12, 3)),
        ("Dominika", RelationshipType.FRIEND, 4, date(1996, 8, 17)),
        ("Tomek", RelationshipType.FRIEND, 4, date(1994, 5, 9)),
        ("Paulina", RelationshipType.FRIEND, 4, date(1995, 1, 22)),
        ("Krzysiek", RelationshipType.FRIEND, 4, date(1993, 7, 6)),
        ("Monika", RelationshipType.FRIEND, 3, date(1997, 3, 11)),
        ("Adam", RelationshipType.FRIEND, 3, date(1994, 11, 28)),
        ("Joanna", RelationshipType.FRIEND, 3, date(1996, 9, 4)),
        ("Wojtek", RelationshipType.FRIEND, 3, date(1993, 6, 19)),
        ("Sylwia", RelationshipType.FRIEND, 3, date(1995, 4, 15)),

        # ── ACQUAINTANCES (10) ────────────────────────────────────────
        ("Marek z siłowni", RelationshipType.ACQUAINTANCE, 2, None),
        ("Ania z jogi", RelationshipType.ACQUAINTANCE, 2, None),
        ("Sąsiad Zbyszek", RelationshipType.ACQUAINTANCE, 3, date(1960, 2, 8)),
        ("Sąsiadka Halina", RelationshipType.ACQUAINTANCE, 3, date(1962, 9, 14)),
        ("Kolega z kursu", RelationshipType.ACQUAINTANCE, 2, None),
        ("Znajomy z konferencji", RelationshipType.ACQUAINTANCE, 1, None),
        ("Trener personalny", RelationshipType.ACQUAINTANCE, 2, None),
        ("Lekarz rodzinny", RelationshipType.ACQUAINTANCE, 3, None),
        ("Fryzjer", RelationshipType.ACQUAINTANCE, 1, None),
        ("Barista z ulubionej kawiarni", RelationshipType.ACQUAINTANCE, 1, None),

        # ── COLLEAGUES (5) ────────────────────────────────────────────
        ("Szef — Robert", RelationshipType.COLLEAGUE, 7, date(1980, 10, 5)),
        ("Kolega z zespołu — Darek", RelationshipType.COLLEAGUE, 6, date(1990, 4, 20)),
        ("Koleżanka z zespołu — Marta", RelationshipType.COLLEAGUE, 6, date(1991, 8, 12)),
        ("PM — Kasia", RelationshipType.COLLEAGUE, 5, date(1988, 6, 3)),
        ("Stażysta — Kamil", RelationshipType.COLLEAGUE, 3, date(2000, 1, 15)),
    ]

    created = []
    for name, rel_type, priority, birthday in people_data:
        person = mgr.add_person(
            name=name,
            relationship_type=rel_type,
            priority=priority,
            birthday=birthday,
        )
        if person:
            created.append(person)
    return created


def seed_medications(mgr: HealthManager) -> list:
    """Seed leków i suplementów."""
    meds_data = [
        ("Witamina D3", "4000 IU", 1, "08:00", 60),
        ("Magnez", "200mg", 1, "20:00", 30),
        ("Omega-3", "1000mg", 2, "08:00,20:00", 45),
        ("Witamina B Complex", "1 tabletka", 1, "08:00", 20),
        ("Melatonina", "3mg", 1, "21:00", 15),
    ]

    created = []
    for name, dosage, freq, time_of_day, stock in meds_data:
        med = mgr.add_medication(
            name=name,
            dosage=dosage,
            frequency_per_day=freq,
            time_of_day=time_of_day,
            stock_remaining=stock,
        )
        created.append(med)
    return created


def seed_hobbies(mgr: HobbyManager) -> list:
    """Seed hobby."""
    hobbies_data = [
        ("Gitara", "muzyka", 3.0, "Nauka gry na gitarze akustycznej"),
        ("Bieganie", "sport", 4.0, "3x w tygodniu po 5km"),
        ("Czytanie", "rozwój", 5.0, "Minimum 30 min dziennie"),
        ("Gotowanie", "kulinaria", 3.0, "Nowe przepisy co tydzień"),
        ("Fotografia", "sztuka", 2.0, "Weekendowe spacery z aparatem"),
        ("Szachy", "gry", 2.0, "Online + klub raz w tygodniu"),
    ]

    created = []
    for name, category, target_hours, notes in hobbies_data:
        hobby = mgr.add_hobby(
            name=name,
            category=category,
            target_hours_per_week=target_hours,
            notes=notes,
        )
        created.append(hobby)
    return created


def seed_events(mgr: EventManager, people: list) -> list:
    """Seed wydarzeń — urodziny, rocznice."""
    today = date.today()
    created = []

    # Urodziny z seedowanych osób
    for person in people:
        if person.birthday:
            # Ustaw datę urodzin na ten rok
            birthday_this_year = date(today.year, person.birthday.month, person.birthday.day)
            if birthday_this_year < today:
                birthday_this_year = date(today.year + 1, person.birthday.month, person.birthday.day)

            event = mgr.add_event(
                title=f"Urodziny: {person.name}",
                event_date=birthday_this_year,
                event_type="birthday",
                person_id=person.id,
                recurring=True,
                reminder_days_before=7,
            )
            created.append(event)

    # Dodatkowe wydarzenia
    extra_events = [
        ("Rocznica ślubu rodziców", today + timedelta(days=45), "anniversary", 14),
        ("Wizyta u dentysty", today + timedelta(days=3), "appointment", 1),
        ("Deadline projektu", today + timedelta(days=10), "deadline", 3),
        ("Koncert ulubionego zespołu", today + timedelta(days=25), "event", 7),
        ("Badania kontrolne", today + timedelta(days=60), "appointment", 7),
    ]

    for title, event_date, event_type, reminder_days in extra_events:
        event = mgr.add_event(
            title=title,
            event_date=event_date,
            event_type=event_type,
            reminder_days_before=reminder_days,
        )
        created.append(event)

    return created


def seed_sample_data(session) -> None:
    """Seed all sample data."""
    print("🌱 Seeding database...")

    # Managers
    people_mgr = PeopleManager(session)
    health_mgr = HealthManager(session)
    hobby_mgr = HobbyManager(session)
    event_mgr = EventManager(session)
    nutrition_mgr = NutritionManager(session)
    mental_mgr = MentalManager(session)
    time_mgr = TimeTracker(session)

    # Seed people
    people = seed_people(people_mgr)
    print(f"  ✅ {len(people)} people seeded")

    # Seed medications
    meds = seed_medications(health_mgr)
    print(f"  ✅ {len(meds)} medications seeded")

    # Seed hobbies
    hobbies = seed_hobbies(hobby_mgr)
    print(f"  ✅ {len(hobbies)} hobbies seeded")

    # Seed events
    events = seed_events(event_mgr, people)
    print(f"  ✅ {len(events)} events seeded")

    # Seed some sample time blocks for the past week
    today = date.today()
    for days_ago in range(7, 0, -1):
        day = today - timedelta(days=days_ago)
        day_start = datetime.combine(day, time(8, 0))

        # Work blocks
        for i in range(8):
            block = TimeBlock(
                start_time=day_start + timedelta(hours=i),
                end_time=day_start + timedelta(hours=i, minutes=55),
                category=TimeCategory.WORK,
                subcategory="coding",
                energy_level=7,
                focus_level=8,
            )
            session.add(block)

        # Health block
        session.add(TimeBlock(
            start_time=day_start + timedelta(hours=17),
            end_time=day_start + timedelta(hours=18),
            category=TimeCategory.HEALTH,
            subcategory="exercise",
        ))

        # Relationships block
        session.add(TimeBlock(
            start_time=day_start + timedelta(hours=19),
            end_time=day_start + timedelta(hours=20, minutes=30),
            category=TimeCategory.RELATIONSHIPS,
            person_id=people[0].id if people else None,
        ))

    session.commit()
    print(f"  ✅ Sample time blocks seeded (7 days)")

    # Seed some interactions
    for i, person in enumerate(people[:10]):
        interaction = Interaction(
            person_id=person.id,
            date=today - timedelta(days=i % 7),
            duration_minutes=30 + (i * 5),
            interaction_type=InteractionType.CALL if i % 2 == 0 else InteractionType.IN_PERSON,
            quality=4,
        )
        session.add(interaction)
    session.commit()
    print(f"  ✅ 10 sample interactions seeded")

    # Seed some meals
    meals_sample = [
        (MealType.BREAKFAST, "Owsianka z bananem i orzechami", 450, 15, 60, 12, 4),
        (MealType.LUNCH, "Kurczak z ryżem i warzywami", 650, 45, 55, 18, 4),
        (MealType.DINNER, "Łosoś z kaszą i szparagami", 550, 40, 35, 22, 5),
        (MealType.SNACK, "Jabłko + garść migdałów", 200, 6, 25, 12, 4),
    ]
    for meal_type, desc, cal, prot, carb, fat, score in meals_sample:
        nutrition_mgr.log_meal(
            meal_type=meal_type,
            description=desc,
            calories=cal,
            protein_g=prot,
            carbs_g=carb,
            fat_g=fat,
            healthy_score=score,
        )
    print(f"  ✅ {len(meals_sample)} sample meals seeded")

    # Seed some focus sessions
    for i in range(3):
        fs = mental_mgr.start_focus(f"Deep work session #{i+1}", planned_minutes=25)
        mental_mgr.end_focus(fs.id, interruptions=i, productivity_score=4)
    print(f"  ✅ 3 focus sessions seeded")

    print("🎉 Database seeded successfully!")


def main():
    """Initialize database and seed data."""
    print(f"📦 Database path: {DB_PATH}")

    engine = create_engine_sqlite(DB_PATH)
    init_db(engine)
    print("✅ Tables created")

    session = get_session(engine)
    try:
        seed_sample_data(session)
    finally:
        session.close()

    print(f"\n📊 Database ready at: {DB_PATH}")
    print(f"   Size: {os.path.getsize(DB_PATH):,} bytes")


if __name__ == "__main__":
    main()
