#!/usr/bin/env python3
"""
Hermes Travel Plugin — kompletny plugin do wyszukiwania restauracji, hoteli,
wydarzeń, pogody i walut.

Instalacja:
    cp travel_plugin.py ~/.hermes/plugins/travel/plugin.py
    # Dodaj API keys do ~/.hermes/.env:
    # GOOGLE_PLACES_API_KEY=...
    # TICKETMASTER_API_KEY=...

Użycie przez Hermesa:
    "Znajdź włoską restaurację w Gdańsku"
    "Jakie wydarzenia są w Warszawie 25 lipca?"
    "Zaplanuj randkę w Sopocie"
    "Znajdź hotel w Krakowie na weekend"
    "Jaka pogoda jest w Gdańsku?"
    "Przelicz 200 PLN na EUR"
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

# Import atrakcji
try:
    from attractions_data import POLAND_ATTRACTIONS, EUROPE_ATTRACTIONS
except ImportError:
    POLAND_ATTRACTIONS = {}
    EUROPE_ATTRACTIONS = {}


# ═══════════════════════════════════════════════════════════════
# MOCK DATA — rozbudowana baza
# ═══════════════════════════════════════════════════════════════

MOCK_RESTAURANTS = {
    "gdańsk": [
        {"name": "Restauracja Gdańska", "rating": 4.7, "price": "$$$", "cuisine": "polska", "romantic": True,
         "address": "ul. Długa 12, Gdańsk", "phone": "+48 58 123 45 67", "hours": "12:00-22:00"},
        {"name": "Mandu Pierogarnia", "rating": 4.6, "price": "$$", "cuisine": "polska", "romantic": False,
         "address": "ul. Kaprów 19D, Gdańsk", "phone": "+48 58 301 23 45", "hours": "11:00-21:00"},
        {"name": "Trattoria Mamma Mia", "rating": 4.6, "price": "$$", "cuisine": "włoska", "romantic": True,
         "address": "ul. Świętego Ducha 12, Gdańsk", "phone": "+48 58 301 98 76", "hours": "12:00-22:00"},
        {"name": "La Pampa Steakhouse", "rating": 4.5, "price": "$$$", "cuisine": "steki", "romantic": False,
         "address": "ul. Szafarnia 10, Gdańsk", "phone": "+48 58 320 12 34", "hours": "13:00-23:00"},
        {"name": "Sensi Sushi", "rating": 4.4, "price": "$$$", "cuisine": "japońska", "romantic": False,
         "address": "ul. Piwna 28, Gdańsk", "phone": "+48 58 345 67 89", "hours": "12:00-22:00"},
        {"name": "Brovarnia Gdańsk", "rating": 4.3, "price": "$$", "cuisine": "polska", "romantic": False,
         "address": "ul. Szafarnia 9, Gdańsk", "phone": "+48 58 320 19 00", "hours": "12:00-23:00"},
        {"name": "Pueblo", "rating": 4.5, "price": "$$", "cuisine": "meksykańska", "romantic": False,
         "address": "ul. Kołodziejska 4, Gdańsk", "phone": "+48 58 301 11 22", "hours": "12:00-22:00"},
        {"name": "Ritz Restaurant", "rating": 4.8, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Długi Targ 19, Gdańsk", "phone": "+48 58 300 12 34", "hours": "17:00-23:00"},
        {"name": "Avocado Vegan Bistro", "rating": 4.6, "price": "$$", "cuisine": "wegańska", "romantic": False,
         "address": "ul. Garncarska 18, Gdańsk", "phone": "+48 58 320 45 67", "hours": "10:00-20:00"},
        {"name": "Winestone", "rating": 4.4, "price": "$$$", "cuisine": "wine bar", "romantic": True,
         "address": "ul. Długa 45, Gdańsk", "phone": "+48 58 320 89 01", "hours": "16:00-00:00"},
        {"name": "Restauracja Filharmonia", "rating": 4.7, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Ołowianka 1, Gdańsk", "phone": "+48 58 320 23 45", "hours": "17:00-23:00"},
    ],
    "sopot": [
        {"name": "Fisherman by Rafał Koziorzemski", "rating": 4.7, "price": "$$$$", "cuisine": "rybna", "romantic": True,
         "address": "Plac Zdrojowy 2, Sopot", "phone": "+48 58 551 21 21", "hours": "12:00-22:00"},
        {"name": "Bulaj", "rating": 4.5, "price": "$$$", "cuisine": "rybna", "romantic": True,
         "address": "ul. Zamkowa Góra 1, Sopot", "phone": "+48 58 555 99 99", "hours": "12:00-22:00"},
        {"name": "Błękitny Pudel", "rating": 4.3, "price": "$$", "cuisine": "polska", "romantic": False,
         "address": "ul. Bohaterów Monte Cassino 44, Sopot", "phone": "+48 58 551 21 22", "hours": "10:00-23:00"},
    ],
    "warszawa": [
        {"name": "Nolita", "rating": 4.8, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Wilcza 46, Warszawa", "phone": "+48 22 292 01 24", "hours": "17:00-23:00"},
        {"name": "Atelier Amaro", "rating": 4.9, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Agrykola 1, Warszawa", "phone": "+48 22 628 77 47", "hours": "18:00-23:00"},
        {"name": "Soul Kitchen", "rating": 4.6, "price": "$$$", "cuisine": "polska", "romantic": True,
         "address": "ul. Nowogrodzka 18A, Warszawa", "phone": "+48 22 299 00 00", "hours": "12:00-22:00"},
        {"name": "Bez Gwiazdek", "rating": 4.5, "price": "$$$", "cuisine": "polska", "romantic": False,
         "address": "ul. Wiślana 8, Warszawa", "phone": "+48 22 299 00 01", "hours": "12:00-22:00"},
        {"name": "Uki Uki", "rating": 4.7, "price": "$$$", "cuisine": "japońska", "romantic": False,
         "address": "ul. Krucza 23/31, Warszawa", "phone": "+48 22 299 00 02", "hours": "12:00-22:00"},
    ],
    "kraków": [
        {"name": "Bottiglieria 1881", "rating": 4.9, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Bocheńska 5, Kraków", "phone": "+48 12 660 47 50", "hours": "18:00-23:00"},
        {"name": "Zazie Bistro", "rating": 4.6, "price": "$$$", "cuisine": "francuska", "romantic": True,
         "address": "ul. Józefa 34, Kraków", "phone": "+48 12 422 22 22", "hours": "12:00-22:00"},
        {"name": "Karakter", "rating": 4.5, "price": "$$", "cuisine": "międzynarodowa", "romantic": False,
         "address": "ul. Brzozowa 17, Kraków", "phone": "+48 12 422 22 23", "hours": "12:00-22:00"},
    ],
    "wrocław": [
        {"name": "La Maddalena", "rating": 4.7, "price": "$$$$", "cuisine": "włoska", "romantic": True,
         "address": "ul. Włodkowica 9, Wrocław", "phone": "+48 71 722 22 22", "hours": "17:00-23:00"},
        {"name": "Młoda Polska", "rating": 4.5, "price": "$$$", "cuisine": "polska", "romantic": False,
         "address": "ul. Białoskórnicza 5, Wrocław", "phone": "+48 71 722 22 23", "hours": "12:00-22:00"},
    ],
    "poznań": [
        {"name": "Muga", "rating": 4.8, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Garbary 45, Poznań", "phone": "+48 61 222 22 22", "hours": "17:00-23:00"},
        {"name": "Wiejskie Jadło", "rating": 4.3, "price": "$$", "cuisine": "polska", "romantic": False,
         "address": "ul. Stary Rynek 77, Poznań", "phone": "+48 61 222 22 23", "hours": "11:00-22:00"},
    ],
    "łódź": [
        {"name": "Quale Restaurant", "rating": 4.6, "price": "$$$", "cuisine": "włoska", "romantic": True,
         "address": "ul. Piotrkowska 89, Łódź", "phone": "+48 42 222 22 22", "hours": "12:00-22:00"},
        {"name": "Ato Sushi", "rating": 4.5, "price": "$$$", "cuisine": "japońska", "romantic": False,
         "address": "ul. Piotrkowska 120, Łódź", "phone": "+48 42 222 22 23", "hours": "12:00-22:00"},
    ],
    "katowice": [
        {"name": "Tatiana", "rating": 4.7, "price": "$$$$", "cuisine": "fine dining", "romantic": True,
         "address": "ul. Staromiejska 12, Katowice", "phone": "+48 32 222 22 22", "hours": "17:00-23:00"},
        {"name": "Kyoto Sushi", "rating": 4.7, "price": "$$$", "cuisine": "japońska", "romantic": False,
         "address": "ul. Mariacka 15, Katowice", "phone": "+48 32 222 22 23", "hours": "12:00-22:00"},
    ],
}

MOCK_HOTELS = {
    "warszawa": [
        {"name": "Hotel Bristol", "stars": 5, "rating": 4.8, "price_per_night": 850,
         "address": "Krakowskie Przedmieście 42/44, Warszawa", "amenities": "SPA, basen, restauracja"},
        {"name": "Raffles Europejski", "stars": 5, "rating": 4.9, "price_per_night": 1200,
         "address": "Krakowskie Przedmieście 13, Warszawa", "amenities": "SPA, 2 restauracje, bar"},
        {"name": "InterContinental Warszawa", "stars": 5, "rating": 4.7, "price_per_night": 700,
         "address": "Emilii Plater 49, Warszawa", "amenities": "Basen, SPA, widok na miasto"},
        {"name": "PURO Warszawa Centrum", "stars": 4, "rating": 4.5, "price_per_night": 400,
         "address": "ul. Widok 9, Warszawa", "amenities": "Design hotel, śniadanie, bar"},
    ],
    "kraków": [
        {"name": "Hotel Stary", "stars": 5, "rating": 4.9, "price_per_night": 900,
         "address": "Szczepańska 5, Kraków", "amenities": "SPA, basen na dachu, restauracja"},
        {"name": "Hotel Copernicus", "stars": 5, "rating": 4.8, "price_per_night": 800,
         "address": "Kanonicza 16, Kraków", "amenities": "Historyczny budynek, SPA"},
        {"name": "PURO Kraków Stare Miasto", "stars": 4, "rating": 4.5, "price_per_night": 380,
         "address": "ul. Ogrodowa 10, Kraków", "amenities": "Design, śniadanie, bar"},
    ],
    "wrocław": [
        {"name": "The Granary La Suite", "stars": 5, "rating": 4.8, "price_per_night": 650,
         "address": "Mennicza 24, Wrocław", "amenities": "SPA, restauracja, design"},
        {"name": "DoubleTree by Hilton", "stars": 4, "rating": 4.5, "price_per_night": 450,
         "address": "Podwale 84, Wrocław", "amenities": "Basen, SPA, parking"},
    ],
    "gdańsk": [
        {"name": "Hilton Gdańsk", "stars": 5, "rating": 4.6, "price_per_night": 600,
         "address": "Targ Rybny 1, Gdańsk", "amenities": "Basen, SPA, widok na Motławę"},
        {"name": "PURO Gdańsk Stare Miasto", "stars": 4, "rating": 4.5, "price_per_night": 350,
         "address": "ul. Stągiewna 26, Gdańsk", "amenities": "Design, śniadanie, bar"},
    ],
    "sopot": [
        {"name": "Sofitel Grand Sopot", "stars": 5, "rating": 4.7, "price_per_night": 900,
         "address": "Powstańców Warszawy 12, Sopot", "amenities": "SPA, plaża, basen"},
        {"name": "Sheraton Sopot", "stars": 5, "rating": 4.6, "price_per_night": 800,
         "address": "Powstańców Warszawy 10, Sopot", "amenities": "SPA, plaża, restauracja"},
    ],
    "poznań": [
        {"name": "Hotel Vivaldi", "stars": 4, "rating": 4.4, "price_per_night": 350,
         "address": "ul. Winogrady 5, Poznań", "amenities": "Restauracja, parking"},
    ],
    "łódź": [
        {"name": "Andel's by Vienna House", "stars": 4, "rating": 4.5, "price_per_night": 400,
         "address": "ul. Ogrodowa 17, Łódź", "amenities": "Design, basen, SPA"},
    ],
    "katowice": [
        {"name": "Hotel Monopol", "stars": 5, "rating": 4.6, "price_per_night": 500,
         "address": "ul. Dworcowa 5, Katowice", "amenities": "SPA, restauracja, historia"},
    ],
}

MOCK_EVENTS = {
    "gdańsk": [
        {"name": "Koncert: Męskie Granie 2026", "date": "2026-07-25", "venue": "Stadion Energa", "category": "music", "price": "150-300 PLN"},
        {"name": "Festiwal Szekspirowski", "date": "2026-07-28", "venue": "Teatr Szekspirowski", "category": "theatre", "price": "50-120 PLN"},
        {"name": "Jarmark Dominikański", "date": "2026-07-26", "venue": "Główne Miasto", "category": "festival", "price": "Free"},
        {"name": "Kino Letnie na Plaży", "date": "2026-07-27", "venue": "Plaża Stogi", "category": "film", "price": "20 PLN"},
        {"name": "Rejs po Motławie", "date": "2026-07-26", "venue": "Przystań Żabi Kruk", "category": "recreation", "price": "60 PLN"},
        {"name": "Degustacja win", "date": "2026-07-29", "venue": "Winestone Gdańsk", "category": "food", "price": "120 PLN"},
        {"name": "Stand-up: Cezary Pazura", "date": "2026-07-30", "venue": "Klub Parlament", "category": "comedy", "price": "80 PLN"},
    ],
    "warszawa": [
        {"name": "Chopin Concerts", "date": "2026-07-25", "venue": "Filharmonia Narodowa", "category": "music", "price": "80-200 PLN"},
        {"name": "Wystawa: Van Gogh", "date": "2026-07-20", "venue": "Muzeum Narodowe", "category": "arts", "price": "40 PLN"},
        {"name": "Noc Muzeów", "date": "2026-07-26", "venue": "Warszawa", "category": "festival", "price": "Free"},
    ],
    "kraków": [
        {"name": "Festiwal Kultury Żydowskiej", "date": "2026-07-25", "venue": "Kazimierz", "category": "festival", "price": "Free-50 PLN"},
        {"name": "Opera: Carmen", "date": "2026-07-28", "venue": "Opera Krakowska", "category": "music", "price": "60-150 PLN"},
    ],
    "wrocław": [
        {"name": "Festiwal Filmowy Nowe Horyzonty", "date": "2026-07-25", "venue": "Kino Nowe Horyzonty", "category": "film", "price": "25 PLN"},
    ],
    "poznań": [
        {"name": "Malta Festival", "date": "2026-07-26", "venue": "Malta", "category": "festival", "price": "Free-100 PLN"},
    ],
}

MOCK_WEATHER = {
    "gdańsk": {"temp": 22, "humidity": 65, "wind": 15, "description": "Częściowo słonecznie", "icon": "⛅"},
    "sopot": {"temp": 21, "humidity": 70, "wind": 18, "description": "Lekki wiatr od morza", "icon": "🌤️"},
    "gdynia": {"temp": 20, "humidity": 72, "wind": 20, "description": "Wietrznie", "icon": "💨"},
    "warszawa": {"temp": 26, "humidity": 55, "wind": 10, "description": "Słonecznie", "icon": "☀️"},
    "kraków": {"temp": 27, "humidity": 50, "wind": 8, "description": "Słonecznie, gorąco", "icon": "☀️"},
    "wrocław": {"temp": 25, "humidity": 58, "wind": 12, "description": "Słonecznie", "icon": "☀️"},
    "poznań": {"temp": 24, "humidity": 60, "wind": 14, "description": "Częściowo słonecznie", "icon": "⛅"},
    "łódź": {"temp": 25, "humidity": 55, "wind": 11, "description": "Słonecznie", "icon": "☀️"},
    "katowice": {"temp": 26, "humidity": 52, "wind": 9, "description": "Słonecznie", "icon": "☀️"},
    "zakopane": {"temp": 18, "humidity": 75, "wind": 5, "description": "Lekkie zachmurzenie", "icon": "🌥️"},
}

MOCK_CURRENCIES = {
    "PLN": 1.0, "EUR": 4.25, "USD": 3.90, "GBP": 4.95,
    "CHF": 4.40, "CZK": 0.17, "HUF": 0.011, "NOK": 0.37,
    "SEK": 0.36, "DKK": 0.57, "RON": 0.85, "BGN": 2.17,
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
}

CITY_COORDS = {
    "gdańsk": (54.3520, 18.6466), "sopot": (54.4416, 18.5601),
    "gdynia": (54.5189, 18.5305), "warszawa": (52.2297, 21.0122),
    "kraków": (50.0647, 19.9450), "wrocław": (51.1079, 17.0385),
    "poznań": (52.4064, 16.9252), "łódź": (51.7592, 19.4560),
    "katowice": (50.2649, 19.0238), "zakopane": (49.2992, 19.9496),
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


def get_weather_live(lat: float, lng: float) -> dict:
    url = (f"https://api.open-meteo.com/v1/forecast?"
           f"latitude={lat}&longitude={lng}"
           f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
           f"&timezone=Europe/Warsaw")
    data = _get_json(url)
    if "error" in data:
        return data
    current = data.get("current", {})
    codes = {0: "Bezchmurnie ☀️", 1: "Prawie bezchmurnie 🌤️", 2: "Częściowo słonecznie ⛅",
             3: "Pochmurno ☁️", 45: "Mgła 🌫️", 61: "Deszcz 🌧️", 80: "Przelotne opady 🌦️", 95: "Burza ⛈️"}
    code = current.get("weather_code", 0)
    return {
        "temp": current.get("temperature_2m", "?"),
        "humidity": current.get("relative_humidity_2m", "?"),
        "wind": current.get("wind_speed_10m", "?"),
        "description": codes.get(code, f"Kod {code}"),
        "icon": codes.get(code, "❓"),
    }


def get_currency_live(base: str = "PLN") -> dict:
    return _get_json(f"https://open.er-api.com/v6/latest/{base}")


# ═══════════════════════════════════════════════════════════════
# TOOLS — funkcje wywoływane przez Hermesa
# ═══════════════════════════════════════════════════════════════

def find_restaurants(city: str, cuisine: str = None, romantic_only: bool = False,
                     max_price: str = None, limit: int = 10) -> dict:
    """Znajdź restauracje w mieście."""
    city_lower = city.lower()
    restaurants = []

    for key in MOCK_RESTAURANTS:
        if city_lower in key or key in city_lower:
            restaurants = MOCK_RESTAURANTS[key]
            break

    if cuisine:
        cuisine_norm = CUISINE_MAP.get(cuisine.lower(), cuisine.lower())
        restaurants = [r for r in restaurants if cuisine_norm in r.get("cuisine", "").lower()]

    if romantic_only:
        restaurants = [r for r in restaurants if r.get("romantic")]

    if max_price:
        price_levels = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}
        max_level = price_levels.get(max_price, 4)
        restaurants = [r for r in restaurants if len(r.get("price", "$")) <= max_level]

    return {"restaurants": restaurants[:limit], "count": len(restaurants[:limit]), "city": city}


def find_hotels(city: str, checkin: str = None, checkout: str = None,
                guests: int = 2, limit: int = 5) -> dict:
    """Znajdź hotele w mieście."""
    city_lower = city.lower()
    hotels = []

    for key in MOCK_HOTELS:
        if city_lower in key or key in city_lower:
            hotels = MOCK_HOTELS[key]
            break

    nights = 1
    if checkin and checkout:
        try:
            d1 = datetime.fromisoformat(checkin)
            d2 = datetime.fromisoformat(checkout)
            nights = max(1, (d2 - d1).days)
        except:
            pass

    result = []
    for h in hotels[:limit]:
        result.append({**h, "total_price": h["price_per_night"] * nights, "nights": nights})

    return {"hotels": result, "count": len(result), "city": city, "nights": nights}


def find_events(city: str, date: str = None, category: str = None, limit: int = 10) -> dict:
    """Znajdź wydarzenia w mieście."""
    city_lower = city.lower()
    events = []

    for key in MOCK_EVENTS:
        if city_lower in key or key in city_lower:
            events = MOCK_EVENTS[key]
            break

    if date:
        events = [e for e in events if e["date"] >= date]

    if category:
        events = [e for e in events if category.lower() in e.get("category", "").lower()]

    return {"events": events[:limit], "count": len(events[:limit]), "city": city}


def get_weather(city: str, use_live: bool = False) -> dict:
    """Pobierz pogodę."""
    city_lower = city.lower()

    if use_live:
        coord = CITY_COORDS.get(city_lower)
        if coord:
            live = get_weather_live(*coord)
            if "error" not in live:
                return {"weather": live, "city": city, "source": "live (Open-Meteo)"}

    weather = MOCK_WEATHER.get(city_lower, {"temp": "?", "description": "Brak danych", "icon": "❓"})
    return {"weather": weather, "city": city, "source": "mock"}


def convert_currency(amount: float, from_cur: str, to_cur: str, use_live: bool = False) -> dict:
    """Konwertuj walutę."""
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()

    if use_live:
        data = get_currency_live(from_cur)
        if "error" not in data:
            rate = data.get("rates", {}).get(to_cur, 0)
            return {"amount": amount, "from": from_cur, "to": to_cur,
                    "rate": rate, "result": amount * rate, "source": "live"}

    from_rate = MOCK_CURRENCIES.get(from_cur, 1.0)
    to_rate = MOCK_CURRENCIES.get(to_cur, 1.0)
    rate = to_rate / from_rate
    return {"amount": amount, "from": from_cur, "to": to_cur,
            "rate": rate, "result": amount * rate, "source": "mock"}


def plan_date_night(city: str) -> dict:
    """Zaplanuj randkę."""
    restaurants = find_restaurants(city, romantic_only=True, limit=5)
    events = find_events(city, limit=5)
    weather = get_weather(city)

    romantic_r = restaurants["restaurants"]
    dinner = romantic_r[0] if romantic_r else None
    event = events["events"][0] if events["events"] else None

    # Znajdź bar
    bars = find_restaurants(city, cuisine="wine bar", limit=3)
    bar = bars["restaurants"][0] if bars["restaurants"] else None

    return {
        "city": city,
        "weather": weather["weather"],
        "dinner": dinner,
        "event": event,
        "drinks": bar,
        "plan": (
            f"🍽️  Kolacja: {dinner['name']} ({dinner['rating']}⭐) — {dinner['address']}\n"
            f"🎭  Wydarzenie: {event['name']} ({event['date']}) — {event['venue']}\n"
            f"🍸  Drink: {bar['name']} ({bar['rating']}⭐) — {bar['address']}"
        ) if dinner and event and bar else "Nie udało się zaplanować — za mało danych",
    }


def full_travel_plan(city: str, checkin: str, checkout: str, guests: int = 2) -> dict:
    """Stwórz pełny plan podróży."""
    hotels = find_hotels(city, checkin, checkout, guests)
    restaurants = find_restaurants(city, limit=5)
    events = find_events(city, limit=5)
    weather = get_weather(city)

    hotel = hotels["hotels"][0] if hotels["hotels"] else None
    total_hotel = hotel["total_price"] if hotel else 0

    return {
        "city": city,
        "dates": f"{checkin} → {checkout}",
        "guests": guests,
        "weather": weather["weather"],
        "hotel": hotel,
        "total_hotel_pln": total_hotel,
        "top_restaurants": restaurants["restaurants"][:3],
        "top_events": events["events"][:3],
    }


def find_attractions(city: str, limit: int = 10) -> dict:
    """Znajdź atrakcje turystyczne w mieście (Polska + Europa)."""
    city_lower = city.lower()

    # Szukaj w Polsce
    for key in POLAND_ATTRACTIONS:
        if city_lower in key or key in city_lower:
            attractions = POLAND_ATTRACTIONS[key]
            return {"attractions": attractions[:limit], "count": len(attractions[:limit]),
                    "city": city, "source": "Poland"}

    # Szukaj w Europie
    for key in EUROPE_ATTRACTIONS:
        if city_lower in key or key in city_lower:
            attractions = EUROPE_ATTRACTIONS[key]
            return {"attractions": attractions[:limit], "count": len(attractions[:limit]),
                    "city": city, "source": "Europe"}

    return {"attractions": [], "count": 0, "city": city, "source": "not found"}


def plan_day_trip(city: str) -> dict:
    """Zaplanuj jednodniową wycieczkę: atrakcje + restauracja + wydarzenie."""
    attractions = find_attractions(city, limit=5)
    restaurants = find_restaurants(city, limit=5)
    events = find_events(city, limit=5)
    weather = get_weather(city)

    top_attraction = attractions["attractions"][0] if attractions["attractions"] else None
    top_restaurant = restaurants["restaurants"][0] if restaurants["restaurants"] else None
    top_event = events["events"][0] if events["events"] else None

    # Buduj plan tekstowy
    plan_lines = []
    if top_attraction:
        plan_lines.append(f"🏛️  Atrakcja: {top_attraction['name']} ({top_attraction['rating']}⭐) — {top_attraction.get('price', '?')}")
    if top_restaurant:
        plan_lines.append(f"🍽️  Obiad: {top_restaurant['name']} ({top_restaurant['rating']}⭐) — {top_restaurant['address']}")
    if top_event:
        plan_lines.append(f"🎭  Wydarzenie: {top_event['name']} ({top_event['date']}) — {top_event['venue']}")

    return {
        "city": city,
        "weather": weather["weather"],
        "top_attraction": top_attraction,
        "top_restaurant": top_restaurant,
        "top_event": top_event,
        "all_attractions": attractions["attractions"],
        "all_restaurants": restaurants["restaurants"],
        "all_events": events["events"],
        "plan": "\n".join(plan_lines) if plan_lines else "Nie udało się zaplanować — za mało danych",
    }


# ═══════════════════════════════════════════════════════════════
# MAIN — do testowania
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Hermes Travel Plugin — test")
        print("  python3 travel_plugin.py restaurants Gdańsk włoska")
        print("  python3 travel_plugin.py hotels Warszawa 2026-08-01 2026-08-03")
        print("  python3 travel_plugin.py events Gdańsk 2026-07-25")
        print("  python3 travel_plugin.py weather Gdańsk")
        print("  python3 travel_plugin.py currency 100 PLN EUR")
        print("  python3 travel_plugin.py date-night Sopot")
        print("  python3 travel_plugin.py full-plan Kraków 2026-08-01 2026-08-03")
        print("  python3 travel_plugin.py attractions Gdańsk")
        print("  python3 travel_plugin.py day-trip Kraków")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "restaurants":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        cuisine = sys.argv[3] if len(sys.argv) > 3 else None
        result = find_restaurants(city, cuisine)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "hotels":
        city = sys.argv[2] if len(sys.argv) > 2 else "Warszawa"
        checkin = sys.argv[3] if len(sys.argv) > 3 else None
        checkout = sys.argv[4] if len(sys.argv) > 4 else None
        guests = int(sys.argv[5]) if len(sys.argv) > 5 else 2
        result = find_hotels(city, checkin, checkout, guests)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "events":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        date = sys.argv[3] if len(sys.argv) > 3 else None
        result = find_events(city, date)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "weather":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        use_live = "--live" in sys.argv
        result = get_weather(city, use_live)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "currency":
        amount = float(sys.argv[2]) if len(sys.argv) > 2 else 100
        from_cur = sys.argv[3] if len(sys.argv) > 3 else "PLN"
        to_cur = sys.argv[4] if len(sys.argv) > 4 else "EUR"
        use_live = "--live" in sys.argv
        result = convert_currency(amount, from_cur, to_cur, use_live)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "date-night":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        result = plan_date_night(city)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "full-plan":
        city = sys.argv[2] if len(sys.argv) > 2 else "Kraków"
        checkin = sys.argv[3] if len(sys.argv) > 3 else "2026-08-01"
        checkout = sys.argv[4] if len(sys.argv) > 4 else "2026-08-03"
        guests = int(sys.argv[5]) if len(sys.argv) > 5 else 2
        result = full_travel_plan(city, checkin, checkout, guests)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "attractions":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        result = find_attractions(city)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif cmd == "day-trip":
        city = sys.argv[2] if len(sys.argv) > 2 else "Kraków"
        result = plan_day_trip(city)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        print(f"Nieznana komenda: {cmd}")
