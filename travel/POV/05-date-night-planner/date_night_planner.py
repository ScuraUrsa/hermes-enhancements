"""
Date Night Planner — one command to plan a perfect evening.

Combines Google Places (restaurants + bars), Eventbrite (events),
and OpenWeatherMap (weather) into a single JSON plan.

Usage:
    python date_night_planner.py "Gdańsk Śródmieście" --date 2026-08-01 --budget moderate

Requires:
    GOOGLE_PLACES_API_KEY
    EVENTBRITE_API_KEY (optional)
    OPENWEATHERMAP_API_KEY (optional)
"""

import json
import sys
import os
import argparse
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlencode


# ── Google Places (New API) ────────────────────────────────────────────

def search_places(
    api_key: str,
    query: str,
    max_results: int = 5,
    min_rating: float = 4.0,
    price_levels: list[str] | None = None,
) -> list[dict]:
    """Search Google Places (New) Text Search."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,places.formattedAddress,places.rating,"
            "places.userRatingCount,places.priceLevel,places.websiteUri,"
            "places.googleMapsUri,places.regularOpeningHours,places.editorialSummary"
        ),
    }
    body: dict = {
        "textQuery": query,
        "maxResultCount": max_results,
    }
    if min_rating:
        body["minRating"] = min_rating
    if price_levels:
        body["priceLevels"] = price_levels

    req = Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return [{"error": str(e)}]

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
        })
    return results


# ── Eventbrite ─────────────────────────────────────────────────────────

def search_events(
    api_key: str,
    location: str,
    start_date: str,
    end_date: str,
    max_results: int = 5,
) -> list[dict]:
    """Search Eventbrite events."""
    params = {
        "location.address": location,
        "start_date.range_start": f"{start_date}T00:00:00Z",
        "start_date.range_end": f"{end_date}T23:59:59Z",
        "expand": "venue",
        "page_size": max_results,
    }
    url = f"https://www.eventbriteapi.com/v3/events/search/?{urlencode(params)}"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        with urlopen(Request(url, headers=headers), timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return [{"error": str(e)}]

    results = []
    for e in data.get("events", []):
        venue = e.get("venue") or {}
        results.append({
            "name": (e.get("name", {}) or {}).get("text", "?"),
            "url": e.get("url", ""),
            "start": e.get("start", {}).get("local", "?"),
            "free": e.get("is_free", False),
            "venue": venue.get("name", "?"),
            "venue_address": (venue.get("address", {}) or {}).get("localized_address_display", "?"),
        })
    return results


# ── OpenWeatherMap ─────────────────────────────────────────────────────

def get_weather(api_key: str, city: str) -> dict:
    """Get current weather + 1-day forecast."""
    params = {"q": city, "appid": api_key, "units": "metric", "cnt": 8}
    url = f"https://api.openweathermap.org/data/2.5/forecast?{urlencode(params)}"

    try:
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

    today = []
    for item in data.get("list", []):
        dt = item.get("dt_txt", "")
        if dt.startswith(datetime.now().strftime("%Y-%m-%d")):
            today.append({
                "time": dt,
                "temp": item.get("main", {}).get("temp"),
                "feels_like": item.get("main", {}).get("feels_like"),
                "description": item.get("weather", [{}])[0].get("description", "?"),
                "rain": item.get("rain", {}).get("3h", 0),
            })

    return {
        "city": data.get("city", {}).get("name", city),
        "forecast": today[:4],  # Next 12 hours
    }


# ── Planner ────────────────────────────────────────────────────────────

def plan_date_night(
    location: str,
    date: str,
    budget: str = "moderate",
    google_key: str = "",
    eventbrite_key: str = "",
    weather_key: str = "",
) -> dict:
    """Generate a complete date night plan.

    Args:
        location: 'Gdańsk Śródmieście' or 'Sopot, Poland'
        date: YYYY-MM-DD
        budget: 'budget', 'moderate', or 'luxury'
    """
    plan: dict = {
        "location": location,
        "date": date,
        "budget": budget,
        "generated_at": datetime.now().isoformat(),
    }

    # Price level mapping
    price_map = {
        "budget": ["PRICE_LEVEL_FREE", "PRICE_LEVEL_INEXPENSIVE"],
        "moderate": ["PRICE_LEVEL_MODERATE"],
        "luxury": ["PRICE_LEVEL_EXPENSIVE", "PRICE_LEVEL_VERY_EXPENSIVE"],
    }
    prices = price_map.get(budget, price_map["moderate"])

    # 1. Restaurants
    if google_key:
        plan["restaurants"] = search_places(
            google_key,
            f"romantic restaurant dinner in {location}",
            max_results=5,
            min_rating=4.3,
            price_levels=prices,
        )
    else:
        plan["restaurants"] = [{"note": "GOOGLE_PLACES_API_KEY not set"}]

    # 2. Bars / drinks
    if google_key:
        plan["bars"] = search_places(
            google_key,
            f"cocktail bar wine bar in {location}",
            max_results=3,
            min_rating=4.0,
        )
    else:
        plan["bars"] = [{"note": "GOOGLE_PLACES_API_KEY not set"}]

    # 3. Events
    if eventbrite_key:
        end_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        plan["events"] = search_events(eventbrite_key, location, date, end_date, max_results=5)
    else:
        plan["events"] = [{"note": "EVENTBRITE_API_KEY not set"}]

    # 4. Weather
    if weather_key:
        plan["weather"] = get_weather(weather_key, location)
    else:
        plan["weather"] = {"note": "OPENWEATHERMAP_API_KEY not set"}

    # 5. Summary
    plan["summary"] = _generate_summary(plan)

    return plan


def _generate_summary(plan: dict) -> str:
    """Generate a human-readable summary."""
    parts = [f"🌙 Date Night Plan for {plan['location']} on {plan['date']}\n"]

    # Weather
    w = plan.get("weather", {})
    if "forecast" in w and w["forecast"]:
        evening = [f for f in w["forecast"] if "18:00" <= f["time"][11:16] <= "23:00"]
        if evening:
            e = evening[0]
            parts.append(f"🌤️ Weather: {e['temp']}°C, {e['description']}")
        else:
            e = w["forecast"][0]
            parts.append(f"🌤️ Weather: {e['temp']}°C, {e['description']}")

    # Top restaurant
    restaurants = plan.get("restaurants", [])
    if restaurants and "name" in restaurants[0]:
        r = restaurants[0]
        parts.append(f"\n🍽️  Dinner: **{r['name']}** — ⭐{r.get('rating','?')} ({r.get('reviews',0)} reviews)")
        if r.get("summary"):
            parts.append(f"   {r['summary'][:200]}")

    # Top bar
    bars = plan.get("bars", [])
    if bars and "name" in bars[0]:
        b = bars[0]
        parts.append(f"\n🍸 Drinks: **{b['name']}** — ⭐{b.get('rating','?')}")

    # Top event
    events = plan.get("events", [])
    if events and "name" in events[0]:
        e = events[0]
        parts.append(f"\n🎭 Event: **{e['name']}** — {e.get('start','?')}")

    return "\n".join(parts)


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Date Night Planner")
    parser.add_argument("location", help="City or neighborhood (e.g. 'Gdańsk Śródmieście')")
    parser.add_argument("--date", "-d", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--budget", "-b", choices=["budget", "moderate", "luxury"], default="moderate")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    google_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    eventbrite_key = os.getenv("EVENTBRITE_API_KEY", "")
    weather_key = os.getenv("OPENWEATHERMAP_API_KEY", "")

    plan = plan_date_night(
        location=args.location,
        date=args.date,
        budget=args.budget,
        google_key=google_key,
        eventbrite_key=eventbrite_key,
        weather_key=weather_key,
    )

    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print(plan["summary"])
        print(f"\n---\n💡 Set API keys for live data: GOOGLE_PLACES_API_KEY, EVENTBRITE_API_KEY, OPENWEATHERMAP_API_KEY")


if __name__ == "__main__":
    main()
