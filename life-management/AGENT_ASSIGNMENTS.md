# Life Management System — Agent Assignments

Każdy agent wpisuje swój obszar poniżej. **Nie dublujemy się.**
Wspólne repo: `ScuraUrsa/hermes-enhancements/life-management/`

| Agent ID | Obszar | Status |
|----------|--------|--------|
| **GŁÓWNY** (Coder, deepseek-v4-pro) | **Time Tracker Core + People CRM** — 5-min bloki, baza 50 osób, balance time, raporty | 🔄 W trakcie |
| deleg_??? | **Health & Wellness** — pigułki, odżywianie, ćwiczenia, woda, sen | ⬜ |
| deleg_??? | **Mind & Habits** — natarczywe myśli, podjadanie, focus, produktywność | ⬜ |
| deleg_??? | **Events & Reminders** — urodziny, ważne daty, kalendarz, powiadomienia | ⬜ |
| deleg_??? | **Hermes Integration** — skill, cron jobs, voice reminders, dashboard | ⬜ |

## Zasady
1. Wpisz swój obszar przed rozpoczęciem pracy
2. Nie wchodź w obszar innego agenta
3. Commituj do `life-management/` w repo `ScuraUrsa/hermes-enhancements`
4. Używaj `ollama_token_monitor.py record` po każdym API callu
5. Każdy POV musi mieć: `core.py` (działający), `README.md`, `test_core.py`

## Architektura wspólna
- Wszystkie moduły ładują się do wspólnej bazy SQLite: `life_management.db`
- Wspólny format czasu: bloki 5-minutowe, ISO 8601
- Wspólny format osób: `people` table (id, name, category, priority, last_contact, notes)
- Każdy moduł ma własne tabele, ale korzysta ze wspólnych `people` i `time_blocks`

## Stan bazy (na start)
- SQLite: `life-management/data/life_management.db`
- Tabele: `people`, `time_blocks`, `events`, `habits`, `health_log`
- Wszystkie tabele tworzone przez pierwszy moduł (Time Tracker Core)
