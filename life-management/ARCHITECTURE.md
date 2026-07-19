# 🧬 Life Management System — Architektura Techniczna

Dokument opisuje architekturę systemu: strukturę modułów, schemat bazy danych, przepływ danych oraz API endpoints.

---

## 📦 Struktura projektu

```
life-management/
├── life_cli.py                # 🔴 Core Engine — TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator, CLI
├── health.py                  # 🟢 Health & Wellness — PillScheduler, MealTracker, WaterTracker, ExerciseTracker, SleepTracker
├── mind.py                    # 🟣 Mind & Habits — IntrusiveThoughtTracker, SnackingTracker, FocusTracker, GoalTracker, ReviewTracker
├── gamification.py            # 🟡 Gamification — XP, poziomy, achievementy, daily questy, weekly challenge'y
├── telegram_bot.py            # 🔵 Telegram Bot — long polling, obsługa komend, szybkie logowanie
├── gcal_sync.py               # 🟠 Google Calendar Sync + Notion Backup
├── hermes_integration.py      # ⚪ Hermes Integration — CronManager, NotificationBridge, SeedGenerator, Dashboard HTML
├── dashboard_server.py        # ⚪ Web Dashboard — HTTP server + REST API
├── voice_reminders.py         # ⚪ Voice Reminders — TTS przez Hermes
├── life_cli_v2.py             # 🔴 Alternatywna implementacja CLI (SQLAlchemy)
├── life_cli_backup.py         # 🔴 Backup oryginalnego CLI
│
├── data/                      # Bazy SQLite
│   ├── life_management.db     # Główna baza (core engine)
│   ├── bot_life.db            # Baza dla Telegram bota
│   ├── hermes_integration.db  # Baza dla dashboardu i integracji
│   └── test_*.db              # Testowe bazy
│
├── tests/
│   ├── test_core.py           # Testy core engine
│   └── test_services.py       # Testy serwisów
│
├── test_life_cli.py           # 27 testów jednostkowych CLI
├── test_health.py             # 63 testy modułu health
├── test_mind.py               # 60 testów modułu mind
│
├── dashboard.html             # Wygenerowany dashboard (statyczny)
├── README.md                  # Oryginalny README
├── AGENT_ASSIGNMENTS.md       # Podział pracy między agentami
│
├── USER_GUIDE.md              # 📖 Przewodnik użytkownika
├── ARCHITECTURE.md            # 📖 Ten dokument
└── QUICKSTART.md              # 📖 Szybki start
```

---

## 🧩 Diagram modułów

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LIFE MANAGEMENT SYSTEM                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  life_cli.py │  │  health.py   │  │   mind.py    │                  │
│  │  (Core)      │  │  (Health)    │  │  (Mind)      │                  │
│  │              │  │              │  │              │                  │
│  │ TimeTracker  │  │ PillScheduler│  │ ThoughtTracker│                │
│  │ PeopleManager│  │ MealTracker  │  │ SnackingTracker│               │
│  │ EventManager │  │ WaterTracker │  │ FocusTracker  │                │
│  │ HabitTracker │  │ ExerciseTr.  │  │ GoalTracker   │                │
│  │ ReportGen.   │  │ SleepTracker │  │ ReviewTracker │                │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                 │                 │                          │
│         └──────────┬──────┴────────┬────────┘                          │
│                    │               │                                   │
│              ┌─────▼─────┐   ┌─────▼─────┐                             │
│              │  LifeDB   │   │ HealthDB  │  (dziedziczy LifeDB)        │
│              │  (SQLite) │   │  MindDB   │  (dziedziczy LifeDB)        │
│              └─────┬─────┘   └─────┬─────┘                             │
│                    │               │                                   │
│                    └───────┬───────┘                                   │
│                            │                                           │
│                    ┌───────▼───────┐                                   │
│                    │  SQLite WAL   │                                   │
│                    │  life_management.db                               │
│                    └───────────────┘                                   │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                          WARSTWA INTEGRACJI                             │
│                                                                         │
│  ┌────────────────┐  ┌────────────┐  ┌──────────────┐                  │
│  │ telegram_bot.py│  │ gcal_sync  │  │ hermes_integ.│                  │
│  │                │  │   .py      │  │   ration.py  │                  │
│  │ LifeBot        │  │ GCalSync   │  │ CronManager  │                  │
│  │ Long polling   │  │ NotionBkp  │  │ NotifBridge  │                  │
│  └───────┬────────┘  └─────┬──────┘  │ SeedGen      │                  │
│          │                 │         └──────┬───────┘                  │
│          │          ┌──────▼──────┐         │                          │
│          │          │ Google      │         │                          │
│          │          │ Calendar    │         │                          │
│          │          │ Notion API  │         │                          │
│          │          └─────────────┘         │                          │
│          │                                  │                          │
│  ┌───────▼────────┐              ┌──────────▼──────────┐               │
│  │ Telegram API   │              │ Hermes Cron System  │               │
│  │ (Bot Messages) │              │ (8 scheduled jobs)  │               │
│  └────────────────┘              └─────────────────────┘               │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                          WARSTWA PREZENTACJI                            │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ dashboard_server │  │ voice_reminders  │  │ gamification.py  │      │
│  │       .py        │  │      .py         │  │                  │      │
│  │                  │  │                  │  │ Gamification     │      │
│  │ HTTP Server      │  │ VoiceReminder    │  │ Engine           │      │
│  │ REST API         │  │ TTS via Hermes   │  │ XP/Levels/Achv   │      │
│  │ SPA Dashboard    │  │                  │  │ Quests/Chall.    │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Schemat bazy danych

Wszystkie dane przechowywane w **SQLite** (WAL mode, foreign keys ON).

### Tabele Core Engine (`life_cli.py` → `LifeDB`)

```sql
-- Osoby w systemie (max 50)
CREATE TABLE people (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'znajomi',  -- rodzina_blizsza, rodzina_dalsza, znajomi_bliscy, znajomi, wspolpracownicy, inni
    priority        INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
    birthday        TEXT,                              -- ISO date: "1990-05-15"
    phone           TEXT DEFAULT '',
    email           TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    last_contact    TEXT,                              -- ISO datetime
    contact_frequency_days INTEGER NOT NULL DEFAULT 14,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Bloki czasu (5-minutowe)
CREATE TABLE time_blocks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time      TEXT NOT NULL,                     -- ISO datetime
    end_time        TEXT NOT NULL,                     -- ISO datetime
    category        TEXT NOT NULL DEFAULT 'inne',      -- praca, rodzina, znajomi, zdrowie, jedzenie, hobby, odpoczynek, nauka, administracja, transport, higiena, inne
    person_id       INTEGER,                          -- FK → people.id (NULL = solo)
    description     TEXT DEFAULT '',
    energy_level    INTEGER NOT NULL DEFAULT 5 CHECK(energy_level BETWEEN 1 AND 10),
    focus_level     INTEGER NOT NULL DEFAULT 5 CHECK(focus_level BETWEEN 1 AND 10),
    was_planned     INTEGER NOT NULL DEFAULT 0,        -- 0/1
    tags            TEXT DEFAULT '[]',                 -- JSON array
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
);

-- Wydarzenia
CREATE TABLE events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    event_date          TEXT NOT NULL,                  -- ISO date
    event_type          TEXT NOT NULL DEFAULT 'inne',   -- urodziny, rocznica, deadline, spotkanie, zdrowie, inne
    person_id           INTEGER,                        -- FK → people.id
    recurring           INTEGER NOT NULL DEFAULT 0,     -- 0/1
    reminder_days_before INTEGER NOT NULL DEFAULT 3,
    notes               TEXT DEFAULT '',
    notified            INTEGER NOT NULL DEFAULT 0,     -- 0/1
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE SET NULL
);

-- Logi nawyków
CREATE TABLE habit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,                          -- ISO datetime
    habit_type  TEXT NOT NULL,                          -- pills, exercise, intrusive_thought, snacking, focus_session, meal, water
    value       TEXT DEFAULT '',                        -- "taken", "skipped", "30min", "occurred", itp.
    intensity   INTEGER DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Indeksy Core

```sql
CREATE INDEX idx_time_blocks_start    ON time_blocks(start_time);
CREATE INDEX idx_time_blocks_category ON time_blocks(category);
CREATE INDEX idx_time_blocks_person   ON time_blocks(person_id);
CREATE INDEX idx_events_date          ON events(event_date);
CREATE INDEX idx_events_person        ON events(person_id);
CREATE INDEX idx_habit_log_timestamp  ON habit_log(timestamp);
CREATE INDEX idx_habit_log_type       ON habit_log(habit_type);
CREATE INDEX idx_people_category      ON people(category);
```

### Tabele Health (`health.py` → `HealthDB` extends `LifeDB`)

```sql
CREATE TABLE pill_schedule (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pill_name    TEXT NOT NULL,
    time_of_day  TEXT NOT NULL DEFAULT '09:00',         -- HH:MM
    days_of_week TEXT NOT NULL DEFAULT '[1,2,3,4,5,6,7]', -- JSON array, 1=Monday
    dosage       TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE pill_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,                        -- FK → pill_schedule.id
    timestamp   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'taken',           -- taken, skipped, missed
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (schedule_id) REFERENCES pill_schedule(id) ON DELETE CASCADE
);

CREATE TABLE meals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    meal_type   TEXT NOT NULL DEFAULT 'other',           -- breakfast, lunch, dinner, snack, other
    name        TEXT DEFAULT '',
    calories    INTEGER NOT NULL DEFAULT 0,
    protein_g   REAL NOT NULL DEFAULT 0.0,
    carbs_g     REAL NOT NULL DEFAULT 0.0,
    fat_g       REAL NOT NULL DEFAULT 0.0,
    photo_path  TEXT DEFAULT '',
    notes       TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE water_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    amount_ml   INTEGER NOT NULL DEFAULT 250,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE water_goals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    daily_goal_ml   INTEGER NOT NULL DEFAULT 2500,
    effective_from  TEXT NOT NULL DEFAULT (date('now')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE exercise_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    exercise_type   TEXT NOT NULL DEFAULT 'other',
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    intensity       INTEGER NOT NULL DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
    calories_burned INTEGER NOT NULL DEFAULT 0,
    notes           TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE sleep_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sleep_date       TEXT NOT NULL,
    bedtime          TEXT NOT NULL,
    wake_time        TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 0,
    quality          INTEGER NOT NULL DEFAULT 5 CHECK(quality BETWEEN 1 AND 10),
    notes            TEXT DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Tabele Mind (`mind.py` → `MindDB` extends `LifeDB`)

```sql
CREATE TABLE intrusive_thoughts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp            TEXT NOT NULL,
    thought_content      TEXT DEFAULT '',
    trigger              TEXT DEFAULT '',
    cbt_pattern          TEXT DEFAULT '',               -- catastrophizing, black_and_white, mind_reading, ...
    intensity            INTEGER NOT NULL DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
    coping_strategy      TEXT DEFAULT '',               -- cognitive_restructuring, mindfulness, distraction, ...
    coping_effectiveness INTEGER NOT NULL DEFAULT 5 CHECK(coping_effectiveness BETWEEN 1 AND 10),
    outcome              TEXT DEFAULT '',
    notes                TEXT DEFAULT '',
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE snacking_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp          TEXT NOT NULL,
    trigger_type       TEXT DEFAULT '',                 -- boredom, stress, sadness, anxiety, ...
    trigger_detail     TEXT DEFAULT '',
    food_eaten         TEXT DEFAULT '',
    amount             TEXT DEFAULT '',
    intensity          INTEGER NOT NULL DEFAULT 5 CHECK(intensity BETWEEN 1 AND 10),
    feeling_after      TEXT DEFAULT '',                 -- guilty, satisfied, neutral, regretful, ...
    alternative_action TEXT DEFAULT '',
    notes              TEXT DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE focus_sessions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time            TEXT NOT NULL,
    end_time              TEXT DEFAULT '',
    duration_minutes      INTEGER NOT NULL DEFAULT 25,
    actual_duration_minutes INTEGER NOT NULL DEFAULT 0,
    task_description      TEXT DEFAULT '',
    distractions          TEXT DEFAULT '[]',            -- JSON array
    distraction_count     INTEGER NOT NULL DEFAULT 0,
    productivity_score    INTEGER NOT NULL DEFAULT 5 CHECK(productivity_score BETWEEN 1 AND 10),
    focus_level           INTEGER NOT NULL DEFAULT 5 CHECK(focus_level BETWEEN 1 AND 10),
    completed             INTEGER NOT NULL DEFAULT 0,
    notes                 TEXT DEFAULT '',
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE daily_goals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_date      TEXT NOT NULL,
    priority_order INTEGER NOT NULL DEFAULT 1 CHECK(priority_order BETWEEN 1 AND 3),
    goal_text      TEXT NOT NULL,
    completed      INTEGER NOT NULL DEFAULT 0,
    completed_at   TEXT,
    notes          TEXT DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE weekly_reviews (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    week_start       TEXT NOT NULL,
    week_end         TEXT NOT NULL,
    what_went_well   TEXT DEFAULT '',
    what_to_improve  TEXT DEFAULT '',
    lessons_learned  TEXT DEFAULT '',
    gratitude        TEXT DEFAULT '',
    energy_avg       INTEGER NOT NULL DEFAULT 5 CHECK(energy_avg BETWEEN 1 AND 10),
    mood_avg         INTEGER NOT NULL DEFAULT 5 CHECK(mood_avg BETWEEN 1 AND 10),
    goals_completed  INTEGER NOT NULL DEFAULT 0,
    goals_total      INTEGER NOT NULL DEFAULT 0,
    next_week_focus  TEXT DEFAULT '',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Tabele Gamifikacji (`gamification.py`)

```sql
CREATE TABLE xp_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    source      TEXT NOT NULL,                           -- time_block, pill, exercise, contact, achievement, daily_quest, weekly_challenge
    amount      INTEGER NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE achievements_unlocked (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id  TEXT NOT NULL UNIQUE,
    unlocked_at     TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE daily_quests_completed (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id     TEXT NOT NULL,
    date         TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(quest_id, date)
);

CREATE TABLE weekly_challenges_completed (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_id  TEXT NOT NULL,
    week_start    TEXT NOT NULL,
    completed_at  TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(challenge_id, week_start)
);
```

---

## 🔄 Flow danych

### 1. Śledzenie czasu (Time Tracking)

```
Użytkownik
    │
    ├── CLI: python3 life_cli.py start praca
    │   └── TimeTracker.start_block()
    │       ├── Zamyka poprzedni blok (jeśli otwarty)
    │       ├── Zapisuje start_time w pamięci
    │       └── Zwraca TimeBlock (bez ID)
    │
    ├── CLI: python3 life_cli.py stop
    │   └── TimeTracker.stop_block()
    │       ├── Oblicza duration (zaokrągla do 5 min)
    │       ├── INSERT INTO time_blocks (...)
    │       ├── Jeśli person_id: UPDATE people SET last_contact = now
    │       └── Zwraca TimeBlock z ID
    │
    ├── Telegram: /praca → LifeBot.handle() → TimeTracker.start_block()
    └── Dashboard: POST /api/start → LifeAPI.start_block() → TimeTracker.start_block()
```

### 2. People CRM — wykrywanie overdue

```
PeopleManager.get_balance_report()
    │
    ├── SELECT people + LEFT JOIN time_blocks (30 dni)
    ├── Dla każdej osoby:
    │   ├── days_since_contact = now - last_contact
    │   └── overdue = days_since_contact > contact_frequency_days
    │
    └── Zwraca listę z flagą overdue

PeopleManager.get_who_needs_attention()
    │
    ├── Wywołuje get_balance_report()
    ├── Sortuje: overdue first → priority desc → days_since_contact desc
    └── Zwraca top N
```

### 3. Daily Brief

```
ReportGenerator.daily_brief()
    │
    ├── TimeTracker.get_today_summary()
    │   └── SELECT category, SUM(minutes) FROM time_blocks WHERE date = today GROUP BY category
    │
    ├── EventManager.get_upcoming_events(days=1)
    │   └── SELECT FROM events WHERE event_date BETWEEN today AND tomorrow
    │
    ├── PeopleManager.get_upcoming_birthdays(days=7)
    │   └── Iteruje people, oblicza najbliższe urodziny
    │
    ├── PeopleManager.get_who_needs_attention(top=5)
    │
    ├── HabitTracker.get_today_habits()
    │   └── SELECT FROM habit_log WHERE date = today GROUP BY habit_type
    │
    └── Formatuje jako tekst
```

### 4. Gamification — auto-check

```
Gamification.auto_check_all()
    │
    ├── check_achievements()
    │   ├── Dla każdego achievementu (20+):
    │   │   ├── Sprawdza warunek (np. pill_streak_7: get_streak("pills") >= 7)
    │   │   ├── Jeśli spełniony i nieodblokowany:
    │   │   │   ├── INSERT INTO achievements_unlocked
    │   │   │   └── add_xp("achievement", ach.xp)
    │   │   └── Zwraca listę nowych
    │
    ├── Auto-complete daily quests
    │   ├── Dla każdego questa: sprawdza progress >= target
    │   └── complete_quest() → INSERT + add_xp
    │
    ├── Auto-complete weekly challenges
    │   ├── Dla każdego challenge'a: sprawdza progress >= 100
    │   └── complete_challenge() → INSERT + add_xp
    │
    └── Zwraca {new_achievements, completed_quests, completed_challenges, level}
```

### 5. Google Calendar Sync

```
Eksport:
GoogleCalendarSync.export_blocks(days=7)
    │
    ├── TimeTracker.get_blocks(start_date)
    ├── Dla każdego bloku:
    │   ├── Tworzy event_data (summary, start, end, colorId, description)
    │   ├── Jeśli person_id: dodaje "z {person.name}" do summary
    │   └── POST /calendars/{id}/events
    └── Zwraca liczbę wyeksportowanych

Import:
GoogleCalendarSync.import_events(days=30)
    │
    ├── GET /calendars/{id}/events?timeMin=now&timeMax=now+30d
    ├── Dla każdego eventu:
    │   ├── Sprawdza czy już istnieje (title + event_date)
    │   ├── Określa event_type po słowach kluczowych
    │   └── EventManager.add_event()
    └── Zwraca liczbę zaimportowanych
```

### 6. Cron Jobs → Hermes

```
CronManager.setup_all()
    │
    ├── Dla każdego z 8 jobów:
    │   └── hermes cron create --schedule "..." --prompt "..."
    │
    └── Hermes Cron System
        │
        ├── 08:00 → life-daily-brief
        │   └── Uruchamia life_cli.py brief → formatuje → wysyła użytkownikowi
        │
        ├── 09:00 → life-pill-morning
        │   └── Pyta "Wziąłeś pigułki?" → jeśli tak: life_cli.py pill taken
        │
        ├── 12:00 → life-midday-checkin
        │   └── Pyta "Co robisz?" → life_cli.py start <kategoria>
        │
        ├── 21:00 → life-pill-evening
        │   └── Pyta "Wieczorne pigułki?"
        │
        ├── 22:00 → life-evening-checkin
        │   └── Pyta o energię, focus, myśli, podjadanie → loguje
        │
        ├── Niedziela 20:00 → life-weekly-report
        │   └── life_cli.py week → formatuje → wysyła
        │
        └── 07:00 → life-birthday-check
            └── life_cli.py birthdays 7 → przypomina
```

---

## 🌐 API Endpoints (Dashboard Server)

Dashboard server (`dashboard_server.py`) wystawia REST API na `http://localhost:8080`.

| Method | Endpoint | Parametry | Zwraca | Opis |
|--------|----------|-----------|--------|------|
| GET | `/` | — | HTML | Dashboard SPA |
| GET | `/api/dashboard` | — | JSON | Pełne dane dashboardu |
| GET | `/api/start` | `category`, `desc`? | JSON | Rozpocznij blok czasu |
| GET | `/api/stop` | — | JSON | Zakończ blok czasu |
| GET | `/api/habit` | `type`, `value`, `intensity`? | JSON | Zaloguj nawyk |

### Struktura odpowiedzi `/api/dashboard`

```json
{
  "today": {
    "date": "2026-07-19",
    "total_minutes": 480,
    "total_hours": 8.0,
    "blocks_tracked": 12,
    "by_category": {
      "praca": 360,
      "jedzenie": 45,
      "zdrowie": 60,
      "hobby": 15
    },
    "coverage_pct": 33.3
  },
  "people": [
    {
      "id": 1,
      "name": "Mama",
      "category": "rodzina_blizsza",
      "priority": 10,
      "hours_last_30d": 2.5,
      "days_since_contact": 2,
      "contact_frequency_days": 3,
      "overdue": false
    }
  ],
  "alerts": [
    {
      "type": "overdue_contact",
      "priority": "high",
      "message": "🔴 Kumpel Marek (znajomi_bliscy) — 12d bez kontaktu",
      "action": "Zadzwoń lub napisz do Kumpel Marek"
    }
  ],
  "streaks": {
    "pigułki": 14,
    "ćwiczenia": 3
  },
  "upcoming": {
    "birthdays": [...],
    "events": [...]
  },
  "weekly": {
    "week_start": "2026-07-13",
    "week_end": "2026-07-20",
    "total_hours": 45.2,
    "by_category": {"praca": 30.0, "zdrowie": 5.5, ...},
    "daily_average_hours": 6.5
  },
  "habits_today": {
    "pills": [{"timestamp": "...", "value": "taken"}],
    "exercise": [{"timestamp": "...", "value": "30min"}]
  },
  "habits_week": {
    "week_start": "2026-07-13",
    "habits": {
      "pills": {"count": 7, "avg_intensity": 5.0},
      "exercise": {"count": 4, "avg_intensity": 7.0}
    }
  }
}
```

---

## 🔌 Telegram Bot API

Bot używa **long pollingu** na Telegram Bot API (bez zewnętrznych bibliotek, tylko `aiohttp`).

### Flow obsługi wiadomości

```
Telegram API (getUpdates)
    │
    ▼
run_polling() [async]
    │
    ├── GET /getUpdates?offset=N&timeout=30
    │
    ├── Dla każdego update:
    │   ├── Wyciąga chat_id, text, user
    │   ├── LifeBot.handle(text)
    │   │   ├── Parsuje komendę (/praca, /pill, /brief...)
    │   │   ├── Mapuje aliasy (pigułki→pill, dziś→today...)
    │   │   └── Wywołuje odpowiedni handler
    │   │
    │   └── POST /sendMessage {chat_id, text, parse_mode: "HTML"}
    │
    └── offset = update_id + 1
```

### Mapowanie komend

| Komenda Telegram | Handler | Wywołuje |
|-----------------|---------|----------|
| `/praca`, `/rodzina`, `/hobby`... | `_start_block(cat, desc)` | `TimeTracker.start_block()` |
| `/stop` | `_cmd_stop(desc)` | `TimeTracker.stop_block()` |
| `/pill` | `_cmd_pill(arg)` | `HabitTracker.log("pills", ...)` |
| `/thought 7` | `_cmd_thought(arg)` | `HabitTracker.log("intrusive_thought", ...)` |
| `/snack 4` | `_cmd_snack(arg)` | `HabitTracker.log("snacking", ...)` |
| `/woda 250` | `_cmd_water(arg)` | `HabitTracker.log("water", ...)` |
| `/ćwiczenia 30` | `_cmd_exercise(arg)` | `HabitTracker.log("exercise", ...)` |
| `/sen 7.5` | `_cmd_sleep(arg)` | `HabitTracker.log("sleep", ...)` |
| `/brief` | `_cmd_brief()` | `ReportGenerator.daily_brief()` |
| `/today` | `_cmd_today()` | `TimeTracker.get_today_summary()` |
| `/week` | `_cmd_week()` | `ReportGenerator.weekly_deep_dive()` |
| `/attention` | `_cmd_attention()` | `PeopleManager.get_who_needs_attention()` |
| `/balance` | `_cmd_balance()` | `PeopleManager.get_balance_report()` |
| `/birthdays` | `_cmd_birthdays(arg)` | `PeopleManager.get_upcoming_birthdays()` |
| `/events` | `_cmd_events(arg)` | `EventManager.get_upcoming_events()` |
| `/people` | `_cmd_people(arg)` | `PeopleManager.get_all_people()` |

---

## 🧬 Dziedziczenie klas

```
LifeDB (SQLite connection, CRUD, tabele core)
    │
    ├── HealthDB (dodaje tabele: pill_schedule, pill_log, meals, water_log, water_goals, exercise_log, sleep_log)
    │
    └── MindDB (dodaje tabele: intrusive_thoughts, snacking_log, focus_sessions, daily_goals, weekly_reviews)
```

Wszystkie trzy klasy współdzielą tę samą bazę `life_management.db`. `HealthDB` i `MindDB` wywołują `super()._init_tables()` przed dodaniem własnych tabel — dzięki temu wszystkie tabele są tworzone przy pierwszym użyciu dowolnego modułu.

---

## 🔐 Zarządzanie sekretami

System pobiera sekrety z **Bitwarden Secrets Manager** (`bws` CLI) lub zmiennych środowiskowych:

| Sekret | Bitwarden Key | Env Variable | Używany przez |
|--------|--------------|--------------|---------------|
| Telegram Bot Token | `TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` | `telegram_bot.py` |
| Google Calendar Token | `GOOGLE_CALENDAR_TOKEN` | — | `gcal_sync.py` |
| Google Credentials JSON | — (plik) | — | `gcal_sync.py` |
| Notion API Key | `NOTION_API_KEY` | `NOTION_API_KEY` | `gcal_sync.py` |

---

## 📊 Statystyki kodu

| Moduł | Linii | Klasy | Testy |
|-------|-------|-------|-------|
| `life_cli.py` | 1063 | 6 (LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator) | 27 |
| `health.py` | 1401 | 8 (HealthDB, PillScheduler, MealTracker, WaterTracker, ExerciseTracker, SleepTracker + CLI) | 63 |
| `mind.py` | 1422 | 7 (MindDB, IntrusiveThoughtTracker, SnackingTracker, FocusTracker, GoalTracker, ReviewTracker + CLI) | 60 |
| `gamification.py` | 709 | 1 (Gamification) | — |
| `telegram_bot.py` | 450 | 1 (LifeBot) | — |
| `gcal_sync.py` | 555 | 2 (GoogleCalendarSync, NotionBackup) | — |
| `hermes_integration.py` | 752 | 3 (CronManager, NotificationBridge, SeedGenerator) | — |
| `dashboard_server.py` | 496 | 2 (LifeAPI, DashboardHandler) | — |
| `voice_reminders.py` | 189 | 1 (VoiceReminder) | — |
| **Razem** | **~7037** | **31** | **150** |

---

## 🚀 Uruchamianie

```bash
# Core CLI
python3 life_cli.py start praca
python3 life_cli.py brief

# Telegram Bot
python3 telegram_bot.py run [token]

# Dashboard
python3 dashboard_server.py 8080

# Google Calendar Sync
python3 gcal_sync.py gcal-export 7

# Gamification
python3 gamification.py status

# Voice Reminders
python3 voice_reminders.py speak

# Seed data
python3 hermes_integration.py seed

# Cron setup
python3 -c "from hermes_integration import CronManager; CronManager.setup_all()"
```
