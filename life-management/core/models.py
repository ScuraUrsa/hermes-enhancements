"""
Life Management System — Core Data Model
=========================================
SQLAlchemy models for all life management domains:
- Time tracking (5-min blocks)
- People & relationships (50-person balanced allocation)
- Health (medications, exercise, weight, sleep)
- Nutrition (meals, recipes, fasting)
- Mental (intrusive thoughts, snacking urges, focus)
- Events (birthdays, important dates, reminders)
- Hobbies (tracking, time allocation)

Author: Hermes Agent (Coder profile)
Repo: ScuraUrsa/hermes-enhancements/life-management
"""

from datetime import datetime, date, time
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, Time, DateTime,
    ForeignKey, Text, Enum as SAEnum, create_engine, Index, CheckConstraint
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, Session
)
from sqlalchemy.sql import func


# ── Base ────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Enums ───────────────────────────────────────────────────────────────────

class RelationshipType(str, Enum):
    CLOSE_FAMILY = "close_family"       # rodzina bliższa
    EXTENDED_FAMILY = "extended_family" # rodzina dalsza
    CLOSE_FRIEND = "close_friend"       # bliski przyjaciel
    FRIEND = "friend"                   # znajomy
    ACQUAINTANCE = "acquaintance"       # dalszy znajomy
    COLLEAGUE = "colleague"             # współpracownik


class InteractionType(str, Enum):
    IN_PERSON = "in_person"
    CALL = "call"
    VIDEO = "video"
    MESSAGE = "message"


class TimeCategory(str, Enum):
    WORK = "work"
    HEALTH = "health"
    RELATIONSHIPS = "relationships"
    NUTRITION = "nutrition"
    HOBBIES = "hobbies"
    PERSONAL_DEV = "personal_dev"
    REST = "rest"
    ADMIN = "admin"
    TRANSPORT = "transport"
    OTHER = "other"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    FASTING = "fasting"


class ExerciseIntensity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Time Tracking ───────────────────────────────────────────────────────────

class TimeBlock(Base):
    """5-minutowy blok czasu — podstawowa jednostka trackingu."""
    __tablename__ = "time_blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    category: Mapped[TimeCategory] = mapped_column(SAEnum(TimeCategory), nullable=False, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    energy_level: Mapped[Optional[int]] = mapped_column(Integer)  # 1-10
    focus_level: Mapped[Optional[int]] = mapped_column(Integer)    # 1-10
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.id"))
    hobby_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hobbies.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    person: Mapped[Optional["Person"]] = relationship(back_populates="time_blocks")
    hobby: Mapped[Optional["Hobby"]] = relationship(back_populates="time_blocks")

    __table_args__ = (
        Index("ix_time_blocks_date", "start_time"),
        CheckConstraint("end_time > start_time", name="ck_time_block_order"),
    )

    @property
    def duration_minutes(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() / 60)

    def __repr__(self) -> str:
        return f"<TimeBlock {self.start_time:%Y-%m-%d %H:%M} [{self.category.value}] {self.duration_minutes}min>"


# ── People & Relationships ─────────────────────────────────────────────────

class Person(Base):
    """Osoba w życiu użytkownika — max 50, zbalansowana alokacja czasu."""
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType), nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    last_contact: Mapped[Optional[date]] = mapped_column(Date)
    next_contact_due: Mapped[Optional[date]] = mapped_column(Date, index=True)
    contact_frequency_days: Mapped[Optional[int]] = mapped_column(Integer)  # co ile dni kontakt
    birthday: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    interactions: Mapped[List["Interaction"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    time_blocks: Mapped[List["TimeBlock"]] = relationship(back_populates="person")
    events: Mapped[List["Event"]] = relationship(back_populates="person")

    __table_args__ = (
        Index("ix_people_next_contact", "next_contact_due"),
    )

    @property
    def days_since_last_contact(self) -> Optional[int]:
        if self.last_contact is None:
            return None
        return (date.today() - self.last_contact).days

    @property
    def is_overdue(self) -> bool:
        if self.next_contact_due is None:
            return False
        return date.today() > self.next_contact_due

    @property
    def total_hours_this_month(self) -> float:
        """Suma godzin spędzonych z tą osobą w bieżącym miesiącu."""
        # computed in service layer
        return 0.0

    def __repr__(self) -> str:
        return f"<Person {self.name} [{self.relationship_type.value}] prio={self.priority}>"


class Interaction(Base):
    """Pojedyncza interakcja z osobą."""
    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    interaction_type: Mapped[InteractionType] = mapped_column(
        SAEnum(InteractionType), nullable=False
    )
    quality: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    person: Mapped["Person"] = relationship(back_populates="interactions")

    def __repr__(self) -> str:
        return f"<Interaction {self.interaction_type.value} with #{self.person_id} on {self.date}>"


# ── Health ──────────────────────────────────────────────────────────────────

class Medication(Base):
    """Lek/suplement do regularnego przyjmowania."""
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dosage: Mapped[Optional[str]] = mapped_column(String(100))
    frequency_per_day: Mapped[int] = mapped_column(Integer, default=1)
    time_of_day: Mapped[Optional[str]] = mapped_column(String(200))  # "08:00,20:00"
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    stock_remaining: Mapped[Optional[int]] = mapped_column(Integer)  # ile tabletek zostało
    refill_reminder_days: Mapped[Optional[int]] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    logs: Mapped[List["MedicationLog"]] = relationship(
        back_populates="medication", cascade="all, delete-orphan"
    )

    @property
    def missed_today(self) -> bool:
        """Czy dzisiejsza dawka została pominięta?"""
        # computed in service layer
        return False

    def __repr__(self) -> str:
        return f"<Medication {self.name} {self.dosage} {self.frequency_per_day}x/day>"


class MedicationLog(Base):
    """Log przyjęcia leku."""
    __tablename__ = "medication_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medications.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    medication: Mapped["Medication"] = relationship(back_populates="logs")

    def __repr__(self) -> str:
        status = "SKIPPED" if self.skipped else "taken"
        return f"<MedicationLog #{self.medication_id} {status} at {self.taken_at}>"


class Exercise(Base):
    """Sesja treningowa."""
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    exercise_type: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    intensity: Mapped[ExerciseIntensity] = mapped_column(
        SAEnum(ExerciseIntensity), nullable=False
    )
    calories_burned: Mapped[Optional[int]] = mapped_column(Integer)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Exercise {self.exercise_type} {self.duration_minutes}min [{self.intensity.value}]>"


class WeightLog(Base):
    """Pomiar wagi."""
    __tablename__ = "weight_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<WeightLog {self.date} {self.weight_kg}kg>"


class SleepLog(Base):
    """Log snu."""
    __tablename__ = "sleep_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bed_time: Mapped[time] = mapped_column(Time, nullable=False)
    wake_time: Mapped[time] = mapped_column(Time, nullable=False)
    quality: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    notes: Mapped[Optional[str]] = mapped_column(Text)

    @property
    def duration_hours(self) -> float:
        """Czas snu w godzinach."""
        today = date.today()
        bed_dt = datetime.combine(today, self.bed_time)
        wake_dt = datetime.combine(today, self.wake_time)
        if wake_dt < bed_dt:
            wake_dt = datetime.combine(today, self.wake_time)  # następny dzień
        delta = wake_dt - bed_dt
        hours = delta.total_seconds() / 3600
        if hours < 0:
            hours += 24
        return round(hours, 1)

    def __repr__(self) -> str:
        return f"<SleepLog {self.date} {self.duration_hours}h quality={self.quality}>"


# ── Nutrition ───────────────────────────────────────────────────────────────

class Meal(Base):
    """Posiłek."""
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    meal_type: Mapped[MealType] = mapped_column(SAEnum(MealType), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    calories: Mapped[Optional[int]] = mapped_column(Integer)
    protein_g: Mapped[Optional[float]] = mapped_column(Float)
    carbs_g: Mapped[Optional[float]] = mapped_column(Float)
    fat_g: Mapped[Optional[float]] = mapped_column(Float)
    healthy_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    was_snacking_urge: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Meal {self.meal_type.value} {self.calories or '?'}kcal on {self.date}>"


class Recipe(Base):
    """Przepis kulinarny."""
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    ingredients: Mapped[str] = mapped_column(Text, nullable=False)  # JSON lub markdown
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    calories_per_serving: Mapped[Optional[int]] = mapped_column(Integer)
    protein_g: Mapped[Optional[float]] = mapped_column(Float)
    prep_time_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    tags: Mapped[Optional[str]] = mapped_column(String(500))  # comma-separated
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Recipe {self.name} {self.calories_per_serving or '?'}kcal>"


# ── Mental & Focus ─────────────────────────────────────────────────────────

class IntrusiveThought(Base):
    """Natarczywa myśl — zarejestrowana i przepracowana."""
    __tablename__ = "intrusive_thoughts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    thought: Mapped[str] = mapped_column(Text, nullable=False)
    intensity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    category: Mapped[Optional[str]] = mapped_column(String(100))  # work, health, relationships, etc.
    response: Mapped[Optional[str]] = mapped_column(Text)  # jak sobie poradziłeś
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<IntrusiveThought intensity={self.intensity} resolved={self.resolved}>"


class SnackingUrge(Base):
    """Odruch podjadania — trigger i reakcja."""
    __tablename__ = "snacking_urges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(300), nullable=False)  # nuda, stres, zmęczenie, nawyk
    intensity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    resisted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    alternative_action: Mapped[Optional[str]] = mapped_column(Text)  # co zrobiłeś zamiast
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def success_rate_7d(self) -> float:
        """Skuteczność opierania się w ostatnich 7 dniach."""
        # computed in service layer
        return 0.0

    def __repr__(self) -> str:
        status = "RESISTED" if self.resisted else "GAVE_IN"
        return f"<SnackingUrge {status} trigger={self.trigger}>"


class FocusSession(Base):
    """Sesja skupienia (deep work / pomodoro)."""
    __tablename__ = "focus_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    productivity_score: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @property
    def actual_duration_minutes(self) -> Optional[int]:
        if self.end_time is None:
            return None
        return int((self.end_time - self.start_time).total_seconds() / 60)

    @property
    def completion_rate(self) -> Optional[float]:
        if self.end_time is None:
            return None
        return self.actual_duration_minutes / self.planned_duration_minutes

    def __repr__(self) -> str:
        return f"<FocusSession {self.task[:40]} {self.actual_duration_minutes or '?'}/{self.planned_duration_minutes}min>"


# ── Events ──────────────────────────────────────────────────────────────────

class Event(Base):
    """Ważne wydarzenie — urodziny, rocznica, spotkanie."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.id"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # birthday, anniversary, appointment, other
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=7)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    person: Mapped[Optional["Person"]] = relationship(back_populates="events")

    @property
    def days_until(self) -> int:
        return (self.event_date - date.today()).days

    @property
    def needs_reminder(self) -> bool:
        return 0 <= self.days_until <= self.reminder_days_before

    def __repr__(self) -> str:
        return f"<Event {self.title} {self.event_date} ({self.days_until}d)>"


# ── Hobbies ─────────────────────────────────────────────────────────────────

class Hobby(Base):
    """Hobby użytkownika."""
    __tablename__ = "hobbies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    target_hours_per_week: Mapped[Optional[float]] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sessions: Mapped[List["HobbySession"]] = relationship(
        back_populates="hobby", cascade="all, delete-orphan"
    )
    time_blocks: Mapped[List["TimeBlock"]] = relationship(back_populates="hobby")

    def __repr__(self) -> str:
        return f"<Hobby {self.name} target={self.target_hours_per_week}h/wk>"


class HobbySession(Base):
    """Sesja hobby."""
    __tablename__ = "hobby_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hobby_id: Mapped[int] = mapped_column(ForeignKey("hobbies.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    enjoyment: Mapped[Optional[int]] = mapped_column(Integer)  # 1-5
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    hobby: Mapped["Hobby"] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return f"<HobbySession #{self.hobby_id} {self.duration_minutes}min>"


# ── Database Factory ────────────────────────────────────────────────────────

def create_engine_sqlite(path: str = "life_management.db", echo: bool = False):
    """Create SQLite engine with WAL mode for concurrent access."""
    engine = create_engine(f"sqlite:///{path}", echo=echo)
    # Enable WAL mode for better concurrent access
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    return engine


def init_db(engine) -> None:
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_session(engine) -> Session:
    """Get a new session."""
    return Session(engine)
