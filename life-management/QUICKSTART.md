# 🧬 Life Management System — Quickstart (5 minut)

Zainstaluj, skonfiguruj i zacznij śledzić swoje życie w 5 minut.

---

## ⚡ Krok 1: Instalacja (30 sekund)

```bash
cd ~/workspace/hermes-enhancements/life-management

# Wygeneruj dane startowe (50 osób + przykładowe bloki)
python3 hermes_integration.py seed
```

**Co się stało:** baza SQLite `data/life_management.db` została utworzona z 50 osobami, przykładowymi blokami czasu i wydarzeniami.

---

## ⚡ Krok 2: Pierwszy blok czasu (10 sekund)

```bash
# Zacznij śledzić co robisz
python3 life_cli.py start praca

# ... pracujesz ...

# Zakończ blok
python3 life_cli.py stop "Skończyłem kodować"
```

**Output:**
```
▶️  START: praca — 2026-07-19T14:30:00
⏹️  STOP: praca — 2026-07-19T14:30:00 → 2026-07-19T15:00:00
```

---

## ⚡ Krok 3: Zaloguj nawyki (10 sekund)

```bash
# Pigułki
python3 life_cli.py pill taken

# Natarczywa myśl (intensywność 1-10)
python3 life_cli.py thought 5

# Podjadanie
python3 life_cli.py snack 3
```

**Output:**
```
💊 Pigułki: taken | Seria: 1 dni
🧠 Natarczywa myśl: intensywność 5/10
🍪 Podjadanie: intensywność 3/10
```

---

## ⚡ Krok 4: Zobacz raport (5 sekund)

```bash
python3 life_cli.py brief
```

**Output (przykład):**
```
📅 niedziela, 19.07.2026
========================================

⏱️ CZAS:
   Śledzone: 0.5h (2.1% dnia)
   praca: 0.5h

🔔 WYDARZENIA:
   ⚠️ Wizyta u dentysty — 2026-08-15

🎂 URODZINY (7 dni):
   🎈 Kumpel Marek — za 3 dni (34 lat)

👥 KONTAKT POTRZEBNY:
   🔴 Kumpel Marek (znajomi_bliscy) — ostatni kontakt: 12 dni temu

💊 NAWYKI:
   pills: 1x dziś
   intrusive_thought: 1x dziś
   snacking: 1x dziś
```

---

## ⚡ Krok 5: Skonfiguruj automatyzację (1 minuta)

```bash
# Uruchom cron jobs — automatyczne przypomnienia co godzinę
python3 -c "from hermes_integration import CronManager; CronManager.setup_all()"
```

Od teraz Hermes będzie Ci przypominał:
- **08:00** — Daily brief
- **09:00** — Poranne pigułki
- **12:00** — Co robisz?
- **21:00** — Wieczorne pigułki
- **22:00** — Podsumowanie dnia
- **Niedziela 20:00** — Raport tygodniowy
- **07:00** — Sprawdzenie urodzin

---

## ⚡ Bonus: Dashboard i Telegram (opcjonalnie)

### Web Dashboard

```bash
# Terminal 1: uruchom dashboard
python3 dashboard_server.py 8080

# Otwórz w przeglądarce
open http://localhost:8080
```

Dashboard pokazuje na żywo: czas dziś, alerty, streaki, nadchodzące wydarzenia, balans osób. Ma też przyciski do szybkiego logowania.

### Telegram Bot

```bash
# Ustaw token
export TELEGRAM_BOT_TOKEN="twój_token_z_Bitwarden"

# Uruchom bota
python3 telegram_bot.py run
```

Teraz możesz logować przez Telegram:
```
/praca          → start pracy
/stop           → koniec bloku
/pill           → pigułki wzięte
/thought 7      → natarczywa myśl
/snack 4        → podjadanie
/brief          → daily brief
```

---

## 📋 Ściągawka — najważniejsze komendy

```bash
# ⏱️ CZAS
python3 life_cli.py start praca          # rozpocznij
python3 life_cli.py stop                 # zakończ
python3 life_cli.py today                # podsumowanie dnia

# 💊 NAWYKI
python3 life_cli.py pill taken           # pigułki
python3 life_cli.py thought 7            # myśl (1-10)
python3 life_cli.py snack 4              # podjadanie (1-10)

# 👥 OSOBY
python3 life_cli.py people               # lista
python3 life_cli.py attention            # kto overdue
python3 life_cli.py birthdays 30         # urodziny

# 📊 RAPORTY
python3 life_cli.py brief                # daily brief
python3 life_cli.py week                 # tydzień

# 🎮 GAMIFIKACJA
python3 gamification.py status           # level, XP, questy
python3 gamification.py check            # sprawdź nagrody
```

---

## 🔜 Co dalej?

- 📖 Przeczytaj pełny [USER_GUIDE.md](./USER_GUIDE.md) — wszystkie funkcje, integracje, moduły Health i Mind
- 🏗️ Zobacz [ARCHITECTURE.md](./ARCHITECTURE.md) — schemat bazy, flow danych, API
- 🔗 Skonfiguruj [Google Calendar Sync](./USER_GUIDE.md#google-calendar) — eksportuj bloki do kalendarza
- 📝 Podłącz [Notion](./USER_GUIDE.md#notion) — automatyczny backup raportów
- 🧠 Użyj [Mind Module](./USER_GUIDE.md#moduł-mind--habits) — analiza CBT, mapowanie triggerów podjadania
- 🏥 Użyj [Health Module](./USER_GUIDE.md#moduł-health--wellness) — harmonogram pigułek, kalorie, makro, sen

---

**Gotowe! 🎉** Właśnie skonfigurowałeś kompletny system do zarządzania życiem. Od teraz każda minuta jest śledzona, każda relacja monitorowana, a każdy nawyk mierzony.
