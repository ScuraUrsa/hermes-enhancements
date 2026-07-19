"""
Life Management System — Core Services
=======================================
Business logic layer for all life management domains.
Uses SQLAlchemy models from models.py.

Author: Hermes Agent (Coder profile)
"""

from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from .models import (
    Base, TimeBlock, TimeCategory,
    Person, RelationshipType, Interaction, InteractionType,
    Medication, MedicationLog, Exercise, ExerciseIntensity,
    WeightLog, SleepLog,
    Meal, MealType, Recipe,
    IntrusiveThought, SnackingUrge, FocusSession,
    Event, Hobby, HobbySession,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Time Tracking Service
# ═══════════════════════════════════════════════════════════════════════════════

class TimeTracker:
    """5-minutowy blokowy tracker czasu."""

    def __init__(self, session: Session):
        self.session = session

    def start_block(
        self,
        category: TimeCategory,
        subcategory: Optional[str] = None,
        description: Optional[str] = None,
        person_id: Optional[int] = None,
        hobby_id: Optional[int] = None,
    ) -> TimeBlock:
        """Rozpocznij nowy blok czasu (5-min)."""
        now = datetime.now()
        block = TimeBlock(
            start_time=now,
            end_time=now + timedelta(minutes=5),
            category=category,
            subcategory=subcategory,
            description=description,
            person_id=person_id,
            hobby_id=hobby_id,
        )
        self.session.add(block)
        self.session.commit()
        return block

    def end_block(
        self,
        block_id: int,
        energy_level: Optional[int] = None,
        focus_level: Optional[int] = None,
    ) -> Optional[TimeBlock]:
        """Zakończ blok — ustawia end_time na teraz."""
        block = self.session.get(TimeBlock, block_id)
        if block is None:
            return None
        block.end_time = datetime.now()
        if energy_level is not None:
            block.energy_level = energy_level
        if focus_level is not None:
            block.focus_level = focus_level
        self.session.commit()
        return block

    def get_blocks_for_day(self, day: Optional[date] = None) -> List[TimeBlock]:
        """Pobierz wszystkie bloki dla danego dnia."""
        if day is None:
            day = date.today()
        day_start = datetime.combine(day, time.min)
        day_end = datetime.combine(day, time.max)
        return (
            self.session.query(TimeBlock)
            .filter(TimeBlock.start_time >= day_start, TimeBlock.start_time <= day_end)
            .order_by(TimeBlock.start_time)
            .all()
        )

    def get_daily_summary(self, day: Optional[date] = None) -> Dict[str, float]:
        """Podsumowanie godzinowe per kategoria dla danego dnia."""
        blocks = self.get_blocks_for_day(day)
        summary: Dict[str, float] = defaultdict(float)
        for block in blocks:
            summary[block.category.value] += block.duration_minutes / 60.0
        return dict(summary)

    def get_weekly_summary(self) -> Dict[str, float]:
        """Podsumowanie godzinowe per kategoria dla bieżącego tygodnia."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        summary: Dict[str, float] = defaultdict(float)
        for i in range(7):
            day = week_start + timedelta(days=i)
            daily = self.get_daily_summary(day)
            for cat, hours in daily.items():
                summary[cat] += hours
        return dict(summary)

    def get_heatmap_data(self, days: int = 30) -> List[Dict]:
        """Dane do heatmapy — każdy dzień, każda kategoria, godziny."""
        today = date.today()
        start = today - timedelta(days=days - 1)
        result = []
        for i in range(days):
            day = start + timedelta(days=i)
            daily = self.get_daily_summary(day)
            for cat in TimeCategory:
                result.append({
                    "date": day.isoformat(),
                    "category": cat.value,
                    "hours": daily.get(cat.value, 0.0),
                })
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# People & Relationship Manager
# ═══════════════════════════════════════════════════════════════════════════════

class PeopleManager:
    """Zarządzanie 50 osobami — zbalansowana alokacja czasu."""

    MAX_PEOPLE = 50

    # Sugerowana częstotliwość kontaktu wg typu relacji
    FREQUENCY_MAP = {
        RelationshipType.CLOSE_FAMILY: 3,      # co 3 dni
        RelationshipType.EXTENDED_FAMILY: 14,   # co 2 tygodnie
        RelationshipType.CLOSE_FRIEND: 7,       # co tydzień
        RelationshipType.FRIEND: 21,            # co 3 tygodnie
        RelationshipType.ACQUAINTANCE: 60,      # co 2 miesiące
        RelationshipType.COLLEAGUE: 5,           # co 5 dni (praca)
    }

    def __init__(self, session: Session):
        self.session = session

    def add_person(
        self,
        name: str,
        relationship_type: RelationshipType,
        priority: int = 5,
        birthday: Optional[date] = None,
        notes: Optional[str] = None,
    ) -> Optional[Person]:
        """Dodaj osobę (max 50)."""
        count = self.session.query(func.count(Person.id)).scalar()
        if count >= self.MAX_PEOPLE:
            return None  # max reached

        person = Person(
            name=name,
            relationship_type=relationship_type,
            priority=priority,
            birthday=birthday,
            notes=notes,
            contact_frequency_days=self.FREQUENCY_MAP[relationship_type],
        )
        self.session.add(person)
        self.session.commit()
        return person

    def get_all_active(self) -> List[Person]:
        """Pobierz wszystkie aktywne osoby."""
        return (
            self.session.query(Person)
            .filter(Person.active == True)
            .order_by(Person.priority.desc(), Person.next_contact_due.asc())
            .all()
        )

    def get_overdue(self) -> List[Person]:
        """Osoby, z którymi kontakt jest zaległy."""
        today = date.today()
        return (
            self.session.query(Person)
            .filter(
                Person.active == True,
                Person.next_contact_due != None,
                Person.next_contact_due < today,
            )
            .order_by(Person.next_contact_due)
            .all()
        )

    def get_balance_score(self) -> Dict[str, float]:
        """
        Oblicza balans czasu między kategoriami relacji.
        Zwraca procent czasu spędzonego z każdą kategorią w ostatnich 30 dniach.
        """
        thirty_days_ago = date.today() - timedelta(days=30)
        people = self.get_all_active()

        # Grupuj osoby wg typu relacji
        by_type: Dict[RelationshipType, List[Person]] = defaultdict(list)
        for p in people:
            by_type[p.relationship_type].append(p)

        # Licz interakcje per typ
        interactions = (
            self.session.query(Interaction)
            .filter(Interaction.date >= thirty_days_ago)
            .all()
        )

        total_minutes = sum(i.duration_minutes or 0 for i in interactions)
        if total_minutes == 0:
            return {rt.value: 0.0 for rt in RelationshipType}

        by_type_minutes: Dict[str, int] = defaultdict(int)
        for i in interactions:
            person = self.session.get(Person, i.person_id)
            if person:
                by_type_minutes[person.relationship_type.value] += i.duration_minutes or 0

        return {
            rt.value: round(by_type_minutes[rt.value] / total_minutes * 100, 1)
            for rt in RelationshipType
        }

    def log_interaction(
        self,
        person_id: int,
        interaction_type: InteractionType,
        duration_minutes: Optional[int] = None,
        quality: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[Interaction]:
        """Zaloguj interakcję z osobą."""
        person = self.session.get(Person, person_id)
        if person is None:
            return None

        interaction = Interaction(
            person_id=person_id,
            date=date.today(),
            duration_minutes=duration_minutes,
            interaction_type=interaction_type,
            quality=quality,
            notes=notes,
        )
        self.session.add(interaction)

        # Aktualizuj last_contact i next_contact_due
        person.last_contact = date.today()
        if person.contact_frequency_days:
            person.next_contact_due = date.today() + timedelta(days=person.contact_frequency_days)

        self.session.commit()
        return interaction

    def get_next_to_contact(self, limit: int = 5) -> List[Person]:
        """Kto powinien być następny do kontaktu (posortowane po priorytecie i pilności)."""
        return (
            self.session.query(Person)
            .filter(Person.active == True)
            .order_by(
                Person.next_contact_due.asc().nulls_last(),
                Person.priority.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_person_stats(self, person_id: int) -> Optional[Dict]:
        """Statystyki dla jednej osoby."""
        person = self.session.get(Person, person_id)
        if person is None:
            return None

        thirty_days_ago = date.today() - timedelta(days=30)
        interactions = (
            self.session.query(Interaction)
            .filter(
                Interaction.person_id == person_id,
                Interaction.date >= thirty_days_ago,
            )
            .all()
        )

        total_minutes = sum(i.duration_minutes or 0 for i in interactions)
        avg_quality = (
            sum(i.quality for i in interactions if i.quality) / len([i for i in interactions if i.quality])
            if any(i.quality for i in interactions) else None
        )

        return {
            "person": person,
            "interactions_30d": len(interactions),
            "total_minutes_30d": total_minutes,
            "avg_quality": round(avg_quality, 1) if avg_quality else None,
            "days_since_last_contact": person.days_since_last_contact,
            "is_overdue": person.is_overdue,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Health Service
# ═══════════════════════════════════════════════════════════════════════════════

class HealthManager:
    """Zarządzanie zdrowiem — leki, ćwiczenia, waga, sen."""

    def __init__(self, session: Session):
        self.session = session

    # ── Medications ──────────────────────────────────────────────────────

    def add_medication(
        self,
        name: str,
        dosage: Optional[str] = None,
        frequency_per_day: int = 1,
        time_of_day: Optional[str] = None,
        stock_remaining: Optional[int] = None,
    ) -> Medication:
        """Dodaj lek/suplement."""
        med = Medication(
            name=name,
            dosage=dosage,
            frequency_per_day=frequency_per_day,
            time_of_day=time_of_day,
            stock_remaining=stock_remaining,
        )
        self.session.add(med)
        self.session.commit()
        return med

    def log_medication(
        self, medication_id: int, skipped: bool = False, notes: Optional[str] = None
    ) -> Optional[MedicationLog]:
        """Zaloguj przyjęcie/pominięcie leku."""
        med = self.session.get(Medication, medication_id)
        if med is None:
            return None

        log = MedicationLog(
            medication_id=medication_id,
            taken_at=datetime.now(),
            skipped=skipped,
            notes=notes,
        )
        self.session.add(log)

        if not skipped and med.stock_remaining is not None:
            med.stock_remaining -= 1

        self.session.commit()
        return log

    def get_missed_medications(self) -> List[Medication]:
        """Leki, które nie zostały dziś wzięte."""
        today = date.today()
        all_active = (
            self.session.query(Medication)
            .filter(Medication.active == True)
            .all()
        )

        missed = []
        for med in all_active:
            taken_today = (
                self.session.query(func.count(MedicationLog.id))
                .filter(
                    MedicationLog.medication_id == med.id,
                    MedicationLog.skipped == False,
                    func.date(MedicationLog.taken_at) == today,
                )
                .scalar()
            )
            if taken_today < med.frequency_per_day:
                missed.append(med)
        return missed

    def get_low_stock(self, threshold: int = 7) -> List[Medication]:
        """Leki z niskim stanem."""
        return (
            self.session.query(Medication)
            .filter(
                Medication.active == True,
                Medication.stock_remaining != None,
                Medication.stock_remaining <= threshold,
            )
            .all()
        )

    # ── Exercise ─────────────────────────────────────────────────────────

    def log_exercise(
        self,
        exercise_type: str,
        duration_minutes: int,
        intensity: ExerciseIntensity,
        calories_burned: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Exercise:
        """Zaloguj trening."""
        ex = Exercise(
            date=date.today(),
            exercise_type=exercise_type,
            duration_minutes=duration_minutes,
            intensity=intensity,
            calories_burned=calories_burned,
            notes=notes,
        )
        self.session.add(ex)
        self.session.commit()
        return ex

    def get_weekly_exercise(self) -> Dict:
        """Podsumowanie ćwiczeń w tym tygodniu."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        exercises = (
            self.session.query(Exercise)
            .filter(Exercise.date >= week_start, Exercise.date <= today)
            .all()
        )
        return {
            "sessions": len(exercises),
            "total_minutes": sum(e.duration_minutes for e in exercises),
            "total_calories": sum(e.calories_burned or 0 for e in exercises),
            "by_type": self._group_by_type(exercises),
        }

    def _group_by_type(self, exercises: List[Exercise]) -> Dict[str, int]:
        result: Dict[str, int] = defaultdict(int)
        for e in exercises:
            result[e.exercise_type] += e.duration_minutes
        return dict(result)

    # ── Weight ───────────────────────────────────────────────────────────

    def log_weight(self, weight_kg: float, notes: Optional[str] = None) -> WeightLog:
        """Zaloguj wagę."""
        wl = WeightLog(date=date.today(), weight_kg=weight_kg, notes=notes)
        self.session.add(wl)
        self.session.commit()
        return wl

    def get_weight_trend(self, days: int = 30) -> List[Dict]:
        """Trend wagi z ostatnich N dni."""
        start = date.today() - timedelta(days=days - 1)
        logs = (
            self.session.query(WeightLog)
            .filter(WeightLog.date >= start)
            .order_by(WeightLog.date)
            .all()
        )
        return [{"date": l.date.isoformat(), "weight_kg": l.weight_kg} for l in logs]

    # ── Sleep ────────────────────────────────────────────────────────────

    def log_sleep(
        self,
        bed_time: time,
        wake_time: time,
        quality: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> SleepLog:
        """Zaloguj sen."""
        sl = SleepLog(
            date=date.today(),
            bed_time=bed_time,
            wake_time=wake_time,
            quality=quality,
            notes=notes,
        )
        self.session.add(sl)
        self.session.commit()
        return sl

    def get_sleep_weekly_avg(self) -> Optional[float]:
        """Średnia długość snu w ostatnich 7 dniach."""
        week_ago = date.today() - timedelta(days=7)
        logs = (
            self.session.query(SleepLog)
            .filter(SleepLog.date >= week_ago)
            .all()
        )
        if not logs:
            return None
        return round(sum(l.duration_hours for l in logs) / len(logs), 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Nutrition Service
# ═══════════════════════════════════════════════════════════════════════════════

class NutritionManager:
    """Zarządzanie odżywianiem — posiłki, przepisy, kalorie."""

    def __init__(self, session: Session):
        self.session = session

    def log_meal(
        self,
        meal_type: MealType,
        description: str,
        calories: Optional[int] = None,
        protein_g: Optional[float] = None,
        carbs_g: Optional[float] = None,
        fat_g: Optional[float] = None,
        healthy_score: Optional[int] = None,
        was_snacking_urge: bool = False,
        notes: Optional[str] = None,
    ) -> Meal:
        """Zaloguj posiłek."""
        meal = Meal(
            date=date.today(),
            meal_type=meal_type,
            description=description,
            calories=calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            healthy_score=healthy_score,
            was_snacking_urge=was_snacking_urge,
            notes=notes,
        )
        self.session.add(meal)
        self.session.commit()
        return meal

    def get_daily_calories(self, day: Optional[date] = None) -> int:
        """Suma kalorii dla danego dnia."""
        if day is None:
            day = date.today()
        return (
            self.session.query(func.sum(Meal.calories))
            .filter(Meal.date == day, Meal.calories != None)
            .scalar()
        ) or 0

    def get_daily_macros(self, day: Optional[date] = None) -> Dict[str, float]:
        """Makra dla danego dnia."""
        if day is None:
            day = date.today()
        meals = self.session.query(Meal).filter(Meal.date == day).all()
        return {
            "protein_g": sum(m.protein_g or 0 for m in meals),
            "carbs_g": sum(m.carbs_g or 0 for m in meals),
            "fat_g": sum(m.fat_g or 0 for m in meals),
            "calories": sum(m.calories or 0 for m in meals),
        }

    def add_recipe(
        self,
        name: str,
        ingredients: str,
        instructions: str,
        calories_per_serving: Optional[int] = None,
        protein_g: Optional[float] = None,
        prep_time_minutes: Optional[int] = None,
        tags: Optional[str] = None,
    ) -> Recipe:
        """Dodaj przepis."""
        recipe = Recipe(
            name=name,
            ingredients=ingredients,
            instructions=instructions,
            calories_per_serving=calories_per_serving,
            protein_g=protein_g,
            prep_time_minutes=prep_time_minutes,
            tags=tags,
        )
        self.session.add(recipe)
        self.session.commit()
        return recipe

    def get_favorite_recipes(self) -> List[Recipe]:
        """Ulubione przepisy."""
        return self.session.query(Recipe).filter(Recipe.favorite == True).all()

    def get_healthy_score_weekly_avg(self) -> Optional[float]:
        """Średni healthy_score z ostatnich 7 dni."""
        week_ago = date.today() - timedelta(days=7)
        avg = (
            self.session.query(func.avg(Meal.healthy_score))
            .filter(Meal.date >= week_ago, Meal.healthy_score != None)
            .scalar()
        )
        return round(avg, 1) if avg else None


# ═══════════════════════════════════════════════════════════════════════════════
# Mental & Focus Service
# ═══════════════════════════════════════════════════════════════════════════════

class MentalManager:
    """Zarządzanie zdrowiem psychicznym — natarczywe myśli, podjadanie, focus."""

    def __init__(self, session: Session):
        self.session = session

    # ── Intrusive Thoughts ───────────────────────────────────────────────

    def log_thought(
        self,
        thought: str,
        intensity: int,
        category: Optional[str] = None,
    ) -> IntrusiveThought:
        """Zarejestruj natarczywą myśl."""
        it = IntrusiveThought(
            timestamp=datetime.now(),
            thought=thought,
            intensity=intensity,
            category=category,
        )
        self.session.add(it)
        self.session.commit()
        return it

    def resolve_thought(self, thought_id: int, response: str) -> Optional[IntrusiveThought]:
        """Oznacz myśl jako przepracowaną."""
        thought = self.session.get(IntrusiveThought, thought_id)
        if thought is None:
            return None
        thought.resolved = True
        thought.response = response
        self.session.commit()
        return thought

    def get_unresolved_thoughts(self) -> List[IntrusiveThought]:
        """Nieprzepracowane myśli."""
        return (
            self.session.query(IntrusiveThought)
            .filter(IntrusiveThought.resolved == False)
            .order_by(IntrusiveThought.intensity.desc())
            .all()
        )

    def get_thought_trend(self, days: int = 30) -> List[Dict]:
        """Trend natarczywych myśli — dzienna liczba i średnia intensywność."""
        start = date.today() - timedelta(days=days - 1)
        thoughts = (
            self.session.query(IntrusiveThought)
            .filter(func.date(IntrusiveThought.timestamp) >= start)
            .all()
        )
        by_day: Dict[date, List[IntrusiveThought]] = defaultdict(list)
        for t in thoughts:
            by_day[t.timestamp.date()].append(t)

        result = []
        for i in range(days):
            day = start + timedelta(days=i)
            day_thoughts = by_day.get(day, [])
            result.append({
                "date": day.isoformat(),
                "count": len(day_thoughts),
                "avg_intensity": (
                    round(sum(t.intensity for t in day_thoughts) / len(day_thoughts), 1)
                    if day_thoughts else 0
                ),
            })
        return result

    # ── Snacking Urges ───────────────────────────────────────────────────

    def log_urge(
        self,
        trigger: str,
        intensity: int,
        resisted: bool,
        alternative_action: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> SnackingUrge:
        """Zarejestruj odruch podjadania."""
        urge = SnackingUrge(
            timestamp=datetime.now(),
            trigger=trigger,
            intensity=intensity,
            resisted=resisted,
            alternative_action=alternative_action,
            notes=notes,
        )
        self.session.add(urge)
        self.session.commit()
        return urge

    def get_urge_stats(self, days: int = 7) -> Dict:
        """Statystyki podjadania z ostatnich N dni."""
        start = date.today() - timedelta(days=days - 1)
        urges = (
            self.session.query(SnackingUrge)
            .filter(func.date(SnackingUrge.timestamp) >= start)
            .all()
        )
        total = len(urges)
        resisted = sum(1 for u in urges if u.resisted)
        return {
            "total": total,
            "resisted": resisted,
            "gave_in": total - resisted,
            "success_rate": round(resisted / total * 100, 1) if total > 0 else 100.0,
            "top_triggers": self._top_triggers(urges),
        }

    def _top_triggers(self, urges: List[SnackingUrge], limit: int = 3) -> List[Dict]:
        counter: Dict[str, int] = defaultdict(int)
        for u in urges:
            counter[u.trigger] += 1
        return sorted(
            [{"trigger": k, "count": v} for k, v in counter.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]

    # ── Focus Sessions ───────────────────────────────────────────────────

    def start_focus(self, task: str, planned_minutes: int = 25) -> FocusSession:
        """Rozpocznij sesję skupienia."""
        fs = FocusSession(
            start_time=datetime.now(),
            planned_duration_minutes=planned_minutes,
            task=task,
        )
        self.session.add(fs)
        self.session.commit()
        return fs

    def end_focus(
        self,
        session_id: int,
        interruptions: int = 0,
        productivity_score: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[FocusSession]:
        """Zakończ sesję skupienia."""
        fs = self.session.get(FocusSession, session_id)
        if fs is None:
            return None
        fs.end_time = datetime.now()
        fs.interruptions = interruptions
        fs.productivity_score = productivity_score
        fs.notes = notes
        self.session.commit()
        return fs

    def get_focus_stats(self, days: int = 7) -> Dict:
        """Statystyki focusu z ostatnich N dni."""
        start = date.today() - timedelta(days=days - 1)
        sessions = (
            self.session.query(FocusSession)
            .filter(func.date(FocusSession.start_time) >= start)
            .all()
        )
        completed = [s for s in sessions if s.end_time is not None]
        return {
            "total_sessions": len(sessions),
            "completed": len(completed),
            "total_focus_minutes": sum(
                (s.actual_duration_minutes or 0) for s in completed
            ),
            "avg_productivity": (
                round(
                    sum(s.productivity_score for s in completed if s.productivity_score)
                    / len([s for s in completed if s.productivity_score]),
                    1,
                )
                if any(s.productivity_score for s in completed)
                else None
            ),
            "total_interruptions": sum(s.interruptions for s in completed),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Events Service
# ═══════════════════════════════════════════════════════════════════════════════

class EventManager:
    """Zarządzanie wydarzeniami — urodziny, rocznice, spotkania."""

    def __init__(self, session: Session):
        self.session = session

    def add_event(
        self,
        title: str,
        event_date: date,
        event_type: str,
        person_id: Optional[int] = None,
        recurring: bool = False,
        reminder_days_before: int = 7,
        notes: Optional[str] = None,
    ) -> Event:
        """Dodaj wydarzenie."""
        event = Event(
            person_id=person_id,
            title=title,
            event_date=event_date,
            event_type=event_type,
            recurring=recurring,
            reminder_days_before=reminder_days_before,
            notes=notes,
        )
        self.session.add(event)
        self.session.commit()
        return event

    def get_upcoming(self, days: int = 30) -> List[Event]:
        """Nadchodzące wydarzenia w ciągu N dni."""
        today = date.today()
        cutoff = today + timedelta(days=days)
        return (
            self.session.query(Event)
            .filter(Event.event_date >= today, Event.event_date <= cutoff)
            .order_by(Event.event_date)
            .all()
        )

    def get_needing_reminder(self) -> List[Event]:
        """Wydarzenia wymagające przypomnienia."""
        return (
            self.session.query(Event)
            .filter(Event.event_date >= date.today())
            .order_by(Event.event_date)
            .all()
        )

    def get_birthdays_this_month(self) -> List[Event]:
        """Urodziny w tym miesiącu."""
        today = date.today()
        return (
            self.session.query(Event)
            .filter(
                Event.event_type == "birthday",
                func.extract("month", Event.event_date) == today.month,
            )
            .order_by(Event.event_date)
            .all()
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Hobbies Service
# ═══════════════════════════════════════════════════════════════════════════════

class HobbyManager:
    """Zarządzanie hobby."""

    def __init__(self, session: Session):
        self.session = session

    def add_hobby(
        self,
        name: str,
        category: Optional[str] = None,
        target_hours_per_week: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> Hobby:
        """Dodaj hobby."""
        hobby = Hobby(
            name=name,
            category=category,
            target_hours_per_week=target_hours_per_week,
            notes=notes,
        )
        self.session.add(hobby)
        self.session.commit()
        return hobby

    def log_session(
        self,
        hobby_id: int,
        duration_minutes: int,
        enjoyment: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Optional[HobbySession]:
        """Zaloguj sesję hobby."""
        hobby = self.session.get(Hobby, hobby_id)
        if hobby is None:
            return None

        session = HobbySession(
            hobby_id=hobby_id,
            date=date.today(),
            duration_minutes=duration_minutes,
            enjoyment=enjoyment,
            notes=notes,
        )
        self.session.add(session)
        self.session.commit()
        return session

    def get_weekly_hobby_time(self) -> Dict[str, float]:
        """Czas spędzony na hobby w tym tygodniu."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        sessions = (
            self.session.query(HobbySession)
            .filter(HobbySession.date >= week_start, HobbySession.date <= today)
            .all()
        )
        by_hobby: Dict[str, float] = defaultdict(float)
        for s in sessions:
            hobby = self.session.get(Hobby, s.hobby_id)
            if hobby:
                by_hobby[hobby.name] += s.duration_minutes / 60.0
        return dict(by_hobby)

    def get_hobby_balance(self) -> List[Dict]:
        """Balans czasu hobby vs target."""
        hobbies = self.session.query(Hobby).filter(Hobby.active == True).all()
        weekly = self.get_weekly_hobby_time()
        result = []
        for h in hobbies:
            actual = weekly.get(h.name, 0.0)
            target = h.target_hours_per_week or 0
            result.append({
                "name": h.name,
                "actual_hours": actual,
                "target_hours": target,
                "deficit": target - actual,
                "on_track": actual >= target if target > 0 else True,
            })
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# Daily Briefing Generator
# ═══════════════════════════════════════════════════════════════════════════════

class DailyBriefing:
    """Generuje codzienny raport — co trzeba dziś zrobić."""

    def __init__(self, session: Session):
        self.session = session
        self.time = TimeTracker(session)
        self.people = PeopleManager(session)
        self.health = HealthManager(session)
        self.mental = MentalManager(session)
        self.events = EventManager(session)
        self.hobbies = HobbyManager(session)

    def generate(self) -> Dict:
        """Generuj pełny daily briefing."""
        today = date.today()

        return {
            "date": today.isoformat(),
            "medications": {
                "missed": [
                    {"name": m.name, "dosage": m.dosage, "frequency": m.frequency_per_day}
                    for m in self.health.get_missed_medications()
                ],
                "low_stock": [
                    {"name": m.name, "remaining": m.stock_remaining}
                    for m in self.health.get_low_stock()
                ],
            },
            "people": {
                "overdue": [
                    {"name": p.name, "days_overdue": (today - p.next_contact_due).days if p.next_contact_due else None}
                    for p in self.people.get_overdue()
                ],
                "next_to_contact": [
                    {"name": p.name, "type": p.relationship_type.value, "due": p.next_contact_due.isoformat() if p.next_contact_due else None}
                    for p in self.people.get_next_to_contact(limit=5)
                ],
            },
            "events": {
                "today": [
                    {"title": e.title, "type": e.event_type}
                    for e in self.events.get_upcoming(days=0)
                ],
                "upcoming_7d": [
                    {"title": e.title, "date": e.event_date.isoformat(), "days_until": e.days_until}
                    for e in self.events.get_upcoming(days=7)
                ],
            },
            "mental": {
                "unresolved_thoughts": len(self.mental.get_unresolved_thoughts()),
                "urge_stats": self.mental.get_urge_stats(days=1),
            },
            "focus": self.mental.get_focus_stats(days=1),
            "hobbies": {
                "balance": self.hobbies.get_hobby_balance(),
            },
            "yesterday_summary": self.time.get_daily_summary(today - timedelta(days=1)),
        }
