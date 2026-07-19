#!/usr/bin/env python3
"""
POV: Restaurant & Event Finder for Hermes
=========================================
Wyszukiwanie restauracji i wydarzeń w Trójmieście przez Google Places API,
Eventbrite API i Ticketmaster API.

Wymagania:
- GOOGLE_PLACES_API_KEY (GCP)
- EVENTBRITE_API_KEY (opcjonalnie)
- TICKETMASTER_API_KEY (opcjonalnie)

Użycie:
    python3 demo.py restaurants "Gdańsk Wrzeszcz" italian
    python3 demo.py events "Gdańsk" 2026-07-25
    python3 demo.py date-night "Gdańsk Śródmieście"
"""

import sys
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


# === KONFIGURACJA ===

GDAŃSK_COORDS = {"lat": 54.3520, "lng": 18.6466}
GDYNIA_COORDS = {"lat": 54.5189, "lng": 18.5305}
SOPOT_COORDS = {"lat": 54.4416, "lng": 18.5601}

TRÓJMIASTO = {
    "gdańsk": GDAŃSK_COORDS,
    "gdynia": GDYNIA_COORDS,
    "sopot": SOPOT_COORDS,
    "wrzeszcz": {"lat": 54.3800, "lng": 18.6000},
    "śródmieście": GDAŃSK_COORDS,
    "oliwa": {"lat": 54.4100, "lng": 18.5600},
    "przymorze": {"lat": 54.4000, "lng": 18.5800},
}

CUISINE_KEYWORDS = {
    "italian": "Italian restaurant",
    "włoska": "Italian restaurant",
    "polish": "Polish restaurant",
    "polska": "Polish restaurant",
    "japanese": "Japanese restaurant",
    "japońska": "Japanese restaurant",
    "sushi": "Sushi restaurant",
    "seafood": "Seafood restaurant",
    "rybna": "Seafood restaurant",
    "steak": "Steak house",
    "stek": "Steak house",
    "vegan": "Vegan restaurant",
    "wegańska": "Vegan restaurant",
    "french": "French restaurant",
    "francuska": "French restaurant",
    "asian": "Asian restaurant",
    "azjatycka": "Asian restaurant",
    "mexican": "Mexican restaurant",
    "meksykańska": "Mexican restaurant",
}

DATE_NIGHT_KEYWORDS = [
    "romantic restaurant",
    "fine dining",
    "rooftop bar",
    "wine bar",
    "cocktail bar",
    "restauracja z widokiem",
    "restauracja romantyczna",
]


# === GOOGLE PLACES API ===

class GooglePlacesClient:
    """Klient Google Places API (New)."""

    BASE_URL = "https://places.googleapis.com/v1/places"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _request(self, endpoint: str, params: dict) -> dict:
        url = f"{self.BASE_URL}:{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.priceLevel,places.types,places.websiteUri,places.nationalPhoneNumber,places.regularOpeningHours,places.photos,places.location",
        }
        data = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": str(e)}

    def nearby_search(self, lat: float, lng: float, radius: int = 2000,
                      keyword: str = "restaurant", max_results: int = 10) -> list:
        """Wyszukaj miejsca w pobliżu."""
        params = {
            "includedTypes": ["restaurant"],
            "maxResultCount": max_results,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
            "languageCode": "pl",
        }
        if keyword:
            params["textQuery"] = keyword

        result = self._request("searchNearby", params)
        if "error" in result:
            return [result]
        return result.get("places", [])

    def text_search(self, query: str, lat: float = None, lng: float = None,
                    max_results: int = 10) -> list:
        """Wyszukaj miejsca po tekście."""
        params = {
            "textQuery": query,
            "maxResultCount": max_results,
            "languageCode": "pl",
        }
        if lat and lng:
            params["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 5000.0,
                }
            }

        result = self._request("searchText", params)
        if "error" in result:
            return [result]
        return result.get("places", [])


# === EVENTBRITE API ===

class EventbriteClient:
    """Klient Eventbrite API."""

    BASE_URL = "https://www.eventbriteapi.com/v3"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_events(self, location: str = "Gdańsk", start_date: str = None,
                      categories: str = None, max_results: int = 10) -> list:
        """Wyszukaj wydarzenia."""
        params = {
            "location.address": location,
            "location.within": "20km",
            "expand": "venue",
            "page_size": max_results,
        }
        if start_date:
            params["start_date.range_start"] = f"{start_date}T00:00:00Z"
        if categories:
            params["categories"] = categories

        url = f"{self.BASE_URL}/events/search/?{urllib.parse.urlencode(params)}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                return data.get("events", [])
        except Exception as e:
            return [{"error": str(e)}]


# === TICKETMASTER API ===

class TicketmasterClient:
    """Klient Ticketmaster Discovery API."""

    BASE_URL = "https://app.ticketmaster.com/discovery/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_events(self, city: str = "Gdańsk", start_date: str = None,
                      size: int = 10, classification: str = None) -> list:
        """Wyszukaj wydarzenia."""
        params = {
            "apikey": self.api_key,
            "city": city,
            "countryCode": "PL",
            "size": size,
            "sort": "date,asc",
        }
        if start_date:
            end = (datetime.fromisoformat(start_date) + timedelta(days=30)).strftime("%Y-%m-%d")
            params["startDateTime"] = f"{start_date}T00:00:00Z"
            params["endDateTime"] = f"{end}T23:59:59Z"
        if classification:
            params["classificationName"] = classification

        url = f"{self.BASE_URL}/events.json?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
                events = data.get("_embedded", {}).get("events", [])
                return events
        except Exception as e:
            return [{"error": str(e)}]


# === MOCK DATA (gdy brak API key) ===

MOCK_RESTAURANTS_GDANSK = [
    {"name": "Restauracja Gdańska", "rating": 4.7, "price": "$$$", "type": "polska",
     "address": "ul. Długa 12, Gdańsk", "phone": "+48 58 123 45 67",
     "hours": "12:00-22:00", "website": "https://example.com/gdanska",
     "notes": "Elegancka restauracja z kuchnią polską. Idealna na randkę."},
    {"name": "Mandu Pierogarnia", "rating": 4.6, "price": "$$", "type": "polska",
     "address": "ul. Kaprów 19D, Gdańsk", "phone": "+48 58 301 23 45",
     "hours": "11:00-21:00", "website": "https://mandu.pl",
     "notes": "Najlepsze pierogi w Trójmieście. Casual atmosfera."},
    {"name": "La Pampa Steakhouse", "rating": 4.5, "price": "$$$", "type": "stek",
     "address": "ul. Szafarnia 10, Gdańsk", "phone": "+48 58 320 12 34",
     "hours": "13:00-23:00", "website": "https://lapampa.pl",
     "notes": "Steki premium. Dobre na biznesowy obiad."},
    {"name": "Trattoria Mamma Mia", "rating": 4.6, "price": "$$", "type": "włoska",
     "address": "ul. Świętego Ducha 12, Gdańsk", "phone": "+48 58 301 98 76",
     "hours": "12:00-22:00", "website": "https://mammamia.pl",
     "notes": "Autentyczna włoska kuchnia. Świetna pizza i pasta. Romantyczny nastrój."},
    {"name": "Sensi Sushi", "rating": 4.4, "price": "$$$", "type": "japońska",
     "address": "ul. Piwna 28, Gdańsk", "phone": "+48 58 345 67 89",
     "hours": "12:00-22:00", "website": "https://sensi.pl",
     "notes": "Świeże sushi w centrum Gdańska."},
    {"name": "Brovarnia Gdańsk", "rating": 4.3, "price": "$$", "type": "polska",
     "address": "ul. Szafarnia 9, Gdańsk", "phone": "+48 58 320 19 00",
     "hours": "12:00-23:00", "website": "https://brovarnia.pl",
     "notes": "Browar restauracyjny z widokiem na Motławę."},
    {"name": "Pueblo", "rating": 4.5, "price": "$$", "type": "meksykańska",
     "address": "ul. Kołodziejska 4, Gdańsk", "phone": "+48 58 301 11 22",
     "hours": "12:00-22:00", "website": "https://pueblo.pl",
     "notes": "Kolorowe meksykańskie jedzenie. Świetne na spotkanie ze znajomymi."},
    {"name": "Ritz Restaurant", "rating": 4.8, "price": "$$$$", "type": "fine dining",
     "address": "ul. Długi Targ 19, Gdańsk", "phone": "+48 58 300 12 34",
     "hours": "17:00-23:00", "website": "https://ritz.pl",
     "notes": "Fine dining w sercu Gdańska. Idealna na wyjątkową randkę."},
    {"name": "Avocado Vegan Bistro", "rating": 4.6, "price": "$$", "type": "wegańska",
     "address": "ul. Garncarska 18, Gdańsk", "phone": "+48 58 320 45 67",
     "hours": "10:00-20:00", "website": "https://avocado.pl",
     "notes": "Najlepsze wegańskie jedzenie w mieście."},
    {"name": "Winestone", "rating": 4.4, "price": "$$$", "type": "wine bar",
     "address": "ul. Długa 45, Gdańsk", "phone": "+48 58 320 89 01",
     "hours": "16:00-00:00", "website": "https://winestone.pl",
     "notes": "Wine bar z bogatą kartą win i przekąskami."},
    {"name": "Restauracja Filharmonia", "rating": 4.7, "price": "$$$$", "type": "fine dining",
     "address": "ul. Ołowianka 1, Gdańsk", "phone": "+48 58 320 23 45",
     "hours": "17:00-23:00", "website": "https://filharmonia.pl",
     "notes": "Elegancka restauracja z widokiem na Motławę. Muzyka na żywo."},
]

MOCK_EVENTS_GDANSK = [
    {"name": "Koncert: Męskie Granie 2026", "date": "2026-07-25", "venue": "Stadion Energa",
     "category": "music", "price": "150-300 PLN", "url": "https://ticketmaster.pl"},
    {"name": "Festiwal Szekspirowski", "date": "2026-07-28", "venue": "Teatr Szekspirowski",
     "category": "theatre", "price": "50-120 PLN", "url": "https://teatr.pl"},
    {"name": "Jarmark Dominikański", "date": "2026-07-26", "venue": "Główne Miasto",
     "category": "festival", "price": "Free", "url": "https://jarmark.pl"},
    {"name": "Kino Letnie na Plaży", "date": "2026-07-27", "venue": "Plaża Stogi",
     "category": "film", "price": "20 PLN", "url": "https://kinonaletnie.pl"},
    {"name": "Wystawa: Impresjoniści", "date": "2026-07-20", "venue": "Muzeum Narodowe",
     "category": "arts", "price": "25 PLN", "url": "https://muzeum.pl"},
    {"name": "Rejs po Motławie", "date": "2026-07-26", "venue": "Przystań Żabi Kruk",
     "category": "recreation", "price": "60 PLN", "url": "https://rejsy.pl"},
    {"name": "Degustacja win", "date": "2026-07-29", "venue": "Winestone Gdańsk",
     "category": "food", "price": "120 PLN", "url": "https://winestone.pl"},
    {"name": "Stand-up: Cezary Pazura", "date": "2026-07-30", "venue": "Klub Parlament",
     "category": "comedy", "price": "80 PLN", "url": "https://ebilet.pl"},
]


# === GŁÓWNE FUNKCJE ===

def find_restaurants(location: str, cuisine: str = None, api_key: str = None) -> list:
    """Znajdź restauracje w danej lokalizacji."""
    coords = TRÓJMIASTO.get(location.lower(), GDAŃSK_COORDS)

    if api_key:
        client = GooglePlacesClient(api_key)
        keyword = CUISINE_KEYWORDS.get(cuisine.lower(), "restaurant") if cuisine else "restaurant"
        return client.nearby_search(coords["lat"], coords["lng"], keyword=keyword)
    else:
        # Mock data
        results = MOCK_RESTAURANTS_GDANSK
        if cuisine:
            cuisine_lower = cuisine.lower()
            results = [r for r in results if cuisine_lower in r.get("type", "").lower()
                       or cuisine_lower in r.get("name", "").lower()]
        return results


def find_events(location: str, date: str = None, api_keys: dict = None) -> list:
    """Znajdź wydarzenia."""
    if api_keys and api_keys.get("ticketmaster"):
        client = TicketmasterClient(api_keys["ticketmaster"])
        return client.search_events(city=location, start_date=date)
    elif api_keys and api_keys.get("eventbrite"):
        client = EventbriteClient(api_keys["eventbrite"])
        return client.search_events(location=location, start_date=date)
    else:
        # Mock data
        results = MOCK_EVENTS_GDANSK
        if date:
            results = [e for e in results if e["date"] >= date]
        return results


def find_date_night(location: str, api_key: str = None) -> dict:
    """Znajdź restaurację + wydarzenie na randkę."""
    coords = TRÓJMIASTO.get(location.lower(), GDAŃSK_COORDS)

    if api_key:
        client = GooglePlacesClient(api_key)
        restaurants = client.text_search("romantic restaurant fine dining", coords["lat"], coords["lng"], 5)
        bars = client.text_search("cocktail bar wine bar rooftop", coords["lat"], coords["lng"], 3)
    else:
        restaurants = [r for r in MOCK_RESTAURANTS_GDANSK
                       if any(kw in r.get("type", "").lower() or kw in r.get("notes", "").lower()
                              for kw in ["fine dining", "wine bar", "romantyczna", "elegancka"])][:5]
        bars = [r for r in MOCK_RESTAURANTS_GDANSK
                if "wine bar" in r.get("type", "").lower() or "cocktail" in r.get("notes", "").lower()][:3]

    events = [e for e in MOCK_EVENTS_GDANSK
              if e["category"] in ["music", "theatre", "comedy", "food"]][:3]

    return {
        "restauracje": restaurants,
        "bary": bars,
        "wydarzenia": events,
        "plan": (
            f"🍽️  Kolacja: {restaurants[0]['name'] if restaurants else '?'} "
            f"(ocena: {restaurants[0].get('rating', '?') if restaurants else '?'})\n"
            f"🎭  Wydarzenie: {events[0]['name'] if events else '?'} "
            f"({events[0]['date'] if events else '?'})\n"
            f"🍸  Drink: {bars[0]['name'] if bars else '?'}"
        ),
    }


def format_restaurant(r: dict) -> str:
    """Formatuj restaurację do wyświetlenia."""
    name = r.get("name", r.get("displayName", {}).get("text", "?"))
    rating = r.get("rating", "?")
    price = r.get("price", r.get("priceLevel", "?"))
    if isinstance(price, str) and price.startswith("PRICE_"):
        price = price.replace("PRICE_LEVEL_", "").replace("_", " ")
    addr = r.get("address", r.get("formattedAddress", "?"))
    phone = r.get("phone", r.get("nationalPhoneNumber", ""))
    notes = r.get("notes", "")
    return f"  🍽️  {name} | ⭐{rating} | 💰{price}\n     📍 {addr} | 📞 {phone}\n     💬 {notes}"


def format_event(e: dict) -> str:
    """Formatuj wydarzenie do wyświetlenia."""
    name = e.get("name", "?")
    date = e.get("date", e.get("dates", {}).get("start", {}).get("localDate", "?"))
    venue = e.get("venue", e.get("_embedded", {}).get("venues", [{}])[0].get("name", "?"))
    if isinstance(venue, dict):
        venue = venue.get("name", "?")
    price = e.get("price", e.get("priceRanges", [{}])[0].get("min", "?"))
    url = e.get("url", "")
    return f"  🎭  {name} | 📅 {date} | 📍 {venue} | 💰 {price}\n     🔗 {url}"


# === MAIN ===

def main():
    if len(sys.argv) < 2:
        print("Użycie:")
        print("  python3 demo.py restaurants <miasto> [kuchnia]")
        print("  python3 demo.py events <miasto> [data]")
        print("  python3 demo.py date-night <miasto>")
        print()
        print("Przykłady:")
        print("  python3 demo.py restaurants Gdańsk włoska")
        print("  python3 demo.py events Gdańsk 2026-07-25")
        print("  python3 demo.py date-night 'Gdańsk Śródmieście'")
        return

    cmd = sys.argv[1]
    location = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
    extra = sys.argv[3] if len(sys.argv) > 3 else None

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    api_keys = {
        "eventbrite": os.environ.get("EVENTBRITE_API_KEY"),
        "ticketmaster": os.environ.get("TICKETMASTER_API_KEY"),
    }

    print("=" * 60)
    print("🍽️  RESTAURANT & EVENT FINDER FOR HERMES")
    print("=" * 60)

    if not api_key:
        print("⚠️  Brak GOOGLE_PLACES_API_KEY — używam danych mockowych")
        print("   Ustaw: export GOOGLE_PLACES_API_KEY='...'")
        print()

    if cmd == "restaurants":
        cuisine = extra
        print(f"🔍 Szukam restauracji w {location}" + (f" ({cuisine})" if cuisine else ""))
        print()
        results = find_restaurants(location, cuisine, api_key)
        for r in results[:10]:
            print(format_restaurant(r))
            print()

    elif cmd == "events":
        date = extra
        print(f"🔍 Szukam wydarzeń w {location}" + (f" od {date}" if date else ""))
        print()
        results = find_events(location, date, api_keys)
        for e in results[:10]:
            print(format_event(e))
            print()

    elif cmd == "date-night":
        print(f"💕 Planuję randkę w {location}")
        print()
        plan = find_date_night(location, api_key)
        print("📋 PROPOZYCJA PLANU:")
        print(plan["plan"])
        print()
        print("🍽️  Restauracje:")
        for r in plan["restauracje"][:3]:
            print(format_restaurant(r))
            print()
        print("🎭  Wydarzenia:")
        for e in plan["wydarzenia"][:3]:
            print(format_event(e))
            print()

    else:
        print(f"Nieznana komenda: {cmd}")

    print("=" * 60)
    print("💡 Integracja z Hermesem:")
    print("   1. Dodaj GOOGLE_PLACES_API_KEY do ~/.hermes/.env")
    print("   2. Zarejestruj jako custom tool w pluginie")
    print("   3. Hermes może szukać restauracji i wydarzeń")
    print("=" * 60)


if __name__ == "__main__":
    main()
