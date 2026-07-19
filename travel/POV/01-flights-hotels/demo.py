#!/usr/bin/env python3
"""
POV #01: Flights & Hotels API Integration
Demonstracja integracji z API lotów i hoteli:
- Kayak Sandbox (Flights + Hotels Search) — darmowy sandbox
- Skyscanner Travel API — struktura (wymaga partner application)
- Booking.com Demand API v3 — struktura (wymaga Managed Affiliate)
- Duffel Flights API — self-service, REST

Wymagania:
    pip install requests python-dotenv

Użycie:
    python3 demo.py                          # Test wszystkich API (symulacja + real)
    python3 demo.py --kayak-flights WAW LON  # Kayak Flights Search
    python3 demo.py --kayak-hotels Paris     # Kayak Hotels Search
    python3 demo.py --duffel WAW LON         # Duffel Flights Search (real API)
    python3 demo.py --compare WAW LON        # Porównanie wszystkich API
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# ============================================================
# KONFIGURACJA
# ============================================================

CONFIG = {
    "kayak": {
        "sandbox_url": "https://sandbox.api.kayak.com",
        "flights_search": "/flights/search",
        "hotels_search": "/hotels/search",
        "auth_type": "API Key (X-API-Key header)",
        "status": "sandbox_free",
        "note": "Wymaga wypełnienia formularza na affiliates.kayak.com"
    },
    "skyscanner": {
        "base_url": "https://partners.api.skyscanner.net/apiservices/v3",
        "flights_live": "/flights/liveprices/query",
        "flights_indicative": "/flights/indicativeprices/query",
        "hotels_live": "/hotels/liveprices/query",
        "auth_type": "API Key (x-api-key header)",
        "status": "partner_required",
        "note": "Wymaga zatwierdzonej aplikacji partnerskiej"
    },
    "booking": {
        "base_url": "https://distribution-xml.booking.com/json",
        "hotels_search": "/hotel/search",
        "auth_type": "OAuth 2.0 + API Key",
        "status": "managed_affiliate_required",
        "note": "Wymaga bycia Managed Affiliate Partner"
    },
    "duffel": {
        "base_url": "https://api.duffel.com/air",
        "flights_search": "/offer_requests",
        "auth_type": "Bearer token (Duffel API key)",
        "status": "self_service",
        "note": "Self-service, rejestracja na duffel.com"
    }
}

# ============================================================
# HELPERS
# ============================================================

def get_api_key(service: str) -> Optional[str]:
    """Pobiera API key z env lub Bitwarden."""
    env_map = {
        "kayak": "KAYAK_API_KEY",
        "skyscanner": "SKYSCANNER_API_KEY",
        "booking": "BOOKING_API_KEY",
        "duffel": "DUFFEL_API_KEY"
    }
    
    key = os.environ.get(env_map.get(service, ""))
    if key:
        return key
    
    # Próba z Bitwarden (jeśli dostępny)
    bw_map = {
        "duffel": "duffel-api-key",
    }
    
    if service in bw_map:
        try:
            import subprocess
            result = subprocess.run(
                ["bws", "secret", "get", bw_map[service],
                 "--server-url", "https://vault.bitwarden.eu"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("value")
        except Exception:
            pass
    
    return None


def print_header(title: str):
    """Drukuje nagłówek sekcji."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_status(service: str, config: dict):
    """Drukuje status API."""
    status_icon = {"self_service": "🟢", "sandbox_free": "🟡", 
                   "partner_required": "🟠", "managed_affiliate_required": "🔴"}
    icon = status_icon.get(config["status"], "⚪")
    print(f"\n{icon} {service.upper()}")
    print(f"   Status: {config['status']}")
    print(f"   Auth:   {config['auth_type']}")
    print(f"   Uwaga:  {config['note']}")


# ============================================================
# KAYAK API (Sandbox — darmowy dostęp)
# ============================================================

def kayak_flights_search(origin: str, destination: str, 
                         depart_date: str = None,
                         return_date: str = None,
                         adults: int = 1) -> Dict[str, Any]:
    """
    Kayak Flights Search API — struktura zapytania.
    
    Endpoint: POST /flights/search
    Auth: X-API-Key header
    
    Dokumentacja: https://developers.kayak.com/
    """
    print_header("KAYAK — Flights Search (Sandbox)")
    print_status("kayak", CONFIG["kayak"])
    
    if depart_date is None:
        depart_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    if return_date is None:
        return_date = (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d")
    
    # Struktura requestu zgodna z dokumentacją Kayak
    request_body = {
        "origin": origin,
        "destination": destination,
        "departDate": depart_date,
        "returnDate": return_date,
        "adults": adults,
        "cabinClass": "economy",
        "currency": "PLN",
        "locale": "pl-PL"
    }
    
    print(f"\n📤 Request (POST /flights/search):")
    print(f"   Origin:      {origin}")
    print(f"   Destination: {destination}")
    print(f"   Depart:      {depart_date}")
    print(f"   Return:      {return_date}")
    print(f"   Adults:      {adults}")
    print(f"   Cabin:       economy")
    print(f"   Currency:    PLN")
    
    api_key = get_api_key("kayak")
    if not api_key:
        print(f"\n⚠️  Brak KAYAK_API_KEY — pokazuję strukturę odpowiedzi (symulacja)")
        return _simulate_kayak_flights_response(origin, destination, depart_date, return_date)
    
    # Real API call
    try:
        import requests
        resp = requests.post(
            f"{CONFIG['kayak']['sandbox_url']}{CONFIG['kayak']['flights_search']}",
            json=request_body,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=15
        )
        print(f"\n📥 Response ({resp.status_code}):")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False)[:2000])
        return resp.json()
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        return {"error": str(e)}


def kayak_hotels_search(destination: str,
                        checkin: str = None,
                        checkout: str = None,
                        guests: int = 2,
                        rooms: int = 1) -> Dict[str, Any]:
    """
    Kayak Hotels Search API — struktura zapytania.
    
    Endpoint: POST /hotels/search
    Auth: X-API-Key header
    
    Dokumentacja: https://affiliates.kayak.com/apis/hotels
    """
    print_header("KAYAK — Hotels Search (Sandbox)")
    print_status("kayak", CONFIG["kayak"])
    
    if checkin is None:
        checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    if checkout is None:
        checkout = (datetime.now() + timedelta(days=33)).strftime("%Y-%m-%d")
    
    request_body = {
        "destination": destination,
        "checkIn": checkin,
        "checkOut": checkout,
        "guests": guests,
        "rooms": rooms,
        "currency": "PLN",
        "locale": "pl-PL",
        "filters": {
            "stars": [3, 4, 5],
            "guestRating": {"min": 7.0},
            "maxPrice": 800
        }
    }
    
    print(f"\n📤 Request (POST /hotels/search):")
    print(f"   Destination: {destination}")
    print(f"   Check-in:    {checkin}")
    print(f"   Check-out:   {checkout}")
    print(f"   Guests:      {guests}")
    print(f"   Rooms:       {rooms}")
    print(f"   Filters:     stars 3-5, rating ≥7.0, max 800 PLN")
    
    api_key = get_api_key("kayak")
    if not api_key:
        print(f"\n⚠️  Brak KAYAK_API_KEY — pokazuję strukturę odpowiedzi (symulacja)")
        return _simulate_kayak_hotels_response(destination, checkin, checkout)
    
    try:
        import requests
        resp = requests.post(
            f"{CONFIG['kayak']['sandbox_url']}{CONFIG['kayak']['hotels_search']}",
            json=request_body,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=15
        )
        print(f"\n📥 Response ({resp.status_code}):")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False)[:2000])
        return resp.json()
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        return {"error": str(e)}


# ============================================================
# SKYSCANNER API (Partner required)
# ============================================================

def skyscanner_flights_search(origin: str, destination: str,
                              depart_date: str = None) -> Dict[str, Any]:
    """
    Skyscanner Flights Live Prices API — struktura zapytania.
    
    Endpoint: POST /flights/liveprices/query
    Auth: x-api-key header
    
    Dokumentacja: https://developers.skyscanner.net/docs/flights-live-prices/overview
    """
    print_header("SKYSCANNER — Flights Live Prices (Partner)")
    print_status("skyscanner", CONFIG["skyscanner"])
    
    if depart_date is None:
        depart_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Struktura zgodna z dokumentacją Skyscanner
    request_body = {
        "query": {
            "market": "PL",
            "locale": "pl-PL",
            "currency": "PLN",
            "queryLegs": [
                {
                    "originPlaceId": {"iata": origin},
                    "destinationPlaceId": {"iata": destination},
                    "date": {
                        "year": int(depart_date[:4]),
                        "month": int(depart_date[5:7]),
                        "day": int(depart_date[8:10])
                    }
                }
            ],
            "adults": 1,
            "cabinClass": "CABIN_CLASS_ECONOMY"
        }
    }
    
    print(f"\n📤 Request (POST /flights/liveprices/query):")
    print(f"   Market:      PL")
    print(f"   Locale:      pl-PL")
    print(f"   Currency:    PLN")
    print(f"   Origin:      {origin}")
    print(f"   Destination: {destination}")
    print(f"   Date:        {depart_date}")
    print(f"   Cabin:       ECONOMY")
    
    api_key = get_api_key("skyscanner")
    if not api_key:
        print(f"\n⚠️  Brak SKYSCANNER_API_KEY — pokazuję strukturę odpowiedzi (symulacja)")
        return _simulate_skyscanner_response(origin, destination, depart_date)
    
    try:
        import requests
        resp = requests.post(
            f"{CONFIG['skyscanner']['base_url']}{CONFIG['skyscanner']['flights_live']}",
            json=request_body,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            timeout=15
        )
        print(f"\n📥 Response ({resp.status_code}):")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False)[:2000])
        return resp.json()
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        return {"error": str(e)}


# ============================================================
# BOOKING.COM API (Managed Affiliate required)
# ============================================================

def booking_hotels_search(destination: str,
                          checkin: str = None,
                          checkout: str = None) -> Dict[str, Any]:
    """
    Booking.com Demand API v3 — struktura zapytania.
    
    Endpoint: POST /hotel/search
    Auth: OAuth 2.0 Bearer token
    
    Dokumentacja: https://developers.booking.com/demand
    """
    print_header("BOOKING.COM — Demand API v3 (Managed Affiliate)")
    print_status("booking", CONFIG["booking"])
    
    if checkin is None:
        checkin = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    if checkout is None:
        checkout = (datetime.now() + timedelta(days=33)).strftime("%Y-%m-%d")
    
    # Struktura zgodna z dokumentacją Booking.com Demand API
    request_body = {
        "checkin": checkin,
        "checkout": checkout,
        "guests": 2,
        "rooms": 1,
        "destination": {
            "type": "city",
            "value": destination
        },
        "currency": "PLN",
        "language": "pl",
        "filters": {
            "review_score": {"min": 7.0},
            "hotel_facility_type_ids": [1, 2, 3]  # hotele, hostele, apartamenty
        }
    }
    
    print(f"\n📤 Request (POST /hotel/search):")
    print(f"   Destination: {destination}")
    print(f"   Check-in:    {checkin}")
    print(f"   Check-out:   {checkout}")
    print(f"   Guests:      2")
    print(f"   Currency:    PLN")
    print(f"   Filters:     review ≥7.0")
    
    api_key = get_api_key("booking")
    if not api_key:
        print(f"\n⚠️  Brak BOOKING_API_KEY — pokazuję strukturę odpowiedzi (symulacja)")
        return _simulate_booking_response(destination, checkin, checkout)
    
    try:
        import requests
        resp = requests.post(
            f"{CONFIG['booking']['base_url']}{CONFIG['booking']['hotels_search']}",
            json=request_body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15
        )
        print(f"\n📥 Response ({resp.status_code}):")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False)[:2000])
        return resp.json()
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        return {"error": str(e)}


# ============================================================
# DUFFEL API (Self-service — można realnie testować!)
# ============================================================

def duffel_flights_search(origin: str, destination: str,
                           depart_date: str = None,
                           return_date: str = None,
                           adults: int = 1) -> Dict[str, Any]:
    """
    Duffel Flights API — realne zapytanie (self-service).
    
    Endpoint: POST /air/offer_requests
    Auth: Bearer token (Duffel API key)
    
    Dokumentacja: https://duffel.com/docs/api
    """
    print_header("DUFFEL — Flights Search (Self-Service 🟢)")
    print_status("duffel", CONFIG["duffel"])
    
    if depart_date is None:
        depart_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    if return_date is None:
        return_date = (datetime.now() + timedelta(days=37)).strftime("%Y-%m-%d")
    
    # Struktura zgodna z Duffel API
    request_body = {
        "data": {
            "slices": [
                {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": depart_date
                }
            ],
            "passengers": [{"type": "adult"} for _ in range(adults)],
            "cabin_class": "economy"
        }
    }
    
    if return_date:
        request_body["data"]["slices"].append({
            "origin": destination,
            "destination": origin,
            "departure_date": return_date
        })
    
    print(f"\n📤 Request (POST /air/offer_requests):")
    print(f"   Origin:      {origin}")
    print(f"   Destination: {destination}")
    print(f"   Depart:      {depart_date}")
    if return_date:
        print(f"   Return:      {return_date}")
    print(f"   Adults:      {adults}")
    print(f"   Cabin:       economy")
    
    api_key = get_api_key("duffel")
    if not api_key:
        print(f"\n⚠️  Brak DUFFEL_API_KEY — pokazuję strukturę odpowiedzi (symulacja)")
        print(f"   💡 Zarejestruj się na https://duffel.com — to self-service!")
        return _simulate_duffel_response(origin, destination, depart_date, return_date)
    
    # Real API call — Duffel jest self-service!
    try:
        import requests
        resp = requests.post(
            f"{CONFIG['duffel']['base_url']}{CONFIG['duffel']['flights_search']}",
            json=request_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Duffel-Version": "2024-05-15"
            },
            timeout=20
        )
        print(f"\n📥 Response ({resp.status_code}):")
        data = resp.json()
        
        if resp.status_code == 201:
            # Duffel zwraca 201 Created z offer_request
            offers = data.get("data", {}).get("offers", [])
            print(f"   Znaleziono ofert: {len(offers)}")
            for i, offer in enumerate(offers[:5]):
                price = offer.get("total_amount", "?")
                currency = offer.get("total_currency", "?")
                airline = offer.get("owner", {}).get("name", "?")
                print(f"   [{i+1}] {airline} — {price} {currency}")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
        
        return data
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        return {"error": str(e)}


# ============================================================
# SYMULACJE ODPOWIEDZI (gdy brak API key)
# ============================================================

def _simulate_kayak_flights_response(origin: str, destination: str, 
                                     depart: str, return_: str) -> Dict:
    return {
        "simulated": True,
        "provider": "Kayak Sandbox",
        "search": {
            "origin": origin,
            "destination": destination,
            "departDate": depart,
            "returnDate": return_
        },
        "results": [
            {
                "airline": "LOT Polish Airlines",
                "flightNumber": "LO 281",
                "departure": f"{depart}T06:30:00",
                "arrival": f"{depart}T08:45:00",
                "duration": "PT2H15M",
                "stops": 0,
                "price": {"amount": 349.00, "currency": "PLN"},
                "cabinClass": "economy"
            },
            {
                "airline": "Wizz Air",
                "flightNumber": "W6 1301",
                "departure": f"{depart}T14:20:00",
                "arrival": f"{depart}T16:55:00",
                "duration": "PT2H35M",
                "stops": 0,
                "price": {"amount": 189.00, "currency": "PLN"},
                "cabinClass": "economy"
            },
            {
                "airline": "Lufthansa",
                "flightNumber": "LH 1349",
                "departure": f"{depart}T10:15:00",
                "arrival": f"{depart}T14:30:00",
                "duration": "PT4H15M",
                "stops": 1,
                "price": {"amount": 520.00, "currency": "PLN"},
                "cabinClass": "economy"
            }
        ],
        "meta": {
            "totalResults": 3,
            "cheapestPrice": 189.00,
            "currency": "PLN"
        }
    }


def _simulate_kayak_hotels_response(destination: str, checkin: str, checkout: str) -> Dict:
    return {
        "simulated": True,
        "provider": "Kayak Sandbox",
        "search": {
            "destination": destination,
            "checkIn": checkin,
            "checkOut": checkout
        },
        "results": [
            {
                "name": "Hotel Bristol",
                "stars": 5,
                "rating": 9.2,
                "reviewCount": 1247,
                "pricePerNight": {"amount": 650.00, "currency": "PLN"},
                "totalPrice": {"amount": 1950.00, "currency": "PLN"},
                "amenities": ["WiFi", "Pool", "Spa", "Restaurant", "Gym"],
                "location": {"lat": 52.23, "lon": 21.01, "district": "Śródmieście"}
            },
            {
                "name": "PURO Hotel",
                "stars": 4,
                "rating": 8.9,
                "reviewCount": 892,
                "pricePerNight": {"amount": 380.00, "currency": "PLN"},
                "totalPrice": {"amount": 1140.00, "currency": "PLN"},
                "amenities": ["WiFi", "Restaurant", "Gym", "Parking"],
                "location": {"lat": 52.22, "lon": 21.00, "district": "Centrum"}
            },
            {
                "name": "Ibis Budget",
                "stars": 2,
                "rating": 7.8,
                "reviewCount": 2103,
                "pricePerNight": {"amount": 120.00, "currency": "PLN"},
                "totalPrice": {"amount": 360.00, "currency": "PLN"},
                "amenities": ["WiFi", "Parking"],
                "location": {"lat": 52.21, "lon": 20.98, "district": "Wola"}
            }
        ],
        "meta": {
            "totalResults": 3,
            "cheapestPerNight": 120.00,
            "currency": "PLN"
        }
    }


def _simulate_skyscanner_response(origin: str, destination: str, date: str) -> Dict:
    return {
        "simulated": True,
        "provider": "Skyscanner",
        "search": {
            "origin": origin,
            "destination": destination,
            "date": date
        },
        "results": {
            "itineraries": [
                {
                    "price": {"amount": "349.00", "currency": "PLN"},
                    "legs": [{
                        "carrier": "LOT Polish Airlines",
                        "flightNumber": "LO 281",
                        "departure": f"{date}T06:30",
                        "arrival": f"{date}T08:45",
                        "duration": "PT2H15M",
                        "stops": 0
                    }]
                }
            ],
            "stats": {
                "minPrice": 189.00,
                "maxPrice": 1200.00,
                "avgPrice": 450.00,
                "currency": "PLN"
            }
        }
    }


def _simulate_booking_response(destination: str, checkin: str, checkout: str) -> Dict:
    return {
        "simulated": True,
        "provider": "Booking.com Demand API v3",
        "search": {
            "destination": destination,
            "checkin": checkin,
            "checkout": checkout
        },
        "results": [
            {
                "hotel_id": "12345",
                "name": "Hotel Warszawa",
                "stars": 5,
                "review_score": 9.1,
                "review_count": 2341,
                "price": {"total": 1950.00, "currency": "PLN", "per_night": 650.00},
                "location": {"city": destination, "district": "Centrum"},
                "facilities": ["free_wifi", "swimming_pool", "spa", "fitness"],
                "images": ["https://example.com/hotel1.jpg"],
                "cancellation": "free_cancellation"
            }
        ],
        "meta": {
            "total_results": 1,
            "currency": "PLN"
        }
    }


def _simulate_duffel_response(origin: str, destination: str, 
                               depart: str, return_: str = None) -> Dict:
    return {
        "simulated": True,
        "provider": "Duffel",
        "search": {
            "origin": origin,
            "destination": destination,
            "departure_date": depart,
            "return_date": return_
        },
        "offers": [
            {
                "id": "off_001",
                "total_amount": "349.00",
                "total_currency": "PLN",
                "owner": {"name": "LOT Polish Airlines", "iata_code": "LO"},
                "slices": [{
                    "segments": [{
                        "flight_number": "LO 281",
                        "departing_at": f"{depart}T06:30:00",
                        "arriving_at": f"{depart}T08:45:00",
                        "duration": "PT2H15M"
                    }]
                }],
                "passengers": [{"type": "adult"}],
                "conditions": {"refundable": True, "changeable": True}
            }
        ]
    }


# ============================================================
# PORÓWNANIE API
# ============================================================

def compare_all_apis(origin: str, destination: str):
    """Porównuje wszystkie API dla tego samego zapytania."""
    print_header("PORÓWNANIE WSZYSTKICH API")
    print(f"\nTrasa: {origin} → {destination}")
    print(f"Data:  {(datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')}")
    print()
    
    apis = [
        ("Kayak (Sandbox)", "🟡", "Darmowy sandbox, Flights + Hotels"),
        ("Skyscanner", "🟠", "Partner API, najlepszy all-in-one"),
        ("Duffel", "🟢", "Self-service, REST, 300+ linii"),
        ("Booking.com", "🔴", "Managed Affiliate, hotele 28M+"),
        ("Amadeus", "⚫", "Enterprise only (self-service zamknięte 17.07.2026)"),
        ("Google Flights", "⚫", "Brak API (QPX Express zamknięty 2018)"),
        ("Airbnb", "⚫", "Brak publicznego API (tylko host API)"),
    ]
    
    print(f"{'API':<25} {'Status':<8} {'Opis'}")
    print("-" * 80)
    for name, icon, desc in apis:
        print(f"{name:<25} {icon:<8} {desc}")
    
    print(f"\n📊 Rekomendacja dla POV:")
    print(f"   1. Kayak Sandbox — najłatwiejszy start (darmowy)")
    print(f"   2. Duffel — self-service, można realnie testować")
    print(f"   3. Skyscanner — docelowo (najlepszy ekosystem)")


# ============================================================
# STATUS — przegląd wszystkich API
# ============================================================

def show_status():
    """Pokazuje status wszystkich API."""
    print_header("STATUS API — Loty + Hotele")
    print()
    
    print("✈️  LOTY:")
    print(f"   {'API':<20} {'Status':<30} {'Dostęp'}")
    print(f"   {'-'*20} {'-'*30} {'-'*20}")
    print(f"   {'Kayak':<20} {'🟡 Sandbox (darmowy)':<30} {'Formularz kontaktowy'}")
    print(f"   {'Duffel':<20} {'🟢 Self-service':<30} {'API key (instant)'}")
    print(f"   {'Skyscanner':<20} {'🟠 Partner required':<30} {'Aplikacja partnerska'}")
    print(f"   {'Amadeus':<20} {'⚫ Enterprise only':<30} {'Sales contact'}")
    print(f"   {'Google Flights':<20} {'⚫ Brak API':<30} {'N/A'}")
    
    print(f"\n🏨  HOTELE:")
    print(f"   {'API':<20} {'Status':<30} {'Dostęp'}")
    print(f"   {'-'*20} {'-'*30} {'-'*20}")
    print(f"   {'Kayak Hotels':<20} {'🟡 Sandbox (darmowy)':<30} {'Formularz kontaktowy'}")
    print(f"   {'Booking.com':<20} {'🔴 Managed Affiliate':<30} {'Aplikacja partnerska'}")
    print(f"   {'Skyscanner Hotels':<20} {'🟠 Partner required':<30} {'Aplikacja partnerska'}")
    print(f"   {'Airbnb':<20} {'⚫ Brak publicznego API':<30} {'Third-party scrapery'}")
    
    print(f"\n⚠️  WAŻNE ZMIANY (Lipiec 2026):")
    print(f"   ❌ Amadeus Self-Service — ZAMKNIĘTY 17.07.2026")
    print(f"   ❌ Google Flights QPX Express — zamknięty od 2018")
    print(f"   ❌ Airbnb — nigdy nie miało publicznego search API")
    print(f"   ✅ Kayak Sandbox — DZIAŁA (darmowy dostęp)")
    print(f"   ✅ Duffel — DZIAŁA (self-service)")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="POV #01: Flights & Hotels API Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python3 demo.py                              # Status + porównanie
  python3 demo.py --status                     # Tylko status
  python3 demo.py --kayak-flights WAW LON      # Kayak Flights
  python3 demo.py --kayak-hotels Paris         # Kayak Hotels
  python3 demo.py --duffel WAW LON             # Duffel (real API)
  python3 demo.py --compare WAW LON            # Porównanie
        """
    )
    
    parser.add_argument("--status", action="store_true", 
                        help="Pokaż status wszystkich API")
    parser.add_argument("--kayak-flights", nargs=2, metavar=("ORIGIN", "DEST"),
                        help="Kayak Flights Search (sandbox)")
    parser.add_argument("--kayak-hotels", nargs=1, metavar="DEST",
                        help="Kayak Hotels Search (sandbox)")
    parser.add_argument("--skyscanner", nargs=2, metavar=("ORIGIN", "DEST"),
                        help="Skyscanner Flights Search (partner)")
    parser.add_argument("--booking", nargs=1, metavar="DEST",
                        help="Booking.com Hotels Search (affiliate)")
    parser.add_argument("--duffel", nargs=2, metavar=("ORIGIN", "DEST"),
                        help="Duffel Flights Search (self-service)")
    parser.add_argument("--compare", nargs=2, metavar=("ORIGIN", "DEST"),
                        help="Porównaj wszystkie API")
    parser.add_argument("--depart", type=str, 
                        help="Data wylotu (YYYY-MM-DD)")
    parser.add_argument("--return", type=str, 
                        help="Data powrotu (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    # Domyślnie: status + porównanie
    if not any([args.status, args.kayak_flights, args.kayak_hotels,
                args.skyscanner, args.booking, args.duffel, args.compare]):
        show_status()
        compare_all_apis("WAW", "LON")
        print()
        print("💡 Uruchom z --help aby zobaczyć dostępne opcje")
        return
    
    if args.status:
        show_status()
    
    if args.kayak_flights:
        kayak_flights_search(args.kayak_flights[0], args.kayak_flights[1],
                            depart_date=args.depart, return_date=getattr(args, 'return'))
    
    if args.kayak_hotels:
        kayak_hotels_search(args.kayak_hotels[0],
                           checkin=args.depart, checkout=getattr(args, 'return'))
    
    if args.skyscanner:
        skyscanner_flights_search(args.skyscanner[0], args.skyscanner[1],
                                  depart_date=args.depart)
    
    if args.booking:
        booking_hotels_search(args.booking[0],
                             checkin=args.depart, checkout=getattr(args, 'return'))
    
    if args.duffel:
        duffel_flights_search(args.duffel[0], args.duffel[1],
                             depart_date=args.depart, return_date=getattr(args, 'return'))
    
    if args.compare:
        compare_all_apis(args.compare[0], args.compare[1])


if __name__ == "__main__":
    main()
