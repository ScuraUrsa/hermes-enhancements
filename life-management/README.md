# Life Management System

System do zarządzania każdą minutą życia. Mierzysz czas w 5-minutowych blokach, zarządzasz relacjami z 50 osobami, śledzisz zdrowie, nawyki i produktywność.

## Architektura

```
life-management/
├── data/
│   └── life_management.db     # SQLite (wszystkie dane)
├── src/
│   ├── __init__.py
│   ├── schema.py              # Schemat bazy (10 tabel)
│   ├── time_tracker.py        # Time Tracker Core — 5-min bloki
│   ├── people_crm.py          # People CRM — 50 osób, balans czasu
│   ├── reporter.py            # Raporty — daily, weekly, balance
│   └── cli.py                 # CLI — komendy terminalowe
├── tests/
│   └── test_core.py           # 42 testy jednostkowe
└── README.md
```

## Tabele w bazie

| Tabela | Opis |
|--------|------|
| `people` | 50 osób, kategorie, priorytety, urodziny, balans |
| `time_blocks` | 5-minutowe bloki czasu, energia, focus |
| `events` | Wydarzenia, urodziny, przypomnienia |
| `habits` | Nawyki (pigułki, woda, ćwiczenia, focus) |
| `habit_log` | Dzienne wykonania nawyków |
| `health_log` | Sen, pigułki, woda, jedzenie, nastrój, natarczywe myśli |
| `interactions` | Log interakcji z ludźmi |
| `focus_sessions` | Sesje Pomodoro / deep work |
| `daily_journal` | Szybki dziennik (gratitude, refleksja) |
| `weekly_summary` | Tygodniowe podsumowania |

## Szybki start

```bash
cd ~/workspace/hermes-enhancements/life-management

# Inicjalizacja bazy + import 50 przykładowych osób
PYTHONPATH=. python3 -m src.cli init --sample

# Śledzenie czasu
PYTHONPATH=. python3 -m src.cli track start work_deep --energy 8 --planned
PYTHONPATH=. python3 -m src.cli track stop --focus 9 --satisfaction 8
PYTHONPATH=. python3 -m src.cli track status

# Zarządzanie ludźmi
PYTHONPATH=. python3 -m src.cli people list
PYTHONPATH=. python3 -m src.cli people neglected
PYTHONPATH=. python3 -m src.cli people birthdays --days 30

# Logowanie zdrowia
PYTHONPATH=. python3 -m src.cli health --pills true --sleep 7.5 --mood 7 --snacking 2 --intrusive 3

# Sesje focus
PYTHONPATH=. python3 -m src.cli focus start --task "kodowanie" --duration 25
PYTHONPATH=. python3 -m src.cli focus stop --focus 8

# Raporty
PYTHONPATH=. python3 -m src.cli report daily
PYTHONPATH=. python3 -m src.cli report weekly
PYTHONPATH=. python3 -m src.cli report balance
```

## Testy

```bash
PYTHONPATH=. python3 -m pytest tests/test_core.py -v
# 42 testów, wszystkie przechodzą
```

## Kategorie czasu

| Kategoria | Opis |
|-----------|------|
| `work_deep` | Głęboka praca (Pomodoro, flow) |
| `work_shallow` | Płytka praca (maile, meetingi) |
| `people` | Czas z ludźmi |
| `health` | Ćwiczenia, sen, jedzenie |
| `hobby` | Hobby, pasje |
| `learning` | Nauka, kursy |
| `admin` | Administracja, rachunki |
| `rest` | Świadomy odpoczynek |
| `waste` | Zmarnowany czas (social media) |
| `transit` | Transport |

## Kategorie osób

| Kategoria | Domyślny kontakt | Tygodniowy cel |
|-----------|-----------------|----------------|
| `family_close` | Codziennie | 120 min |
| `partner` | Codziennie | 300 min |
| `friends_close` | Co 3 dni | 90 min |
| `family_extended` | Co tydzień | 60 min |
| `friends` | Co 2 tygodnie | 45 min |
| `work` | Co 5 dni | — |
| `mentor` | Co miesiąc | 30 min |

## Podział pracy między agentami

Zobacz `AGENT_ASSIGNMENTS.md` — każdy agent ma swój obszar:

- **GŁÓWNY (Coder)**: Time Tracker Core + People CRM ✅ (ten moduł)
- **Health & Wellness**: pigułki, odżywianie, ćwiczenia, woda, sen
- **Mind & Habits**: natarczywe myśli, podjadanie, focus, produktywność
- **Events & Reminders**: urodziny, ważne daty, kalendarz, powiadomienia
- **Hermes Integration**: skill, cron jobs, voice reminders, dashboard

## Status

- [x] Schema (10 tabel)
- [x] Time Tracker Core (start/stop, 5-min bloki, focus sessions)
- [x] People CRM (50 osób, balans, neglected detection, birthdays)
- [x] Reporter (daily briefing, weekly summary, balance alerts)
- [x] CLI (wszystkie komendy)
- [x] Testy (42/42 passing)
- [ ] Hermes skill (do zrobienia przez agenta Integration)
- [ ] Cron jobs (do zrobienia przez agenta Integration)
- [ ] Voice reminders (do zrobienia przez agenta Integration)
