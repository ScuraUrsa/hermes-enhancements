#!/usr/bin/env python3
"""weather.py — pogoda dla Hermesa (Open-Meteo, bez klucza; zapasowo wttr.in). Tylko biblioteka standardowa.

Użycie:
  weather.py                      # teraz, Gdańsk
  weather.py jutro                # jutro, Gdańsk
  weather.py dzis Zadar           # dziś w Zadarze
  weather.py dni 3 Kraków         # 3 dni (1–7)
  weather.py godzinowo            # godzina po godzinie do końca dnia
  weather.py tomorrow --place "Split, Croatia" --json

Tryby: now/teraz, today/dzis/dziś, tomorrow/jutro, days/dni N, hourly/godzinowo, brief/krotko (1 linia).
Domyślna lokalizacja: Gdańsk (54.35, 18.65, Europe/Warsaw); zmienne WEATHER_LAT/WEATHER_LON/WEATHER_NAME/WEATHER_TZ ją nadpisują.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

UA = {"User-Agent": "hermes-weather/1.0"}
TIMEOUT = 12
DEFAULT = {
    "name": os.environ.get("WEATHER_NAME", "Gdańsk"),
    "lat": float(os.environ.get("WEATHER_LAT", "54.35")),
    "lon": float(os.environ.get("WEATHER_LON", "18.65")),
    "tz": os.environ.get("WEATHER_TZ", "Europe/Warsaw"),
    "country": "Polska",
}
HOME_ALIASES = {"", "dom", "home", "gdansk", "gdańsk", "tutaj", "here"}
MODES = {
    "now": "now", "teraz": "now", "current": "now",
    "today": "today", "dzis": "today", "dziś": "today", "dzisiaj": "today",
    "tomorrow": "tomorrow", "jutro": "tomorrow",
    "days": "days", "dni": "days", "week": "days", "tydzien": "days", "tydzień": "days",
    "hourly": "hourly", "godzinowo": "hourly", "hours": "hourly",
    "brief": "brief", "krotko": "brief", "krótko": "brief",
}

WMO_PL = {
    0: "bezchmurnie", 1: "przeważnie pogodnie", 2: "częściowe zachmurzenie", 3: "pochmurno",
    45: "mgła", 48: "mgła osadzająca szadź",
    51: "słaba mżawka", 53: "mżawka", 55: "gęsta mżawka", 56: "marznąca mżawka", 57: "gęsta marznąca mżawka",
    61: "słaby deszcz", 63: "deszcz", 65: "ulewny deszcz", 66: "marznący deszcz", 67: "silny marznący deszcz",
    71: "słaby śnieg", 73: "śnieg", 75: "intensywny śnieg", 77: "ziarna śniegu",
    80: "przelotny słaby deszcz", 81: "przelotny deszcz", 82: "gwałtowne ulewy",
    85: "przelotny śnieg", 86: "intensywne przelotne opady śniegu",
    95: "burza", 96: "burza z gradem", 99: "silna burza z gradem",
}
WMO_EN = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "rime fog",
    51: "light drizzle", 53: "drizzle", 55: "dense drizzle", 56: "freezing drizzle", 57: "dense freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "violent showers", 85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}
WEEKDAY_PL = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]
WIND_DIR_PL = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(place):
    if place.strip().lower() in HOME_ALIASES:
        return dict(DEFAULT)
    # "Split, Croatia" -> search "Split", prefer a result whose country/admin matches the rest
    name, _, hint = place.partition(",")
    q = urllib.parse.urlencode({"name": name.strip(), "count": 10, "language": "pl", "format": "json"})
    res = (get_json("https://geocoding-api.open-meteo.com/v1/search?" + q).get("results") or [])
    if not res:
        raise LookupError(f"nie znam miejsca: {place}")
    hint = hint.strip().lower()
    if hint:
        res = [r for r in res if hint in " ".join(str(r.get(k, "")) for k in ("country", "admin1", "country_code")).lower()] or res
    r = res[0]
    return {"name": r["name"], "lat": r["latitude"], "lon": r["longitude"],
            "tz": r.get("timezone") or "auto", "country": r.get("country", ""), "admin1": r.get("admin1", "")}


def wind_dir(deg):
    return None if deg is None else WIND_DIR_PL[int((deg % 360) / 45 + 0.5) % 8]


def open_meteo(loc, days):
    q = urllib.parse.urlencode({
        "latitude": loc["lat"], "longitude": loc["lon"], "timezone": loc["tz"] or "auto",
        "forecast_days": max(days, 2),
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,"
                   "cloud_cover,wind_speed_10m,wind_gusts_10m,wind_direction_10m",
        "hourly": "temperature_2m,apparent_temperature,precipitation,precipitation_probability,weather_code,"
                  "cloud_cover,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
                 "apparent_temperature_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,"
                 "wind_gusts_10m_max,sunrise,sunset",
    })
    d = get_json("https://api.open-meteo.com/v1/forecast?" + q)
    c, h, dy = d["current"], d["hourly"], d["daily"]
    hourly = [{
        "time": t, "temp": h["temperature_2m"][i], "feels": h["apparent_temperature"][i],
        "precip_mm": h["precipitation"][i], "precip_prob": h["precipitation_probability"][i],
        "code": h["weather_code"][i], "clouds": h["cloud_cover"][i], "wind_kmh": h["wind_speed_10m"][i],
    } for i, t in enumerate(h["time"])]
    out_days = []
    for i, day in enumerate(dy["time"]):
        clouds = [x["clouds"] for x in hourly if x["time"].startswith(day) and x["clouds"] is not None]
        # daily weather_code is the day's worst hour; describe the day by its most common daytime (07–20) code
        dcodes = [x["code"] for x in hourly if x["time"].startswith(day) and "07" <= x["time"][11:13] <= "20"
                  and x["code"] is not None]
        code = max(set(dcodes), key=lambda k: (dcodes.count(k), k)) if dcodes else dy["weather_code"][i]
        worst = dy["weather_code"][i]
        prob = dy["precipitation_probability_max"][i]
        out_days.append({
            "date": day, "code": code,
            "worst_code": worst if worst != code and worst >= 51 and (prob or 0) >= 30 else None,
            "tmin": dy["temperature_2m_min"][i], "tmax": dy["temperature_2m_max"][i],
            "feels_min": dy["apparent_temperature_min"][i], "feels_max": dy["apparent_temperature_max"][i],
            "precip_mm": dy["precipitation_sum"][i], "precip_prob": dy["precipitation_probability_max"][i],
            "wind_kmh": dy["wind_speed_10m_max"][i], "gusts_kmh": dy["wind_gusts_10m_max"][i],
            "clouds": round(sum(clouds) / len(clouds)) if clouds else None,
            "sunrise": dy["sunrise"][i][11:16], "sunset": dy["sunset"][i][11:16],
        })
    current = {
        "time": c["time"], "temp": c["temperature_2m"], "feels": c["apparent_temperature"],
        "humidity": c["relative_humidity_2m"], "precip_mm": c["precipitation"], "code": c["weather_code"],
        "clouds": c["cloud_cover"], "wind_kmh": c["wind_speed_10m"], "gusts_kmh": c["wind_gusts_10m"],
        "wind_dir": wind_dir(c.get("wind_direction_10m")),
    }
    hour_now = c["time"][:13]
    current["precip_prob"] = next((x["precip_prob"] for x in hourly if x["time"][:13] == hour_now), None)
    return {"source": "open-meteo", "timezone": d.get("timezone"), "current": current, "days": out_days, "hourly": hourly}


def wttr(loc, days):
    where = f'{loc["lat"]},{loc["lon"]}'
    d = get_json(f"https://wttr.in/{urllib.parse.quote(where)}?format=j1&lang=pl")
    cc = d["current_condition"][0]
    desc = (cc.get("lang_pl") or cc.get("weatherDesc") or [{"value": ""}])[0]["value"]
    hourly, out_days = [], []
    for w in d.get("weather", [])[:days]:
        hs = w.get("hourly", [])
        for x in hs:
            hourly.append({"time": f'{w["date"]}T{int(x["time"]) // 100:02d}:00', "temp": float(x["tempC"]),
                           "feels": float(x["FeelsLikeC"]), "precip_mm": float(x["precipMM"]),
                           "precip_prob": int(x.get("chanceofrain", 0)), "code": None,
                           "desc": (x.get("lang_pl") or x.get("weatherDesc") or [{"value": ""}])[0]["value"],
                           "clouds": int(x["cloudcover"]), "wind_kmh": float(x["windspeedKmph"])})
        ast = (w.get("astronomy") or [{}])[0]
        out_days.append({
            "date": w["date"], "code": None,
            "desc": (hs[len(hs) // 2].get("lang_pl") or hs[len(hs) // 2]["weatherDesc"])[0]["value"] if hs else "",
            "tmin": float(w["mintempC"]), "tmax": float(w["maxtempC"]),
            "feels_min": min((float(x["FeelsLikeC"]) for x in hs), default=None),
            "feels_max": max((float(x["FeelsLikeC"]) for x in hs), default=None),
            "precip_mm": round(sum(float(x["precipMM"]) for x in hs), 1),
            "precip_prob": max((int(x.get("chanceofrain", 0)) for x in hs), default=None),
            "wind_kmh": max((float(x["windspeedKmph"]) for x in hs), default=None),
            "gusts_kmh": max((float(x.get("WindGustKmph", 0)) for x in hs), default=None),
            "clouds": round(sum(int(x["cloudcover"]) for x in hs) / len(hs)) if hs else None,
            "sunrise": _ampm(ast.get("sunrise")), "sunset": _ampm(ast.get("sunset")),
        })
    current = {"time": cc.get("localObsDateTime", ""), "temp": float(cc["temp_C"]), "feels": float(cc["FeelsLikeC"]),
               "humidity": int(cc["humidity"]), "precip_mm": float(cc["precipMM"]), "code": None, "desc": desc,
               "clouds": int(cc["cloudcover"]), "wind_kmh": float(cc["windspeedKmph"]), "gusts_kmh": None,
               "wind_dir": cc.get("winddir16Point"), "precip_prob": None}
    return {"source": "wttr.in", "timezone": None, "current": current, "days": out_days, "hourly": hourly}


def _ampm(s):
    try:
        return dt.datetime.strptime(s.strip(), "%I:%M %p").strftime("%H:%M")
    except (AttributeError, ValueError):
        return s


def desc(x, en=False):
    if x.get("code") is not None:
        return (WMO_EN if en else WMO_PL).get(x["code"], f"kod {x['code']}")
    return x.get("desc", "")


def n(v, unit="", nd=0):
    if v is None:
        return "?"
    return f"{round(v, nd) if nd else round(v):g}{unit}"


def fmt_now(loc, data, en=False):
    c = data["current"]
    t = c["time"][11:16] if "T" in c["time"] else c["time"]
    prob = f" ({n(c['precip_prob'], '%')})" if c.get("precip_prob") is not None else ""
    gust = f", porywy {n(c['gusts_kmh'])}" if c.get("gusts_kmh") else ""
    wd = f" z {c['wind_dir']}" if c.get("wind_dir") else ""
    return (f"{loc['name']} — teraz ({t}): {n(c['temp'], '°C')} (odczuwalna {n(c['feels'], '°C')}), {desc(c, en)}, "
            f"zachmurzenie {n(c['clouds'], '%')}, wiatr {n(c['wind_kmh'])} km/h{wd}{gust}, "
            f"opady {n(c['precip_mm'], ' mm', 1)}{prob}, wilgotność {n(c['humidity'], '%')}.")


def fmt_day(d, en=False):
    day = dt.date.fromisoformat(d["date"])
    gust = f" (porywy {n(d['gusts_kmh'])})" if d.get("gusts_kmh") else ""
    worst = f", miejscami {desc({'code': d['worst_code']}, en)}" if d.get("worst_code") else ""
    return (f"{WEEKDAY_PL[day.weekday()]} {day:%d.%m}: {n(d['tmin'])}…{n(d['tmax'], '°C')} "
            f"(odczuwalna {n(d['feels_min'])}…{n(d['feels_max'], '°C')}), {desc(d, en)}{worst}, "
            f"opady {n(d['precip_mm'], ' mm', 1)} (szansa {n(d['precip_prob'], '%')}), "
            f"wiatr do {n(d['wind_kmh'])} km/h{gust}, zachmurzenie {n(d['clouds'], '%')}, "
            f"wschód {d['sunrise']}, zachód {d['sunset']}.")


def fmt_hourly(loc, data, en=False):
    now_h = data["current"]["time"][:13]
    today = data["days"][0]["date"]
    rows = [x for x in data["hourly"] if x["time"].startswith(today) and x["time"][:13] >= now_h] or \
           [x for x in data["hourly"] if x["time"].startswith(today)]
    lines = [f"{loc['name']} — dziś godzinowo:"]
    for x in rows:
        lines.append(f"{x['time'][11:16]} {n(x['temp'], '°C')} (odcz. {n(x['feels'])}), {desc(x, en)}, "
                     f"opady {n(x['precip_mm'], ' mm', 1)} ({n(x['precip_prob'], '%')}), "
                     f"wiatr {n(x['wind_kmh'])} km/h, chmury {n(x['clouds'], '%')}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pogoda (Open-Meteo, zapasowo wttr.in)")
    ap.add_argument("words", nargs="*", help="[tryb] [N] [miejsce] np. 'jutro Zadar', 'dni 3 Kraków'")
    ap.add_argument("--place", "-p", help="miejsce (domyślnie Gdańsk)")
    ap.add_argument("--mode", "-m", choices=sorted(set(MODES.values())))
    ap.add_argument("--days", "-d", type=int, help="liczba dni 1–7 (tryb days)")
    ap.add_argument("--json", action="store_true", help="wynik jako JSON")
    ap.add_argument("--en", action="store_true", help="opisy pogody po angielsku")
    ap.add_argument("--date", help="YYYY-MM-DD: dzień dla trybu brief (domyślnie dziś)")
    ap.add_argument("--source", choices=["auto", "open-meteo", "wttr"], default="auto")
    a = ap.parse_args(argv)

    words = list(a.words)
    mode = a.mode
    if words and words[0].lower() in MODES and not mode:
        mode = MODES[words.pop(0).lower()]
    ndays = a.days
    if words and words[0].isdigit():
        ndays = int(words.pop(0))
        mode = mode or "days"
    mode = mode or ("days" if ndays else "now")
    ndays = max(1, min(7, ndays or (3 if mode == "days" else 2)))
    place = a.place or " ".join(words)

    try:
        loc = geocode(place)
    except Exception as e:  # geocoding down or unknown place
        if place.strip():
            print(f"BŁĄD: {e}", file=sys.stderr)
            return 2
        loc = dict(DEFAULT)

    data, errors = None, []
    for src in (["open-meteo", "wttr"] if a.source == "auto" else [a.source]):
        try:
            data = open_meteo(loc, ndays) if src == "open-meteo" else wttr(loc, max(ndays, 2))
            break
        except Exception as e:
            errors.append(f"{src}: {e}")
    if data is None:
        print("BŁĄD: brak danych pogodowych (" + "; ".join(errors) + ")", file=sys.stderr)
        return 1

    if a.json:
        sel = {"now": data["days"][:1], "today": data["days"][:1], "brief": data["days"][:1],
               "tomorrow": data["days"][1:2],
               "days": data["days"][:ndays], "hourly": data["days"][:1]}[mode]
        out = {"place": loc, "mode": mode, "source": data["source"], "current": data["current"], "days": sel}
        if mode == "hourly":
            out["hourly"] = [x for x in data["hourly"] if x["time"].startswith(data["days"][0]["date"])]
        if errors:
            out["fallback_errors"] = errors
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    head = f"{loc['name']}" + (f" ({loc['country']})" if loc.get("country") and loc["country"] != "Polska" else "")
    loc = dict(loc, name=head)
    if mode == "now":
        text = fmt_now(loc, data, a.en) + "\nDziś: " + fmt_day(data["days"][0], a.en)
    elif mode == "today":
        text = f"{head} — dziś: " + fmt_day(data["days"][0], a.en) + "\n" + fmt_now(loc, data, a.en)
    elif mode == "tomorrow":
        text = f"{head} — jutro: " + fmt_day(data["days"][1], a.en)
    elif mode == "hourly":
        text = fmt_hourly(loc, data, a.en)
    elif mode == "brief":  # one line, no source tag (timeplane morning brief)
        d = next((x for x in data["days"] if x["date"] == a.date), data["days"][0])
        worst = f", miejscami {desc({'code': d['worst_code']}, a.en)}" if d.get("worst_code") else ""
        print(f"{head}: {n(d['tmin'])}…{n(d['tmax'], '°C')}, {desc(d, a.en)}{worst}, "
              f"opady {n(d['precip_mm'], ' mm', 1)} ({n(d['precip_prob'], '%')}), wiatr do {n(d['wind_kmh'])} km/h")
        return 0
    else:
        text = f"{head} — prognoza na {ndays} dni:\n" + "\n".join(fmt_day(d, a.en) for d in data["days"][:ndays])
    print(text + f"\n[źródło: {data['source']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
