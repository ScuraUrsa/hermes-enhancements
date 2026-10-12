---
name: weather
description: "Pogoda i prognoza (weather, forecast) dla dowolnego miejsca; domyślnie Gdańsk. Uruchom ~/.hermes/scripts/weather.py zamiast zgadywać lub szukać w sieci."
version: 1.0.0
author: Claude Code (for Filip)
platforms: [linux]
metadata:
  hermes:
    tags: [pogoda, prognoza, prognoza pogody, czy będzie padać, deszcz, temperatura, wiatr, parasol, weather, forecast, rain, temperature]
---

# weather — pogoda (Filip, 2026-10-12)

Use this whenever Filip asks about the weather: "jaka pogoda", "jaka jutro pogoda w Gdańsku?", "czy będzie padać?",
"potrzebuję parasola?", "prognoza na weekend w Zadarze", "weather in Split tomorrow". Do not answer from memory and
do not web-search: run the script. It needs no API key (Open-Meteo, falls back to wttr.in by itself).

## Run

`python3 ~/.hermes/scripts/weather.py [mode] [N] [place]`

| Filip asks about | Command |
|---|---|
| now / "jaka pogoda" | `weather.py` (now + today's summary) |
| today | `weather.py dzis [place]` |
| tomorrow | `weather.py jutro [place]` |
| next N days, weekend, week (N ≤ 7) | `weather.py dni N [place]` |
| hour by hour today, "o której przestanie padać" | `weather.py godzinowo [place]` |
| one line (briefs, notifications) | `weather.py brief [place]` |

- Place: any city name (`Zadar`, `Kraków`, `"Split, Croatia"`). No place, "dom" or "tutaj" means **Gdańsk** (home).
- `--json` gives structured data if you need to compute something (for example, which day of the weekend is driest).
- For a weekday or weekend: count the days from today and use `dni N`, then talk only about the days asked for.
- Exit code 2 + "nie znam miejsca" means geocoding found nothing: ask Filip for a nearby bigger city.

## Answer

Reply in Polish, short: temperature (and odczuwalna if it differs by ≥ 3°C), sky, rain in mm and probability,
wind (mention gusts ≥ 50 km/h), sunrise/sunset only if relevant. Answer the actual question first
("Tak, weź parasol: 2.5 mm, 88 % szans po 15:00"). In voice replies use one or two sentences and no tables.
