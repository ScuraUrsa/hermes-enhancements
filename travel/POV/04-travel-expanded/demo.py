#!/usr/bin/env python3
"""
POV: Travel & Events — rozszerzenie o hotele, pogodę, waluty, więcej miast.

Użycie:
    python3 demo.py hotels Warszawa 2026-08-01 2026-08-03
    python3 demo.py weather Gdańsk
    python3 demo.py currency PLN EUR 100
    python3 demo.py full-plan Warszawa 2026-08-01 2026-08-03 2
"""

import sys
import json
import os
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


# === MOCK DATA — Hotele ===

MOCK_HOTELS = {
    "warszawa": [
        {"name": "Hotel Bristol", "stars": 5, "rating": 4.8, "price_per_night": 850,
         "address": "Krakowskie Przedmieście 42/44, Warszawa", "amenities": "SPA, basen, restauracja"},
        {"name": "Raffles Europejski", "stars": 5, "rating": 4.9, "price_per_night": 1200,
         "address": "Krakowskie Przedmieście 13, Warszawa", "amenities": "SPA, 2 restauracje, bar"},
        {"name": "InterContinental Warszawa", "stars": 5, "rating": 4.7, "price_per_night": 700,
         "address": "Emilii Plater 49, Warszawa", "amenities": "Basen, SPA, widok na miasto"},
        {"name": "Mamaison Le Regina", "stars": 5, "rating": 4.6, "price_per_night": 600,
         "address": "Kościelna 12, Warszawa", "amenities": "SPA, restauracja, parking"},
        {"name": "PURO Warszawa Centrum", "stars": 4, "rating": 4.5, "price_per_night": 400,
         "address": "ul. Widok 9, Warszawa", "amenities": "Design hotel, śniadanie, bar"},
    ],
    "kraków": [
        {"name": "Hotel Stary", "stars": 5, "rating": 4.9, "price_per_night": 900,
         "address": "Szczepańska 5, Kraków", "amenities": "SPA, basen na dachu, restauracja"},
        {"name": "Hotel Copernicus", "stars": 5, "rating": 4.8, "price_per_night": 800,
         "address": "Kanonicza 16, Kraków", "amenities": "Historyczny budynek, SPA"},
        {"name": "Bachleda Luxury Hotel", "stars": 5, "rating": 4.7, "price_per_night": 750,
         "address": "Plac Kossaka 6, Kraków", "amenities": "SPA, widok na Wawel"},
        {"name": "PURO Kraków Stare Miasto", "stars": 4, "rating": 4.5, "price_per_night": 380,
         "address": "ul. Ogrodowa 10, Kraków", "amenities": "Design, śniadanie, bar"},
    ],
    "wrocław": [
        {"name": "The Granary La Suite", "stars": 5, "rating": 4.8, "price_per_night": 650,
         "address": "Mennicza 24, Wrocław", "amenities": "SPA, restauracja, design"},
        {"name": "DoubleTree by Hilton", "stars": 4, "rating": 4.5, "price_per_night": 450,
         "address": "Podwale 84, Wrocław", "amenities": "Basen, SPA, parking"},
        {"name": "PURO Wrocław Stare Miasto", "stars": 4, "rating": 4.6, "price_per_night": 350,
         "address": "ul. Pawła Włodkowica 6, Wrocław", "amenities": "Design, śniadanie"},
    ],
    "gdańsk": [
        {"name": "Hilton Gdańsk", "stars": 5, "rating": 4.6, "price_per_night": 600,
         "address": "Targ Rybny 1, Gdańsk", "amenities": "Basen, SPA, widok na Motławę"},
        {"name": "PURO Gdańsk Stare Miasto", "stars": 4, "rating": 4.5, "price_per_night": 350,
         "address": "ul. Stągiewna 26, Gdańsk", "amenities": "Design, śniadanie, bar"},
        {"name": "Radisson Blu", "stars": 4, "rating": 4.4, "price_per_night": 400,
         "address": "Długi Targ 19, Gdańsk", "amenities": "Restauracja, centrum"},
    ],
    "sopot": [
        {"name": "Sofitel Grand Sopot", "stars": 5, "rating": 4.7, "price_per_night": 900,
         "address": "Powstańców Warszawy 12, Sopot", "amenities": "SPA, plaża, basen"},
        {"name": "Sheraton Sopot", "stars": 5, "rating": 4.6, "price_per_night": 800,
         "address": "Powstańców Warszawy 10, Sopot", "amenities": "SPA, plaża, restauracja"},
    ],
}


# === MOCK DATA — Pogoda ===

MOCK_WEATHER = {
    "gdańsk": {"temp": 22, "feels_like": 20, "humidity": 65, "wind": 15, "description": "Częściowo słonecznie", "icon": "⛅"},
    "sopot": {"temp": 21, "feels_like": 19, "humidity": 70, "wind": 18, "description": "Lekki wiatr od morza", "icon": "🌤️"},
    "gdynia": {"temp": 20, "feels_like": 18, "humidity": 72, "wind": 20, "description": "Wietrznie", "icon": "💨"},
    "warszawa": {"temp": 26, "feels_like": 25, "humidity": 55, "wind": 10, "description": "Słonecznie", "icon": "☀️"},
    "kraków": {"temp": 27, "feels_like": 26, "humidity": 50, "wind": 8, "description": "Słonecznie, gorąco", "icon": "☀️"},
    "wrocław": {"temp": 25, "feels_like": 24, "humidity": 58, "wind": 12, "description": "Słonecznie", "icon": "☀️"},
    "poznań": {"temp": 24, "feels_like": 23, "humidity": 60, "wind": 14, "description": "Częściowo słonecznie", "icon": "⛅"},
    "zakopane": {"temp": 18, "feels_like": 16, "humidity": 75, "wind": 5, "description": "Lekkie zachmurzenie", "icon": "🌥️"},
}


# === MOCK DATA — Waluty ===

MOCK_CURRENCIES = {
    "PLN": 1.0,
    "EUR": 4.25,
    "USD": 3.90,
    "GBP": 4.95,
    "CHF": 4.40,
    "CZK": 0.17,
    "HUF": 0.011,
    "NOK": 0.37,
    "SEK": 0.36,
    "DKK": 0.57,
}


# === API: Open-Meteo (darmowe, bez klucza) ===

def get_weather_live(lat: float, lng: float) -> dict:
    """Pobierz pogodę z Open-Meteo (darmowe API)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lng}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code"
        f"&timezone=Europe/Warsaw"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            current = data.get("current", {})
            weather_codes = {
                0: "Bezchmurnie ☀️", 1: "Prawie bezchmurnie 🌤️", 2: "Częściowo słonecznie ⛅",
                3: "Pochmurno ☁️", 45: "Mgła 🌫️", 51: "Lekka mżawka 🌧️",
                61: "Deszcz 🌧️", 80: "Przelotne opady 🌦️", 95: "Burza ⛈️",
            }
            code = current.get("weather_code", 0)
            return {
                "temp": current.get("temperature_2m", "?"),
                "humidity": current.get("relative_humidity_2m", "?"),
                "wind": current.get("wind_speed_10m", "?"),
                "description": weather_codes.get(code, f"Kod {code}"),
                "icon": weather_codes.get(code, "❓"),
            }
    except Exception as e:
        return {"error": str(e)}


# === API: ExchangeRate-API (darmowe, bez klucza) ===

def get_currency_live(base: str = "PLN") -> dict:
    """Pobierz kursy walut z ExchangeRate-API (darmowe)."""
    url = f"https://open.er-api.com/v6/latest/{base}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("rates", {})
    except Exception as e:
        return {"error": str(e)}


# === GŁÓWNE FUNKCJE ===

def find_hotels(city: str, checkin: str = None, checkout: str = None, guests: int = 2) -> list:
    """Znajdź hotele w mieście."""
    city_lower = city.lower()
    hotels = MOCK_HOTELS.get(city_lower, [])
    if not hotels:
        # Fallback: szukaj częściowego dopasowania
        for key in MOCK_HOTELS:
            if city_lower in key or key in city_lower:
                hotels = MOCK_HOTELS[key]
                break
    return hotels


def get_weather(city: str, use_live: bool = False) -> dict:
    """Pobierz pogodę dla miasta."""
    city_lower = city.lower()

    # Współrzędne dla polskich miast
    coords = {
        "gdańsk": (54.3520, 18.6466), "sopot": (54.4416, 18.5601),
        "gdynia": (54.5189, 18.5305), "warszawa": (52.2297, 21.0122),
        "kraków": (50.0647, 19.9450), "wrocław": (51.1079, 17.0385),
        "poznań": (52.4064, 16.9252), "zakopane": (49.2992, 19.9496),
    }

    if use_live:
        coord = coords.get(city_lower)
        if coord:
            return get_weather_live(*coord)

    return MOCK_WEATHER.get(city_lower, {"temp": "?", "description": "Brak danych", "icon": "❓"})


def convert_currency(amount: float, from_cur: str, to_cur: str, use_live: bool = False) -> dict:
    """Konwertuj walutę."""
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()

    if use_live:
        rates = get_currency_live(from_cur)
        if "error" not in rates:
            rate = rates.get(to_cur, 0)
            return {"rate": rate, "result": amount * rate, "source": "live"}
        return {"error": rates.get("error", "API error")}

    # Mock
    from_rate = MOCK_CURRENCIES.get(from_cur, 1.0)
    to_rate = MOCK_CURRENCIES.get(to_cur, 1.0)
    rate = to_rate / from_rate
    return {"rate": rate, "result": amount * rate, "source": "mock"}


def full_plan(city: str, checkin: str, checkout: str, guests: int = 2) -> dict:
    """Stwórz pełny plan podróży."""
    hotels = find_hotels(city, checkin, checkout, guests)
    weather = get_weather(city)

    # Oblicz koszt
    nights = 1
    if checkin and checkout:
        try:
            d1 = datetime.fromisoformat(checkin)
            d2 = datetime.fromisoformat(checkout)
            nights = max(1, (d2 - d1).days)
        except:
            pass

    hotel = hotels[0] if hotels else None
    total_hotel = hotel["price_per_night"] * nights if hotel else 0

    return {
        "city": city,
        "dates": f"{checkin} → {checkout} ({nights} noclegów)",
        "guests": guests,
        "weather": weather,
        "hotel": hotel,
        "total_hotel_pln": total_hotel,
        "all_hotels": hotels,
    }


# === FORMATTERS ===

def format_hotel(h: dict, nights: int = 1) -> str:
    stars = "⭐" * h.get("stars", 0)
    return (
        f"  🏨 {h['name']} {stars} | ⭐{h['rating']}\n"
        f"     📍 {h['address']}\n"
        f"     💰 {h['price_per_night']} PLN/noc × {nights} = {h['price_per_night'] * nights} PLN\n"
        f"     🛎️  {h['amenities']}"
    )


def format_weather(w: dict) -> str:
    return f"  {w.get('icon', '❓')} {w.get('description', '?')} | 🌡️ {w.get('temp', '?')}°C | 💧 {w.get('humidity', '?')}% | 💨 {w.get('wind', '?')} km/h"


def format_currency(result: dict, amount: float, from_cur: str, to_cur: str) -> str:
    if "error" in result:
        return f"  ❌ Błąd: {result['error']}"
    return f"  💱 {amount} {from_cur} = {result['result']:.2f} {to_cur} (kurs: {result['rate']:.4f}) [{result['source']}]"


# === MAIN ===

def main():
    if len(sys.argv) < 2:
        print("Użycie:")
        print("  python3 demo.py hotels <miasto> [checkin] [checkout] [goście]")
        print("  python3 demo.py weather <miasto> [--live]")
        print("  python3 demo.py currency <kwota> <z> <do> [--live]")
        print("  python3 demo.py full-plan <miasto> <checkin> <checkout> [goście]")
        print()
        print("Przykłady:")
        print("  python3 demo.py hotels Warszawa 2026-08-01 2026-08-03 2")
        print("  python3 demo.py weather Gdańsk --live")
        print("  python3 demo.py currency 100 PLN EUR")
        print("  python3 demo.py full-plan Kraków 2026-08-01 2026-08-03")
        return

    cmd = sys.argv[1]

    print("=" * 60)
    print("🧳 TRAVEL & EVENTS — ROZSZERZENIE")
    print("=" * 60)
    print()

    if cmd == "hotels":
        city = sys.argv[2] if len(sys.argv) > 2 else "Warszawa"
        checkin = sys.argv[3] if len(sys.argv) > 3 else None
        checkout = sys.argv[4] if len(sys.argv) > 4 else None
        guests = int(sys.argv[5]) if len(sys.argv) > 5 else 2

        nights = 1
        if checkin and checkout:
            try:
                d1 = datetime.fromisoformat(checkin)
                d2 = datetime.fromisoformat(checkout)
                nights = max(1, (d2 - d1).days)
            except:
                pass

        print(f"🏨 Hotele w {city} ({checkin} → {checkout}, {guests} os., {nights} noclegów)")
        print()
        hotels = find_hotels(city, checkin, checkout, guests)
        for h in hotels:
            print(format_hotel(h, nights))
            print()

    elif cmd == "weather":
        city = sys.argv[2] if len(sys.argv) > 2 else "Gdańsk"
        use_live = "--live" in sys.argv
        print(f"🌤️  Pogoda: {city}")
        print()
        w = get_weather(city, use_live)
        print(format_weather(w))
        print()

    elif cmd == "currency":
        if len(sys.argv) < 5:
            print("Użycie: python3 demo.py currency <kwota> <z> <do> [--live]")
            return
        amount = float(sys.argv[2])
        from_cur = sys.argv[3]
        to_cur = sys.argv[4]
        use_live = "--live" in sys.argv
        print(f"💱 Konwersja: {amount} {from_cur} → {to_cur}")
        print()
        result = convert_currency(amount, from_cur, to_cur, use_live)
        print(format_currency(result, amount, from_cur, to_cur))
        print()

    elif cmd == "full-plan":
        if len(sys.argv) < 5:
            print("Użycie: python3 demo.py full-plan <miasto> <checkin> <checkout> [goście]")
            return
        city = sys.argv[2]
        checkin = sys.argv[3]
        checkout = sys.argv[4]
        guests = int(sys.argv[5]) if len(sys.argv) > 5 else 2

        plan = full_plan(city, checkin, checkout, guests)

        print(f"📋 PEŁNY PLAN: {city}")
        print(f"📅 {plan['dates']} | 👥 {plan['guests']} os.")
        print()
        print("🌤️  POGODA:")
        print(format_weather(plan["weather"]))
        print()
        print("🏨 ZAKWATEROWANIE:")
        if plan["hotel"]:
            nights = 1
            try:
                d1 = datetime.fromisoformat(checkin)
                d2 = datetime.fromisoformat(checkout)
                nights = max(1, (d2 - d1).days)
            except:
                pass
            print(format_hotel(plan["hotel"], nights))
        print()
        print(f"💰 Szacunkowy koszt hotelu: {plan['total_hotel_pln']} PLN")
        print()
        print("🏨 ALTERNATYWY:")
        for h in plan["all_hotels"][1:4]:
            print(f"  - {h['name']} ({h['stars']}⭐) — {h['price_per_night']} PLN/noc")

    else:
        print(f"Nieznana komenda: {cmd}")

    print()
    print("=" * 60)
    print("💡 API użyte (lub gotowe do użycia):")
    print("   - Open-Meteo: pogoda (darmowe, bez klucza)")
    print("   - ExchangeRate-API: waluty (darmowe, bez klucza)")
    print("   - Google Places: restauracje, miejsca (GCP key)")
    print("   - Ticketmaster: wydarzenia (API key)")
    print("=" * 60)


if __name__ == "__main__":
    main()
