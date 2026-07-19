#!/usr/bin/env python3
"""
Life Management — AI Insights Engine
======================================
Analizuje dane z life_management.db i generuje spersonalizowane rekomendacje:
- Pattern detection (kiedy spada energia, kiedy pojawiają się myśli)
- Correlation analysis (podjadanie vs stres, sen vs focus)
- Predictive alerts (kto będzie overdue za 3 dni)
- Weekly optimization suggestions
- Life Score — composite metric 0-100

Nie używa zewnętrznego AI — czysta statystyka i heurystyki.
"""

from __future__ import annotations

import sys
import os
import math
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict, Counter
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from life_cli import LifeDB, TimeTracker, PeopleManager, EventManager, HabitTracker

LIFE_DIR = Path(__file__).parent


class InsightsEngine:
    """Analizuje dane i generuje insights."""

    def __init__(self, db: LifeDB):
        self.db = db
        self.tracker = TimeTracker(db)
        self.people = PeopleManager(db)
        self.events = EventManager(db)
        self.habits = HabitTracker(db)

    # ── Life Score ───────────────────────────────────────────────────────

    def life_score(self) -> dict:
        """Composite Life Score 0-100 z breakdownem."""
        scores = {}

        # 1. Time Coverage (0-25)
        summary = self.tracker.get_today_summary()
        coverage = summary["coverage_pct"]
        scores["time_coverage"] = min(25, round(coverage / 100 * 25))

        # 2. Social Health (0-20)
        balance = self.people.get_balance_report()
        overdue_pct = balance["overdue_count"] / max(1, balance["total_people"]) * 100
        scores["social"] = max(0, round(20 - overdue_pct / 5))

        # 3. Health Adherence (0-20)
        pill_streak = self.habits.get_streak("pills")
        scores["health"] = min(20, pill_streak * 3)

        # 4. Mind Wellness (0-15)
        today_habits = self.habits.get_today_habits()
        thoughts = today_habits.get("intrusive_thought", [])
        snacking = today_habits.get("snacking", [])
        thought_penalty = sum(t.get("intensity", 5) for t in thoughts) * 0.5
        snack_penalty = len(snacking) * 3
        scores["mind"] = max(0, round(15 - thought_penalty - snack_penalty))

        # 5. Balance (0-10)
        cats_today = len(summary.get("by_category", {}))
        scores["balance"] = min(10, cats_today * 2)

        # 6. Consistency (0-10)
        week_data = self._get_week_coverage()
        if week_data:
            avg = sum(week_data) / len(week_data)
            variance = sum((x - avg) ** 2 for x in week_data) / len(week_data)
            consistency = max(0, 10 - math.sqrt(variance) / 10)
        else:
            consistency = 0
        scores["consistency"] = round(consistency)

        total = sum(scores.values())
        grade = self._grade(total)

        return {
            "total": total,
            "grade": grade,
            "breakdown": scores,
            "max": 100,
        }

    def _grade(self, score: int) -> str:
        if score >= 90:
            return "🌟 Legendarny"
        elif score >= 75:
            return "💎 Świetny"
        elif score >= 60:
            return "👍 Dobry"
        elif score >= 40:
            return "📈 Do poprawy"
        elif score >= 20:
            return "⚠️ Słaby"
        else:
            return "🚨 Krytyczny"

    def _get_week_coverage(self) -> list[float]:
        """Procent pokrycia dla każdego dnia tygodnia."""
        result = []
        for d in range(7):
            day = date.today() - timedelta(days=d)
            blocks = self.db.execute(
                "SELECT COALESCE(SUM((julianday(end_time)-julianday(start_time))*24*60),0) as mins FROM time_blocks WHERE date(start_time) = ?",
                (day.isoformat(),),
            )
            mins = blocks[0]["mins"]
            result.append(min(100, mins / 1440 * 100))
        return result

    # ── Pattern Detection ─────────────────────────────────────────────────

    def energy_patterns(self) -> dict:
        """Analiza poziomu energii w ciągu dnia i tygodnia."""
        blocks = self.db.execute(
            "SELECT start_time, energy_level, category FROM time_blocks WHERE energy_level > 0 ORDER BY start_time"
        )

        by_hour = defaultdict(list)
        by_day = defaultdict(list)
        by_category = defaultdict(list)

        for b in blocks:
            try:
                dt = datetime.fromisoformat(b["start_time"])
                by_hour[dt.hour].append(b["energy_level"])
                by_day[dt.strftime("%A")].append(b["energy_level"])
                by_category[b["category"]].append(b["energy_level"])
            except Exception:
                pass

        # Średnia energia na godzinę
        hourly_avg = {}
        for h in range(24):
            vals = by_hour.get(h, [])
            hourly_avg[h] = round(sum(vals) / len(vals), 1) if vals else 0

        # Znajdź peak i slump
        peak_hour = max(hourly_avg, key=hourly_avg.get) if any(hourly_avg.values()) else 0
        slump_hour = min(
            (h for h in hourly_avg if hourly_avg[h] > 0),
            key=hourly_avg.get,
            default=0,
        )

        # Najlepszy dzień
        daily_avg = {}
        for day_name, vals in by_day.items():
            daily_avg[day_name] = round(sum(vals) / len(vals), 1) if vals else 0
        best_day = max(daily_avg, key=daily_avg.get) if daily_avg else "?"

        # Kategorie z najwyższą/najniższą energią
        cat_avg = {}
        for cat, vals in by_category.items():
            cat_avg[cat] = round(sum(vals) / len(vals), 1) if vals else 0

        return {
            "hourly": hourly_avg,
            "peak_hour": peak_hour,
            "slump_hour": slump_hour,
            "best_day": best_day,
            "daily": daily_avg,
            "by_category": cat_avg,
            "recommendation": self._energy_recommendation(peak_hour, slump_hour, cat_avg),
        }

    def _energy_recommendation(self, peak: int, slump: int, cat_avg: dict) -> str:
        """Generuj rekomendację na podstawie wzorców energii."""
        parts = []

        if peak > 0:
            parts.append(f"Twoja energia szczytuje o {peak}:00 — planuj najważniejsze zadania na tę godzinę.")
        if slump > 0:
            parts.append(f"Spadek energii o {slump}:00 — to dobry moment na przerwę lub lekkie zadania.")

        high_energy_cats = [c for c, v in cat_avg.items() if v >= 7]
        low_energy_cats = [c for c, v in cat_avg.items() if v <= 4 and v > 0]

        if high_energy_cats:
            parts.append(f"Najwięcej energii masz przy: {', '.join(high_energy_cats[:3])}.")
        if low_energy_cats:
            parts.append(f"Rozważ zmianę podejścia do: {', '.join(low_energy_cats[:3])}.")

        return " ".join(parts) if parts else "Zaloguj więcej bloków z oceną energii, aby zobaczyć wzorce."

    def thought_triggers(self) -> dict:
        """Analiza triggerów natarczywych myśli."""
        thoughts = self.db.execute(
            "SELECT timestamp, intensity, notes FROM habit_log WHERE habit_type='intrusive_thought' ORDER BY timestamp DESC LIMIT 100"
        )

        if not thoughts:
            return {"message": "Brak danych o natarczywych myślach. Zacznij logować przez /thought."}

        by_hour = defaultdict(list)
        by_day = defaultdict(list)
        intensities = []

        for t in thoughts:
            try:
                dt = datetime.fromisoformat(t["timestamp"])
                by_hour[dt.hour].append(1)
                by_day[dt.strftime("%A")].append(1)
                intensities.append(t["intensity"])
            except Exception:
                pass

        # Najczęstsze godziny
        hour_counts = {h: len(v) for h, v in by_hour.items()}
        worst_hour = max(hour_counts, key=hour_counts.get) if hour_counts else 0

        # Najczęstsze dni
        day_counts = {d: len(v) for d, v in by_day.items()}
        worst_day = max(day_counts, key=day_counts.get) if day_counts else "?"

        avg_intensity = round(sum(intensities) / len(intensities), 1) if intensities else 0

        # Trend (ostatnie 7 dni vs poprzednie 7)
        recent = sum(1 for t in thoughts if t["timestamp"] >= (date.today() - timedelta(days=7)).isoformat())
        older = sum(1 for t in thoughts if (date.today() - timedelta(days=14)).isoformat() <= t["timestamp"] < (date.today() - timedelta(days=7)).isoformat())
        trend = "malejący 📉" if recent < older else "rosnący 📈" if recent > older else "stabilny ➡️"

        return {
            "total_logged": len(thoughts),
            "avg_intensity": avg_intensity,
            "worst_hour": worst_hour,
            "worst_day": worst_day,
            "trend_7d": trend,
            "recommendation": self._thought_recommendation(worst_hour, worst_day, avg_intensity, trend),
        }

    def _thought_recommendation(self, hour: int, day: str, intensity: float, trend: str) -> str:
        parts = []
        if hour > 0:
            parts.append(f"Najczęściej myśli pojawiają się o {hour}:00 — przygotuj strategię na tę porę (oddychanie, spacer).")
        if day != "?":
            parts.append(f"{day} to najtrudniejszy dzień — zaplanuj coś przyjemnego.")
        if intensity > 7:
            parts.append("Wysoka intensywność myśli — rozważ techniki CBT lub konsultację.")
        if "rosnący" in trend:
            parts.append("Trend rosnący — zwróć uwagę na ostatnie stresory.")
        return " ".join(parts) if parts else "Zaloguj więcej myśli z intensywnością, aby zobaczyć wzorce."

    def snacking_patterns(self) -> dict:
        """Analiza wzorców podjadania."""
        snacks = self.db.execute(
            "SELECT timestamp, intensity FROM habit_log WHERE habit_type='snacking' ORDER BY timestamp DESC LIMIT 100"
        )

        if not snacks:
            return {"message": "Brak danych o podjadaniu."}

        by_hour = defaultdict(list)
        for s in snacks:
            try:
                dt = datetime.fromisoformat(s["timestamp"])
                by_hour[dt.hour].append(s["intensity"])
            except Exception:
                pass

        hour_avg = {}
        for h in range(24):
            vals = by_hour.get(h, [])
            hour_avg[h] = round(sum(vals) / len(vals), 1) if vals else 0

        worst_hour = max(hour_avg, key=lambda h: (hour_avg[h], len(by_hour.get(h, [])))) if any(hour_avg.values()) else 0

        # Korelacja z myślami
        thought_days = self.db.execute(
            "SELECT DISTINCT date(timestamp) as d FROM habit_log WHERE habit_type='intrusive_thought'"
        )
        snack_days = self.db.execute(
            "SELECT DISTINCT date(timestamp) as d FROM habit_log WHERE habit_type='snacking'"
        )
        thought_set = {r["d"] for r in thought_days}
        snack_set = {r["d"] for r in snack_days}
        overlap = thought_set & snack_set
        correlation_pct = round(len(overlap) / max(1, len(snack_set)) * 100)

        return {
            "total_logged": len(snacks),
            "worst_hour": worst_hour,
            "thought_correlation_pct": correlation_pct,
            "recommendation": self._snack_recommendation(worst_hour, correlation_pct),
        }

    def _snack_recommendation(self, hour: int, corr_pct: int) -> str:
        parts = []
        if hour > 0:
            parts.append(f"Najczęściej podjadasz o {hour}:00 — przygotuj zdrowe przekąski na tę porę.")
        if corr_pct > 50:
            parts.append(f"Silna korelacja z natarczywymi myślami ({corr_pct}%) — podjadanie może być reakcją na stres.")
        return " ".join(parts) if parts else "Zaloguj więcej epizodów podjadania."

    # ── Predictive Alerts ─────────────────────────────────────────────────

    def predict_overdue(self, days_ahead: int = 3) -> list[dict]:
        """Przewiduj kto będzie overdue za N dni."""
        predictions = []
        all_people = self.people.get_all_people()

        for person in all_people:
            if not person.last_contact:
                predictions.append({
                    "name": person.name,
                    "category": person.category,
                    "priority": person.priority,
                    "days_since_contact": None,
                    "will_be_overdue_in_days": 0,
                    "urgency": "critical",
                })
                continue

            try:
                last = datetime.fromisoformat(person.last_contact)
                days_since = (datetime.now() - last).days
                days_until_overdue = person.contact_frequency_days - days_since

                if days_until_overdue <= days_ahead:
                    predictions.append({
                        "name": person.name,
                        "category": person.category,
                        "priority": person.priority,
                        "days_since_contact": days_since,
                        "will_be_overdue_in_days": max(0, days_until_overdue),
                        "urgency": "critical" if days_until_overdue <= 0 else "high" if days_until_overdue <= 1 else "medium",
                    })
            except Exception:
                pass

        predictions.sort(key=lambda x: (x["urgency"] == "critical", x["urgency"] == "high", -x["priority"]), reverse=True)
        return predictions

    # ── Weekly Optimization ───────────────────────────────────────────────

    def weekly_optimization(self) -> dict:
        """Sugestie optymalizacji na podstawie danych tygodniowych."""
        weekly = self.tracker.get_weekly_report()
        balance = self.people.get_balance_report()
        energy = self.energy_patterns()

        suggestions = []

        # Time balance
        by_cat = weekly.get("by_category", {})
        work_hours = by_cat.get("praca", 0)
        family_hours = by_cat.get("rodzina", 0)
        health_hours = by_cat.get("zdrowie", 0)
        hobby_hours = by_cat.get("hobby", 0)
        rest_hours = by_cat.get("odpoczynek", 0)

        if work_hours > 50:
            suggestions.append({
                "area": "praca",
                "issue": f"Pracujesz {work_hours}h tygodniowo — to ponad 50h",
                "suggestion": "Zablokuj max 8h dziennie na pracę. Deleguj lub powiedz 'nie'.",
                "priority": "high",
            })

        if family_hours < 2 and balance["total_people"] > 0:
            suggestions.append({
                "area": "rodzina",
                "issue": f"Tylko {family_hours}h z rodziną w tym tygodniu",
                "suggestion": "Zaplanuj 2-3 bloki czasu z rodziną. Nawet 30-minutowy telefon się liczy.",
                "priority": "high",
            })

        if health_hours < 2:
            suggestions.append({
                "area": "zdrowie",
                "issue": f"Tylko {health_hours}h na zdrowie",
                "suggestion": "Minimum 3x30min ćwiczeń tygodniowo. Zacznij od krótkiego spaceru.",
                "priority": "medium",
            })

        if hobby_hours < 1:
            suggestions.append({
                "area": "hobby",
                "issue": "Zero czasu na hobby",
                "suggestion": "Zarezerwuj 2x1h w tygodniu na coś co sprawia Ci przyjemność.",
                "priority": "medium",
            })

        if rest_hours < 7 * 7:  # mniej niż 7h dziennie
            suggestions.append({
                "area": "odpoczynek",
                "issue": f"Tylko {rest_hours}h odpoczynku",
                "suggestion": "Sen i odpoczynek to podstawa produktywności. Minimum 7h snu.",
                "priority": "high",
            })

        # Overdue contacts
        if balance["overdue_count"] > 0:
            suggestions.append({
                "area": "kontakty",
                "issue": f"{balance['overdue_count']} osób czeka na kontakt",
                "suggestion": "Zrób 'social hour' — 1h na nadrobienie zaległych kontaktów.",
                "priority": "high" if balance["overdue_count"] > 3 else "medium",
            })

        # Energy optimization
        if energy["peak_hour"] > 0:
            suggestions.append({
                "area": "produktywność",
                "issue": f"Szczyt energii o {energy['peak_hour']}:00",
                "suggestion": f"Planuj deep work na {energy['peak_hour']}:00. Meetingi przenieś na godziny niższej energii.",
                "priority": "low",
            })

        return {
            "suggestions": suggestions,
            "total_issues": len(suggestions),
            "critical_count": sum(1 for s in suggestions if s["priority"] == "high"),
        }

    # ── Full Report ───────────────────────────────────────────────────────

    def full_report(self) -> str:
        """Pełny raport insights jako tekst."""
        score = self.life_score()
        energy = self.energy_patterns()
        thoughts = self.thought_triggers()
        snacks = self.snacking_patterns()
        overdue_pred = self.predict_overdue(3)
        optimization = self.weekly_optimization()

        lines = [
            "🧬 LIFE INSIGHTS REPORT",
            "=" * 50,
            "",
            f"🎯 LIFE SCORE: {score['total']}/100 — {score['grade']}",
        ]

        for area, val in score["breakdown"].items():
            bar = "█" * (val // 2) + "░" * (10 - val // 2)
            lines.append(f"   {area:15s} [{bar}] {val}")

        lines.extend([
            "",
            "⚡ ENERGIA",
            f"   Peak: {energy['peak_hour']}:00 | Slump: {energy['slump_hour']}:00",
            f"   Najlepszy dzień: {energy['best_day']}",
            f"   💡 {energy['recommendation']}",
            "",
            "🧠 NATARCZYWE MYŚLI",
        ])

        if "message" in thoughts:
            lines.append(f"   {thoughts['message']}")
        else:
            lines.append(f"   Średnia intensywność: {thoughts['avg_intensity']}/10")
            lines.append(f"   Najgorsza pora: {thoughts['worst_hour']}:00 | Dzień: {thoughts['worst_day']}")
            lines.append(f"   Trend: {thoughts['trend_7d']}")
            lines.append(f"   💡 {thoughts['recommendation']}")

        lines.extend([
            "",
            "🍪 PODJADANIE",
        ])
        if "message" in snacks:
            lines.append(f"   {snacks['message']}")
        else:
            lines.append(f"   Najgorsza pora: {snacks['worst_hour']}:00")
            lines.append(f"   Korelacja z myślami: {snacks['thought_correlation_pct']}%")
            lines.append(f"   💡 {snacks['recommendation']}")

        lines.extend([
            "",
            "🔮 PREDYKCJE OVERDUE (3 dni)",
        ])
        if overdue_pred:
            for p in overdue_pred[:5]:
                icon = "🔴" if p["urgency"] == "critical" else "🟡"
                lines.append(f"   {icon} {p['name']} — overdue za {p['will_be_overdue_in_days']}d")
        else:
            lines.append("   ✅ Nikt nie będzie overdue w ciągu 3 dni")

        lines.extend([
            "",
            "📈 OPTYMALIZACJE",
        ])
        for s in optimization["suggestions"]:
            icon = "🔴" if s["priority"] == "high" else "🟡" if s["priority"] == "medium" else "🟢"
            lines.append(f"   {icon} [{s['area']}] {s['suggestion']}")

        return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Life Insights Engine — CLI")
        print()
        print("Komendy:")
        print("  score         — Life Score 0-100")
        print("  energy        — wzorce energii")
        print("  thoughts      — analiza natarczywych myśli")
        print("  snacking      — analiza podjadania")
        print("  overdue       — predykcja overdue (3 dni)")
        print("  optimize      — sugestie optymalizacji tygodniowej")
        print("  report        — pełny raport")
        return

    cmd = sys.argv[1]
    db_path = str(LIFE_DIR / "data" / "hermes_integration.db")
    if not os.path.exists(db_path):
        db_path = str(LIFE_DIR / "data" / "bot_life.db")

    db = LifeDB(db_path)
    engine = InsightsEngine(db)

    if cmd == "score":
        score = engine.life_score()
        print(f"🎯 Life Score: {score['total']}/100 — {score['grade']}")
        for area, val in score["breakdown"].items():
            bar = "█" * (val // 2) + "░" * (10 - val // 2)
            print(f"   {area:15s} [{bar}] {val}")

    elif cmd == "energy":
        energy = engine.energy_patterns()
        print(f"⚡ Peak: {energy['peak_hour']}:00 | Slump: {energy['slump_hour']}:00")
        print(f"   Najlepszy dzień: {energy['best_day']}")
        print(f"   💡 {energy['recommendation']}")

    elif cmd == "thoughts":
        thoughts = engine.thought_triggers()
        if "message" in thoughts:
            print(thoughts["message"])
        else:
            print(f"🧠 Zalogowanych: {thoughts['total_logged']}")
            print(f"   Śr. intensywność: {thoughts['avg_intensity']}/10")
            print(f"   Najgorsza pora: {thoughts['worst_hour']}:00")
            print(f"   Trend: {thoughts['trend_7d']}")
            print(f"   💡 {thoughts['recommendation']}")

    elif cmd == "snacking":
        snacks = engine.snacking_patterns()
        if "message" in snacks:
            print(snacks["message"])
        else:
            print(f"🍪 Zalogowanych: {snacks['total_logged']}")
            print(f"   Najgorsza pora: {snacks['worst_hour']}:00")
            print(f"   Korelacja z myślami: {snacks['thought_correlation_pct']}%")
            print(f"   💡 {snacks['recommendation']}")

    elif cmd == "overdue":
        predictions = engine.predict_overdue(3)
        if not predictions:
            print("✅ Nikt nie będzie overdue w ciągu 3 dni")
        for p in predictions:
            icon = "🔴" if p["urgency"] == "critical" else "🟡"
            print(f"  {icon} {p['name']} ({p['category']}) — overdue za {p['will_be_overdue_in_days']}d")

    elif cmd == "optimize":
        opt = engine.weekly_optimization()
        print(f"📈 Znaleziono {opt['total_issues']} obszarów do poprawy ({opt['critical_count']} krytycznych)")
        for s in opt["suggestions"]:
            icon = "🔴" if s["priority"] == "high" else "🟡" if s["priority"] == "medium" else "🟢"
            print(f"  {icon} [{s['area']}] {s['suggestion']}")

    elif cmd == "report":
        print(engine.full_report())

    else:
        print(f"❌ Nieznana komenda: {cmd}")


if __name__ == "__main__":
    main()
