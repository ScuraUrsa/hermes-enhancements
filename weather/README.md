# weather — Hermes weather skill

Source of truth for the skill deployed on the prod VM (2026-10-12):

| File | Deployed to |
|---|---|
| `weather.py` | `~/.hermes/scripts/weather.py` (mode 755) |
| `SKILL.md` | `~/.hermes/skills/productivity/weather/SKILL.md` |

`weather.py` uses only the Python standard library: Open-Meteo (forecast + geocoding, no key), falling back to
wttr.in. Default place Gdańsk (54.35, 18.65, Europe/Warsaw); `WEATHER_LAT/LON/NAME/TZ` override it.
Modes: `teraz`, `dzis`, `jutro`, `dni N`, `godzinowo`, `brief [--date YYYY-MM-DD]`; `--json`, `--en`,
`--source open-meteo|wttr`. The timeplane Informator calls `weather.py brief --date <day>` for its 🌦 line
(hermes-timeplane branch `claude/project-thread-xnujsm`).

Deploy: `scp weather.py SKILL.md ubuntu@<vm>:/tmp/ && ssh ubuntu@<vm> 'install -m 755 /tmp/weather.py ~/.hermes/scripts/ && install -Dm 644 /tmp/SKILL.md ~/.hermes/skills/productivity/weather/SKILL.md'`
