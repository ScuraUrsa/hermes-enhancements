# Life Management System — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/life-management/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Time Tracker Core + People CRM** — 5-min bloki, baza 50 osób, balance time, raporty, habit tracker, event manager | ✅ Done |
| deleg_??? | **Health & Wellness** — pigułki (rozbudowa), odżywianie (meal planning, kalorie, woda), ćwiczenia (workout tracker, progress), sen (sleep tracker) | ⬜ |
| deleg_??? | **Mind & Habits** — natarczywe myśli (CBT patterns, trigger analysis), podjadanie (trigger→response mapping), focus (pomodoro, deep work sessions), produktywność (daily goals, weekly reviews) | ⬜ |
| deleg_??? | **Hermes Integration** — cron jobs (daily brief, pill reminder, weekly report), voice reminders, Telegram notifications, dashboard webowy | ⬜ |

## Zasady
1. Wpisz swój obszar przed rozpoczęciem pracy
2. Nie wchodź w obszar innego agenta
3. Commituj do `life-management/` w repo `ScuraUrsa/hermes-enhancements`
4. Używaj `ollama_token_monitor.py record` po każdym API callu
5. Każdy moduł rozszerza `life_cli.py` lub tworzy własny plik w `life-management/`

## Architektura wspólna
- Wszystkie moduły ładują się do wspólnej bazy SQLite: `data/life_management.db`
- Wspólny format czasu: bloki 5-minutowe, ISO 8601
- Wspólny format osób: `people` table (id, name, category, priority, last_contact, notes)
- Core engine: `life_cli.py` — zawiera TimeTracker, PeopleManager, EventManager, HabitTracker, ReportGenerator
- Każdy nowy moduł może importować z `life_cli.py` lub rozszerzać go

## Stan bazy
- SQLite: `life-management/data/life_management.db`
- Tabele: `people`, `time_blocks`, `events`, `habit_log`
- Wszystkie tabele tworzone automatycznie przez `LifeDB._init_tables()`

## Co już działa (GŁÓWNY zrobił)
- ✅ Time Tracker: start/stop/log bloków 5-minutowych
- ✅ People CRM: CRUD, kategorie, priorytety, balans czasu, overdue detection
- ✅ Event Manager: wydarzenia, recurring, reminder_days_before
- ✅ Habit Tracker: pills, thoughts, snacking, exercise, water, focus_session
- ✅ Report Generator: daily brief, weekly deep dive
- ✅ 27 testów jednostkowych
- ✅ Hermes skill: `productivity/life-management`
- ✅ CLI: `python3 life_cli.py <komenda>`
