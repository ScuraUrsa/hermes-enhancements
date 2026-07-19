"""
Hermes Travel Plugin — live Google Places + Open-Meteo + ExchangeRate API.

Installs as a Hermes skill. No Node.js required. Python stdlib only.

Installation:
    cp travel_plugin.py ~/.hermes/skills/travel/SKILL.md  # (rename to plugin.py)
    # Set API keys in ~/.hermes/.env:
    # GOOGLE_PLACES_API_KEY=...

Usage by Hermes:
    "Find Italian restaurants in Gdańsk"
    "What events are in Warsaw on July 25?"
    "Plan a date night in Sopot"
    "Find a hotel in Kraków for the weekend"
    "What's the weather in Gdańsk?"
    "Convert 200 PLN to EUR"
"""

import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

CITY_COORDS = {
    "gdańsk": (54.3520, 18.6466), "sopot": (54.4416, 18.5601),
    "gdynia": (54.5189, 18.5305), "warszawa": (52.2297, 21.0122),
    "kraków": (50.0647, 19.9450), "wrocław": (51.1079, 17.0385),
    "poznań": (52.4064, 16.9252), "łódź": (51.7592, 19.4560),
    "katowice": (50.2649, 19.0238), "zakopane": (49.2992, 19.9496),
    "berlin": (52.5200, 13.4050), "prague": (50.0755, 14.4378),
    "vienna": (48.2082, 16.3738), "paris": (48.8566, 2.3522),
    "london": (51.5074, -0.1278), "barcelona": (41.3874, 2.1686),
    "rome": (41.9028, 12.4964), "amsterdam": (52.3676, 4.9041),
    "budapest": (47.4979, 19.0402), "copenhagen": (55.6761, 12.5683),
    "stockholm": (59.3293, 18.0686), "oslo": (59.9139, 10.7522),
    "helsinki": (60.1699, 24.9384), "lisbon": (38.7223, -9.1393),
    "madrid": (40.4168, -3.7038), "dublin": (53.3498, -6.2603),
    "brussels": (50.8503, 4.3517), "athens": (37.9838, 23.7275),
    "milan": (45.4642, 9.1900), "munich": (48.1351, 11.5820),
    "zurich": (47.3769, 8.5417), "dubrovnik": (42.6507, 18.0944),
    "split": (43.5081, 16.4402), "tallinn": (59.4370, 24.7536),
    "riga": (56.9496, 24.1052), "vilnius": (54.6872, 25.2797),
    "lviv": (49.8397, 24.0297), "bucuresti": (44.4268, 26.1025),
    "sofia": (42.6977, 23.3219), "belgrade": (44.7866, 20.4489),
    "zagreb": (45.8150, 15.9819), "ljubljana": (46.0569, 14.5058),
    "bratislava": (48.1486, 17.1077), "reykjavik": (64.1466, -21.9426),
    "malaga": (36.7213, -4.4214), "valencia": (39.4699, -0.3763),
    "porto": (41.1579, -8.6291), "naples": (40.8518, 14.2681),
    "florence": (43.7696, 11.2558), "venice": (45.4408, 12.3155),
    "seville": (37.3891, -5.9845), "granada": (37.1773, -3.5986),
    "nice": (43.7102, 7.2620), "lyon": (45.7640, 4.8357),
    "hamburg": (53.5511, 9.9937), "frankfurt": (50.1109, 8.6821),
    "cologne": (50.9375, 6.9603), "dresden": (51.0504, 13.7373),
    "edinburgh": (55.9533, -3.1883), "manchester": (53.4808, -2.2426),
    "birmingham": (52.4862, -1.8904), "liverpool": (53.4084, -2.9916),
    "glasgow": (55.8642, -4.2518), "cardiff": (51.4816, -3.1791),
    "belfast": (54.5973, -5.9301), "antwerp": (51.2194, 4.4025),
    "rotterdam": (51.9244, 4.4777), "the hague": (52.0705, 4.3007),
    "geneva": (46.2044, 6.1432), "bern": (46.9480, 7.4474),
    "salzburg": (47.8095, 13.0550), "innsbruck": (47.2692, 11.4041),
    "gdansk": (54.3520, 18.6466), "warsaw": (52.2297, 21.0122),
    "cracow": (50.0647, 19.9450), "wroclaw": (51.1079, 17.0385),
    "poznan": (52.4064, 16.9252), "lodz": (51.7592, 19.4560),
    "katowice": (50.2649, 19.0238), "zakopane": (49.2992, 19.9496),
}

CUISINE_MAP = {
    "włoska": "włoska", "wloska": "włoska", "italian": "włoska",
    "polska": "polska", "polish": "polska",
    "japońska": "japońska", "japonska": "japońska", "japanese": "japońska", "sushi": "japońska",
    "meksykańska": "meksykańska", "meksykanska": "meksykańska", "mexican": "meksykańska",
    "francuska": "francuska", "french": "francuska",
    "rybna": "rybna", "seafood": "rybna",
    "steki": "steki", "steak": "steki", "steakhouse": "steki",
    "wegańska": "wegańska", "weganska": "wegańska", "vegan": "wegańska",
    "fine dining": "fine dining", "fine_dining": "fine dining",
    "wine bar": "wine bar", "winebar": "wine bar",
    "indyjska": "indyjska", "indian": "indyjska",
    "chińska": "chińska", "chinese": "chińska",
    "tajska": "tajska", "thai": "tajska",
    "grecka": "grecka", "greek": "grecka",
    "hiszpańska": "hiszpańska", "spanish": "hiszpańska",
    "turecka": "turecka", "turkish": "turecka",
    "wietnamska": "wietnamska", "vietnamese": "wietnamska",
    "koreańska": "koreańska", "korean": "koreańska",
    "śródziemnomorska": "śródziemnomorska", "mediterranean": "śródziemnomorska",
    "amerykańska": "amerykańska", "american": "amerykańska",
    "burgery": "burgery", "burgers": "burgery",
    "pizza": "pizza",
    "kawa": "kawa", "coffee": "kawa", "cafe": "kawa",
    "lody": "lody", "ice cream": "lody",
    "piekarnia": "piekarnia", "bakery": "piekarnia",
    "owoce morza": "owoce morza",
    "tapas": "tapas",
    "grill": "grill", "bbq": "grill", "barbecue": "grill",
}


# ═══════════════════════════════════════════════════════════════
# API CLIENTS
# ═══════════════════════════════════════════════════════════════

def _get_json(url: str, headers: dict = None, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def _post_json(url: str, body: dict, headers: dict = None, timeout: int = 10) -> dict:
    hdrs = headers or {}
    hdrs["Content-Type"] = "application/json"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# GOOGLE PLACES API (New) — LIVE
# ═══════════════════════════════════════════════════════════════

def _google_places_search(
    query: str,
    max_results: int = 10,
    min_rating: float = 4.0,
    price_levels: list[str] | None = None,
    open_now: bool = False,
) -> list[dict]:
    """Search Google Places (New) Text Search."""
    if not GOOGLE_API_KEY:
        return [{"error": "GOOGLE_PLACES_API_KEY not set"}]

    field_mask = (
        "places.displayName,places.formattedAddress,places.rating,"
        "places.userRatingCount,places.priceLevel,places.websiteUri,"
        "places.googleMapsUri,places.regularOpeningHours.openNow,"
        "places.editorialSummary,places.primaryType,places.photos"
    )

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": field_mask,
    }

    body: dict = {
        "textQuery": query,
        "maxResultCount": max_results,
    }
    if min_rating:
        body["minRating"] = min_rating
    if price_levels:
        body["priceLevels"] = price_levels
    if open_now:
        body["openNow"] = True

    data = _post_json(
        "https://places.googleapis.com/v1/places:searchText",
        body, headers, timeout=15,
    )

    if "error" in data:
        return [data]

    results = []
    for p in data.get("places", []):
        results.append({
            "name": p.get("displayName", {}).get("text", "?"),
            "address": p.get("formattedAddress", "?"),
            "rating": p.get("rating"),
            "reviews": p.get("userRatingCount", 0),
            "price_level": p.get("priceLevel", "?"),
            "open_now": p.get("regularOpeningHours", {}).get("openNow"),
            "summary": (p.get("editorialSummary", {}) or {}).get("text", ""),
            "website": p.get("websiteUri", ""),
            "maps": p.get("googleMapsUri", ""),
            "type": p.get("primaryType", ""),
        })
    return results


# ═══════════════════════════════════════════════════════════════
# OPEN-METEO — LIVE (free, no key)
# ═══════════════════════════════════════════════════════════════

def _get_weather_live(lat: float, lng: float) -> dict:
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lng}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
        f"&timezone=Europe/Warsaw&forecast_days=3"
    )
    data = _get_json(url)
    if "error" in data:
        return data

    codes = {
        0: ("Bezchmurnie", "☀️"), 1: ("Prawie bezchmurnie", "🌤️"),
        2: ("Częściowo słonecznie", "⛅"), 3: ("Pochmurno", "☁️"),
        45: ("Mgła", "🌫️"), 48: ("Szadź", "🌫️"),
        51: ("Lekka mżawka", "🌦️"), 53: ("Mżawka", "🌦️"), 55: ("Gęsta mżawka", "🌦️"),
        61: ("Lekki deszcz", "🌧️"), 63: ("Deszcz", "🌧️"), 65: ("Ulewa", "🌧️"),
        71: ("Lekki śnieg", "🌨️"), 73: ("Śnieg", "🌨️"), 75: ("Śnieżyca", "🌨️"),
        80: ("Przelotne opady", "🌦️"), 95: ("Burza", "⛈️"), 96: ("Burza z gradem", "⛈️"),
    }

    current = data.get("current", {})
    daily = data.get("daily", {})

    code = current.get("weather_code", 0)
    desc, icon = codes.get(code, (f"Kod {code}", "❓"))

    forecast = []
    for i in range(min(3, len(daily.get("time", [])))):
        fc_code = daily.get("weather_code", [0])[i] if i < len(daily.get("weather_code", [])) else 0
        fc_desc, fc_icon = codes.get(fc_code, (f"Kod {fc_code}", "❓"))
        forecast.append({
            "date": daily.get("time", [])[i] if i < len(daily.get("time", [])) else "?",
            "temp_max": daily.get("temperature_2m_max", [])[i] if i < len(daily.get("temperature_2m_max", [])) else "?",
            "temp_min": daily.get("temperature_2m_min", [])[i] if i < len(daily.get("temperature_2m_min", [])) else "?",
            "rain_prob": daily.get("precipitation_probability_max", [])[i] if i < len(daily.get("precipitation_probability_max", [])) else "?",
            "description": fc_desc,
            "icon": fc_icon,
        })

    return {
        "temp": current.get("temperature_2m", "?"),
        "humidity": current.get("relative_humidity_2m", "?"),
        "wind": current.get("wind_speed_10m", "?"),
        "description": desc,
        "icon": icon,
        "forecast": forecast,
        "source": "Open-Meteo (live)",
    }


# ═══════════════════════════════════════════════════════════════
# EXCHANGE RATE — LIVE (free, no key)
# ═══════════════════════════════════════════════════════════════

def _get_currency_live(base: str = "PLN") -> dict:
    return _get_json(f"https://open.er-api.com/v6/latest/{base}")


# ═══════════════════════════════════════════════════════════════
# TOOLS — public API for Hermes
# ═══════════════════════════════════════════════════════════════

def find_restaurants(
    city: str,
    cuisine: str = None,
    romantic: bool = False,
    max_price: str = None,
    open_now: bool = False,
    limit: int = 10,
) -> dict:
    """Find restaurants in a city. Uses Google Places API if key is set.

    Args:
        city: 'Gdańsk', 'Warszawa', 'Berlin', etc.
        cuisine: 'włoska', 'japońska', 'polska', etc.
        romantic: filter for romantic atmosphere
        max_price: '$', '$$', '$$$', '$$$$'
        open_now: only show currently open
        limit: max results
    """
    query_parts = ["restaurant"]
    if cuisine:
        cuisine_norm = CUISINE_MAP.get(cuisine.lower(), cuisine)
        query_parts.append(cuisine_norm)
    if romantic:
        query_parts.append("romantic")
    query_parts.append("in")
    query_parts.append(city)

    query = " ".join(query_parts)

    price_map = {
        "$": ["PRICE_LEVEL_INEXPENSIVE"],
        "$$": ["PRICE_LEVEL_MODERATE"],
        "$$$": ["PRICE_LEVEL_EXPENSIVE"],
        "$$$$": ["PRICE_LEVEL_VERY_EXPENSIVE"],
    }
    price_levels = price_map.get(max_price) if max_price else None

    results = _google_places_search(
        query, max_results=limit, min_rating=4.0,
        price_levels=price_levels, open_now=open_now,
    )

    return {
        "restaurants": results,
        "count": len(results),
        "city": city,
        "cuisine": cuisine,
        "source": "Google Places (live)" if GOOGLE_API_KEY else "API key not set",
    }


def find_hotels(
    city: str,
    checkin: str = None,
    checkout: str = None,
    guests: int = 2,
    limit: int = 5,
) -> dict:
    """Find hotels in a city. Uses Google Places API.

    Args:
        city: 'Gdańsk', 'Kraków', etc.
        checkin: YYYY-MM-DD
        checkout: YYYY-MM-DD
        guests: number of guests
        limit: max results
    """
    results = _google_places_search(
        f"hotel in {city}", max_results=limit, min_rating=4.0,
    )

    nights = 1
    if checkin and checkout:
        try:
            d1 = datetime.fromisoformat(checkin)
            d2 = datetime.fromisoformat(checkout)
            nights = max(1, (d2 - d1).days)
        except Exception:
            pass

    return {
        "hotels": results,
        "count": len(results),
        "city": city,
        "nights": nights,
        "source": "Google Places (live)" if GOOGLE_API_KEY else "API key not set",
    }


def find_attractions(
    city: str,
    attraction_type: str = None,
    limit: int = 10,
) -> dict:
    """Find tourist attractions, museums, landmarks.

    Args:
        city: 'Gdańsk', 'Rzym', etc.
        attraction_type: 'museum', 'landmark', 'park', 'church', etc.
        limit: max results
    """
    query = f"tourist attraction"
    if attraction_type:
        query = f"{attraction_type} {query}"
    query += f" in {city}"

    results = _google_places_search(query, max_results=limit, min_rating=4.0)
    return {
        "attractions": results,
        "count": len(results),
        "city": city,
        "source": "Google Places (live)" if GOOGLE_API_KEY else "API key not set",
    }


def find_bars(
    city: str,
    vibe: str = None,
    limit: int = 5,
) -> dict:
    """Find bars, pubs, cocktail bars.

    Args:
        city: 'Gdańsk', 'Sopot', etc.
        vibe: 'cocktail', 'wine', 'rooftop', 'speakeasy', etc.
        limit: max results
    """
    query = f"{vibe or ''} bar in {city}".strip()
    results = _google_places_search(query, max_results=limit, min_rating=4.0)
    return {
        "bars": results,
        "count": len(results),
        "city": city,
        "source": "Google Places (live)" if GOOGLE_API_KEY else "API key not set",
    }


def get_weather(city: str) -> dict:
    """Get current weather + 3-day forecast. Uses Open-Meteo (free, no key).

    Args:
        city: 'Gdańsk', 'Warszawa', 'Berlin', etc.
    """
    city_lower = city.lower()
    coord = CITY_COORDS.get(city_lower)

    if not coord:
        # Try partial match
        for key, val in CITY_COORDS.items():
            if city_lower in key or key in city_lower:
                coord = val
                break

    if coord:
        weather = _get_weather_live(*coord)
        if "error" not in weather:
            return {"weather": weather, "city": city, "source": "Open-Meteo (live)"}

    return {"weather": {"error": f"No coordinates for {city}"}, "city": city}


def convert_currency(amount: float, from_cur: str, to_cur: str) -> dict:
    """Convert currency. Uses ExchangeRate-API (free, no key).

    Args:
        amount: e.g. 100
        from_cur: 'PLN', 'EUR', 'USD', etc.
        to_cur: 'PLN', 'EUR', 'USD', etc.
    """
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()

    data = _get_currency_live(from_cur)
    if "error" in data:
        return {"error": data["error"]}

    rate = data.get("rates", {}).get(to_cur, 0)
    return {
        "amount": amount,
        "from": from_cur,
        "to": to_cur,
        "rate": rate,
        "result": round(amount * rate, 2),
        "source": "ExchangeRate-API (live)",
    }


def plan_date_night(city: str) -> dict:
    """Zaplanuj randkę — restauracja, bar, wydarzenie, pogoda.

    Args:
        city: 'Gdańsk', 'Sopot', 'Warszawa', etc.
    """
    # Try Google Places first, fall back to european_data mock
    restaurants = find_restaurants(city, romantic=True, limit=5)
    if not restaurants.get("restaurants") or "error" in restaurants["restaurants"][0]:
        # Fallback: use european_data
        try:
            from european_data import EUROPEAN_RESTAURANTS
            city_lower = city.lower()
            mock = []
            for key in EUROPEAN_RESTAURANTS:
                if city_lower in key or key in city_lower:
                    mock = [r for r in EUROPEAN_RESTAURANTS[key] if r.get("romantic")]
                    break
            restaurants = {"restaurants": mock, "count": len(mock), "city": city, "source": "mock"}
        except ImportError:
            pass

    bars = find_restaurants(city, cuisine="wine bar", limit=3)
    if not bars.get("restaurants") or "error" in bars["restaurants"][0]:
        try:
            from european_data import EUROPEAN_RESTAURANTS
            city_lower = city.lower()
            mock = []
            for key in EUROPEAN_RESTAURANTS:
                if city_lower in key or key in city_lower:
                    mock = [r for r in EUROPEAN_RESTAURANTS[key] if "wine" in r.get("cuisine", "").lower()]
                    break
            bars = {"restaurants": mock, "count": len(mock), "city": city, "source": "mock"}
        except ImportError:
            pass

    weather = get_weather(city)

    dinner = None
    if restaurants.get("restaurants"):
        for r in restaurants["restaurants"]:
            if "name" in r:
                dinner = r
                break
    bar = None
    if bars.get("restaurants"):
        for r in bars["restaurants"]:
            if "name" in r:
                bar = r
                break
    w = weather.get("weather", {})

    plan_lines = []
    if w.get("temp"):
        plan_lines.append(f"🌤️  Pogoda: {w['temp']}°C, {w.get('description', '?')}")
    if dinner:
        plan_lines.append(f"🍽️  Kolacja: {dinner['name']} (⭐{dinner.get('rating', '?')}) — {dinner.get('address', '?')}")
    if bar:
        plan_lines.append(f"🍸  Drink: {bar['name']} (⭐{bar.get('rating', '?')}) — {bar.get('address', '?')}")

    return {
        "city": city,
        "weather": w,
        "dinner": dinner,
        "drinks": bar,
        "all_restaurants": restaurants.get("restaurants", []),
        "all_bars": bars.get("restaurants", []),
        "plan": "\n".join(plan_lines) if plan_lines else "Za mało danych — ustaw GOOGLE_PLACES_API_KEY",
    }


def full_travel_plan(city: str, checkin: str, checkout: str, guests: int = 2) -> dict:
    """Create a complete travel plan: hotel + restaurants + attractions + weather.

    Args:
        city: 'Kraków', 'Praga', etc.
        checkin: YYYY-MM-DD
        checkout: YYYY-MM-DD
        guests: number of guests
    """
    hotels = find_hotels(city, checkin, checkout, guests)
    restaurants = find_restaurants(city, limit=5)
    attractions = find_attractions(city, limit=5)
    weather = get_weather(city)

    hotel = hotels["hotels"][0] if hotels["hotels"] else None

    return {
        "city": city,
        "dates": f"{checkin} → {checkout}",
        "guests": guests,
        "weather": weather.get("weather", {}),
        "hotel": hotel,
        "top_restaurants": restaurants["restaurants"][:3],
        "top_attractions": attractions["attractions"][:3],
    }


# ═══════════════════════════════════════════════════════════════
# MAIN — for testing
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Hermes Travel Plugin — test")
        print("  python3 travel_plugin.py restaurants Gdańsk włoska")
        print("  python3 travel_plugin.py hotels Warszawa 2026-08-01 2026-08-03")
        print("  python3 travel_plugin.py attractions Kraków")
        print("  python3 travel_plugin.py bars Sopot cocktail")
        print("  python3 travel_plugin.py weather Gdańsk")
        print("  python3 travel_plugin.py currency 100 PLN EUR")
        print("  python3 travel_plugin.py date-night Sopot")
        print("  python3 travel_plugin.py full-plan Kraków 2026-08-01 2026-08-03")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "restaurants":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        cuisine = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(find_restaurants(city, cuisine), indent=2, ensure_ascii=False))

    elif cmd == "hotels":
        city = sys.argv[2] if len(sys.argv) > 2 else "Warszawa"
        checkin = sys.argv[3] if len(sys.argv) > 3 else None
        checkout = sys.argv[4] if len(sys.argv) > 4 else None
        print(json.dumps(find_hotels(city, checkin, checkout), indent=2, ensure_ascii=False))

    elif cmd == "attractions":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        atype = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(find_attractions(city, atype), indent=2, ensure_ascii=False))

    elif cmd == "bars":
        city = sys.argv[2] if len(sys.argv) > 2 else "Sopot"
        vibe = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(find_bars(city, vibe), indent=2, ensure_ascii=False))

    elif cmd == "weather":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        print(json.dumps(get_weather(city), indent=2, ensure_ascii=False))

    elif cmd == "currency":
        amount = float(sys.argv[2]) if len(sys.argv) > 2 else 100
        from_cur = sys.argv[3] if len(sys.argv) > 3 else "PLN"
        to_cur = sys.argv[4] if len(sys.argv) > 4 else "EUR"
        print(json.dumps(convert_currency(amount, from_cur, to_cur), indent=2, ensure_ascii=False))

    elif cmd == "date-night":
        city = sys.argv[2] if len(sys.argv) > 2 else "Sopot"
        print(json.dumps(plan_date_night(city), indent=2, ensure_ascii=False))

    elif cmd == "full-plan":
        city = sys.argv[2] if len(sys.argv) > 2 else "Kraków"
        checkin = sys.argv[3] if len(sys.argv) > 3 else "2026-08-01"
        checkout = sys.argv[4] if len(sys.argv) > 4 else "2026-08-03"
        print(json.dumps(full_travel_plan(city, checkin, checkout), indent=2, ensure_ascii=False))
