#!/usr/bin/env python3
"""
POV #02: Transport lokalny + Mapy + Randki
===========================================
Date Night Planner — integracja Google Maps, Uber, TripAdvisor, Yelp.

Demonstruje:
1. Google Maps Routes API — trasa + czas dojazdu na randkę
2. Google Maps Places API — wyszukiwanie romantycznych miejsc
3. Uber API — szacowanie ceny i czasu przejazdu
4. TripAdvisor Content API — recenzje i zdjęcia miejsc
5. Yelp Fusion API — kategorie, ratingi, recenzje

Wymagane zmienne środowiskowe:
    GOOGLE_MAPS_API_KEY — GCP API key z włączonym Routes API i Places API
    UBER_CLIENT_ID, UBER_CLIENT_SECRET — z Uber Developer Dashboard
    TRIPADVISOR_API_KEY — z TripAdvisor Developer Portal
    YELP_API_KEY — z Yelp Fusion Developer Portal

Użycie:
    python3 demo.py
    python3 demo.py --city "Gdańsk" --budget 2
"""

import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


# ─── Konfiguracja ───────────────────────────────────────────────────────────

@dataclass
class Config:
    google_api_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_MAPS_API_KEY", ""))
    uber_client_id: str = field(default_factory=lambda: os.environ.get("UBER_CLIENT_ID", ""))
    uber_client_secret: str = field(default_factory=lambda: os.environ.get("UBER_CLIENT_SECRET", ""))
    tripadvisor_api_key: str = field(default_factory=lambda: os.environ.get("TRIPADVISOR_API_KEY", ""))
    yelp_api_key: str = field(default_factory=lambda: os.environ.get("YELP_API_KEY", ""))

    # Domyślne współrzędne — Gdańsk Śródmieście
    default_lat: float = 54.3520
    default_lng: float = 18.6466
    default_city: str = "Gdańsk"


# ─── Klient Google Maps ─────────────────────────────────────────────────────

class GoogleMapsClient:
    """Klient Google Maps Platform — Routes API (nowe) + Places API (New)."""

    ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"
    PLACES_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
    PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self, field_mask: str = None) -> dict:
        h = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
        }
        if field_mask:
            h["X-Goog-FieldMask"] = field_mask
        return h

    def geocode(self, address: str) -> Optional[tuple[float, float]]:
        """Geokodowanie adresu → (lat, lng)."""
        params = urllib.parse.urlencode({"address": address, "key": self.api_key})
        url = f"{self.GEOCODE_URL}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read())
            if data.get("status") == "OK":
                loc = data["results"][0]["geometry"]["location"]
                return loc["lat"], loc["lng"]
        except Exception as e:
            print(f"  [WARN] Geocode failed: {e}")
        return None

    def compute_route(
        self,
        origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
        travel_mode: str = "DRIVE",
    ) -> Optional[dict]:
        """
        Oblicza trasę używając Routes API (nowe, POST).
        travel_mode: DRIVE, WALK, BICYCLE, TRANSIT, TWO_WHEELER
        """
        body = {
            "origin": {
                "location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}
            },
            "destination": {
                "location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}
            },
            "travelMode": travel_mode,
            "computeAlternativeRoutes": False,
            "languageCode": "pl",
            "units": "METRIC",
        }
        req = urllib.request.Request(
            self.ROUTES_URL,
            data=json.dumps(body).encode(),
            headers=self._headers(
                "routes.duration,routes.distanceMeters,routes.description,"
                "routes.legs.steps.transitDetails"
            ),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            print(f"  [WARN] Routes API error: {e.code} {e.reason}")
            return None
        except Exception as e:
            print(f"  [WARN] Routes API failed: {e}")
            return None

    def nearby_places(
        self,
        lat: float, lng: float,
        radius: int = 2000,
        place_types: list = None,
        max_results: int = 10,
    ) -> list[dict]:
        """
        Wyszukiwanie miejsc w pobliżu (Places API New).
        place_types: restaurant, cafe, bar, night_club, park, etc.
        """
        if place_types is None:
            place_types = ["restaurant", "cafe", "bar"]

        body = {
            "includedTypes": place_types,
            "maxResultCount": max_results,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
            "languageCode": "pl",
        }
        req = urllib.request.Request(
            self.PLACES_NEARBY_URL,
            data=json.dumps(body).encode(),
            headers=self._headers(
                "places.id,places.displayName,places.types,places.rating,"
                "places.userRatingCount,places.priceLevel,places.location,"
                "places.googleMapsUri,places.primaryTypeDisplayName"
            ),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            return data.get("places", [])
        except urllib.error.HTTPError as e:
            print(f"  [WARN] Places API error: {e.code} {e.reason}")
            return []
        except Exception as e:
            print(f"  [WARN] Places API failed: {e}")
            return []

    def place_details(self, place_id: str) -> Optional[dict]:
        """Szczegóły miejsca (Place Details New)."""
        url = self.PLACE_DETAILS_URL.format(place_id=place_id)
        req = urllib.request.Request(
            url,
            headers=self._headers(
                "id,displayName,formattedAddress,rating,userRatingCount,"
                "priceLevel,googleMapsUri,websiteUri,internationalPhoneNumber,"
                "regularOpeningHours,reviews,photos"
            ),
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  [WARN] Place Details failed: {e}")
            return None


# ─── Klient Uber ────────────────────────────────────────────────────────────

class UberClient:
    """Klient Uber Riders API v1.2 — szacowanie cen i czasu."""

    BASE_URL = "https://api.uber.com/v1.2"
    AUTH_URL = "https://auth.uber.com/oauth/v2/token"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None

    def _get_token(self) -> Optional[str]:
        """Uzyskaj OAuth 2.0 token (client credentials)."""
        if self._token:
            return self._token
        body = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
            "scope": "eats.deliveries",  # minimal scope for estimates
        }).encode()
        req = urllib.request.Request(self.AUTH_URL, data=body, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            self._token = data.get("access_token")
            return self._token
        except Exception as e:
            print(f"  [WARN] Uber auth failed: {e}")
            return None

    def _headers(self) -> dict:
        token = self._get_token()
        if not token:
            return {}
        return {
            "Authorization": f"Bearer {token}",
            "Accept-Language": "pl",
        }

    def get_products(self, lat: float, lng: float) -> list[dict]:
        """Lista dostępnych produktów Uber w danej lokalizacji."""
        url = f"{self.BASE_URL}/products?latitude={lat}&longitude={lng}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("products", [])
        except Exception as e:
            print(f"  [WARN] Uber products failed: {e}")
            return []

    def price_estimate(
        self,
        start_lat: float, start_lng: float,
        end_lat: float, end_lng: float,
    ) -> list[dict]:
        """Szacunkowe ceny przejazdu."""
        params = urllib.parse.urlencode({
            "start_latitude": start_lat,
            "start_longitude": start_lng,
            "end_latitude": end_lat,
            "end_longitude": end_lng,
        })
        url = f"{self.BASE_URL}/estimates/price?{params}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("prices", [])
        except Exception as e:
            print(f"  [WARN] Uber price estimate failed: {e}")
            return []

    def time_estimate(self, lat: float, lng: float) -> list[dict]:
        """Szacunkowy czas przyjazdu Ubera."""
        params = urllib.parse.urlencode({
            "start_latitude": lat,
            "start_longitude": lng,
        })
        url = f"{self.BASE_URL}/estimates/time?{params}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("times", [])
        except Exception as e:
            print(f"  [WARN] Uber time estimate failed: {e}")
            return []


# ─── Klient TripAdvisor ─────────────────────────────────────────────────────

class TripAdvisorClient:
    """Klient TripAdvisor Content API — wyszukiwanie miejsc i recenzji."""

    BASE_URL = "https://api.content.tripadvisor.com/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"accept": "application/json", "X-TripAdvisor-API-Key": self.api_key}

    def search_locations(self, query: str, category: str = "restaurants", lat: float = None, lng: float = None) -> list[dict]:
        """Wyszukiwanie lokacji."""
        params = {"searchQuery": query, "category": category, "language": "pl"}
        if lat and lng:
            params["lat"] = lat
            params["lng"] = lng
        url = f"{self.BASE_URL}/location/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("data", [])
        except Exception as e:
            print(f"  [WARN] TripAdvisor search failed: {e}")
            return []

    def location_details(self, location_id: str) -> Optional[dict]:
        """Szczegóły lokacji."""
        url = f"{self.BASE_URL}/location/{location_id}/details?language=pl"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  [WARN] TripAdvisor details failed: {e}")
            return None

    def location_reviews(self, location_id: str) -> list[dict]:
        """Recenzje lokacji."""
        url = f"{self.BASE_URL}/location/{location_id}/reviews?language=pl"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("data", [])
        except Exception as e:
            print(f"  [WARN] TripAdvisor reviews failed: {e}")
            return []


# ─── Klient Yelp ────────────────────────────────────────────────────────────

class YelpClient:
    """Klient Yelp Fusion API v3 — wyszukiwanie firm i recenzji."""

    BASE_URL = "https://api.yelp.com/v3"

    # Kategorie Yelp przydatne na randki
    DATE_CATEGORIES = [
        "restaurants", "french", "italian", "japanese", "wine_bars",
        "cocktailbars", "coffee", "desserts", "nightlife",
        "arts", "museums", "parks", "bowling",
    ]

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    def search_businesses(
        self,
        term: str = "romantic",
        location: str = "Gdańsk",
        categories: str = "restaurants",
        price: str = None,
        limit: int = 10,
        sort_by: str = "rating",
    ) -> list[dict]:
        """Wyszukiwanie firm."""
        params = {
            "term": term,
            "location": location,
            "categories": categories,
            "limit": limit,
            "sort_by": sort_by,
            "locale": "pl_PL",
        }
        if price:
            params["price"] = price  # 1,2,3,4 (od $ do $$$$)
        url = f"{self.BASE_URL}/businesses/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("businesses", [])
        except Exception as e:
            print(f"  [WARN] Yelp search failed: {e}")
            return []

    def business_details(self, business_id: str) -> Optional[dict]:
        """Szczegóły firmy."""
        url = f"{self.BASE_URL}/businesses/{business_id}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            print(f"  [WARN] Yelp details failed: {e}")
            return None

    def business_reviews(self, business_id: str) -> list[dict]:
        """Recenzje firmy."""
        url = f"{self.BASE_URL}/businesses/{business_id}/reviews?locale=pl_PL"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return data.get("reviews", [])
        except Exception as e:
            print(f"  [WARN] Yelp reviews failed: {e}")
            return []


# ─── Date Night Planner ─────────────────────────────────────────────────────

class DateNightPlanner:
    """
    Łączy wszystkie API w jeden planer randkowy.

    Flow:
    1. Geokodowanie adresu startowego i docelowego
    2. Google Maps Routes — trasa + czas dojazdu
    3. Google Maps Places — miejsca w pobliżu celu
    4. Uber — szacowanie ceny przejazdu
    5. TripAdvisor — recenzje i zdjęcia
    6. Yelp — kategorie i ratingi
    """

    def __init__(self, config: Config):
        self.config = config
        self.gmaps = GoogleMapsClient(config.google_api_key) if config.google_api_key else None
        self.uber = UberClient(config.uber_client_id, config.uber_client_secret) if config.uber_client_id else None
        self.tripadvisor = TripAdvisorClient(config.tripadvisor_api_key) if config.tripadvisor_api_key else None
        self.yelp = YelpClient(config.yelp_api_key) if config.yelp_api_key else None

    def plan(
        self,
        origin_address: str,
        destination_address: str,
        budget: int = 2,  # 1=$, 2=$$, 3=$$$, 4=$$$$
        travel_mode: str = "DRIVE",
        vibe: str = "romantic",
        log=None,
    ) -> dict:
        """
        Główna funkcja planowania randki.

        Args:
            origin_address: adres startowy (np. "Gdańsk Wrzeszcz")
            destination_address: adres docelowy (np. "Gdańsk Śródmieście")
            budget: poziom cenowy 1-4
            travel_mode: DRIVE, WALK, BICYCLE, TRANSIT
            vibe: nastrój — romantic, casual, fancy, adventurous
            log: file handle for progress output (defaults to sys.stdout)

        Returns:
            dict z pełnym planem randki
        """
        if log is None:
            log = sys.stdout

        plan = {
            "origin": origin_address,
            "destination": destination_address,
            "budget": budget,
            "travel_mode": travel_mode,
            "vibe": vibe,
            "route": None,
            "places": [],
            "uber_estimates": [],
            "tripadvisor_venues": [],
            "yelp_venues": [],
            "errors": [],
        }

        # 1. Geokodowanie
        print(f"\n📍 Geokodowanie adresów...", file=log)
        origin_coords = None
        dest_coords = None

        if self.gmaps:
            origin_coords = self.gmaps.geocode(origin_address)
            dest_coords = self.gmaps.geocode(destination_address)

        if not origin_coords:
            origin_coords = (self.config.default_lat, self.config.default_lng)
            plan["errors"].append(f"Używam domyślnych współrzędnych dla origin")
        if not dest_coords:
            dest_coords = (self.config.default_lat + 0.02, self.config.default_lng + 0.02)
            plan["errors"].append(f"Używam domyślnych współrzędnych dla destination")

        plan["origin_coords"] = origin_coords
        plan["dest_coords"] = dest_coords
        print(f"  Origin: {origin_coords}", file=log)
        print(f"  Destination: {dest_coords}", file=log)

        # 2. Google Maps Routes
        if self.gmaps:
            print(f"\n🗺️  Obliczanie trasy ({travel_mode})...", file=log)
            route = self.gmaps.compute_route(
                origin_coords[0], origin_coords[1],
                dest_coords[0], dest_coords[1],
                travel_mode=travel_mode,
            )
            if route and "routes" in route:
                r = route["routes"][0]
                plan["route"] = {
                    "distance_meters": r.get("distanceMeters"),
                    "duration": r.get("duration"),
                    "description": r.get("description", ""),
                }
                duration_sec = int(r.get("duration", "0s").rstrip("s"))
                print(f"  Dystans: {r.get('distanceMeters', '?')}m", file=log)
                print(f"  Czas: {duration_sec // 60} min", file=log)
            else:
                plan["errors"].append("Routes API nie zwróciło trasy")

        # 3. Google Maps Places — miejsca w pobliżu celu
        if self.gmaps:
            print(f"\n🍽️  Wyszukiwanie miejsc w pobliżu celu...", file=log)
            place_types = self._vibe_to_place_types(vibe)
            places = self.gmaps.nearby_places(
                dest_coords[0], dest_coords[1],
                radius=2000,
                place_types=place_types,
                max_results=10,
            )
            for p in places:
                plan["places"].append({
                    "name": p.get("displayName", {}).get("text", "?"),
                    "types": p.get("types", []),
                    "rating": p.get("rating"),
                    "price_level": p.get("priceLevel"),
                    "maps_url": p.get("googleMapsUri", ""),
                })
            print(f"  Znaleziono {len(places)} miejsc", file=log)

        # 4. Uber — szacowanie ceny
        if self.uber:
            print(f"\n🚗 Szacowanie ceny Ubera...", file=log)
            prices = self.uber.price_estimate(
                origin_coords[0], origin_coords[1],
                dest_coords[0], dest_coords[1],
            )
            for p in prices:
                plan["uber_estimates"].append({
                    "name": p.get("display_name", p.get("localized_display_name", "?")),
                    "estimate": p.get("estimate", "?"),
                    "duration": p.get("duration"),
                    "distance": p.get("distance"),
                })
            print(f"  Dostępne opcje: {len(prices)}", file=log)

        # 5. TripAdvisor — wyszukiwanie miejsc
        if self.tripadvisor:
            print(f"\n⭐ TripAdvisor — wyszukiwanie...", file=log)
            ta_venues = self.tripadvisor.search_locations(
                query=vibe,
                category="restaurants",
                lat=dest_coords[0],
                lng=dest_coords[1],
            )
            for v in ta_venues[:5]:
                plan["tripadvisor_venues"].append({
                    "name": v.get("name", "?"),
                    "location_id": v.get("location_id", ""),
                    "rating": v.get("rating"),
                    "num_reviews": v.get("num_reviews"),
                })
            print(f"  Znaleziono {len(ta_venues)} miejsc", file=log)

        # 6. Yelp — wyszukiwanie
        if self.yelp:
            print(f"\n🌟 Yelp — wyszukiwanie...", file=log)
            yelp_categories = self._vibe_to_yelp_categories(vibe)
            yelp_venues = self.yelp.search_businesses(
                term=vibe,
                location=destination_address.split(",")[0],
                categories=yelp_categories,
                price=str(budget) if budget else None,
                limit=10,
            )
            for v in yelp_venues:
                plan["yelp_venues"].append({
                    "name": v.get("name", "?"),
                    "rating": v.get("rating"),
                    "review_count": v.get("review_count"),
                    "price": v.get("price", "?"),
                    "url": v.get("url", ""),
                    "categories": [c.get("title") for c in v.get("categories", [])],
                })
            print(f"  Znaleziono {len(yelp_venues)} miejsc", file=log)

        return plan

    def _vibe_to_place_types(self, vibe: str) -> list[str]:
        mapping = {
            "romantic": ["restaurant", "cafe", "bar", "park", "art_gallery"],
            "casual": ["restaurant", "cafe", "bar", "movie_theater", "bowling_alley"],
            "fancy": ["restaurant", "bar", "night_club", "art_gallery", "museum"],
            "adventurous": ["park", "amusement_park", "hiking_area", "restaurant", "cafe"],
        }
        return mapping.get(vibe, ["restaurant", "cafe", "bar"])

    def _vibe_to_yelp_categories(self, vibe: str) -> str:
        mapping = {
            "romantic": "french,italian,wine_bars,cocktailbars",
            "casual": "restaurants,coffee,desserts",
            "fancy": "restaurants,cocktailbars,japanese",
            "adventurous": "restaurants,parks,active",
        }
        return mapping.get(vibe, "restaurants")


# ─── Formatowanie wyników ───────────────────────────────────────────────────

def print_plan(plan: dict):
    """Ładne formatowanie planu randki."""
    print("\n" + "=" * 70)
    print("  💘 DATE NIGHT PLANNER — Twój plan randki")
    print("=" * 70)

    print(f"\n📍 Z: {plan['origin']}")
    print(f"📍 Do: {plan['destination']}")
    print(f"💰 Budżet: {'$' * plan['budget']}")
    print(f"🚗 Transport: {plan['travel_mode']}")
    print(f"💫 Nastrój: {plan['vibe']}")

    # Trasa
    if plan.get("route"):
        r = plan["route"]
        dist_km = (r.get("distance_meters", 0) or 0) / 1000
        dur = r.get("duration", "?")
        print(f"\n🗺️  TRASA")
        print(f"   Dystans: {dist_km:.1f} km")
        print(f"   Czas: {dur}")
        if r.get("description"):
            print(f"   Opis: {r['description']}")

    # Uber
    if plan.get("uber_estimates"):
        print(f"\n🚗 UBER — Szacunkowe ceny")
        for u in plan["uber_estimates"]:
            print(f"   {u['name']}: {u['estimate']} | ~{u.get('duration', '?')} min")

    # Google Places
    if plan.get("places"):
        print(f"\n🍽️  GOOGLE PLACES — Miejsca w pobliżu")
        for i, p in enumerate(plan["places"][:8], 1):
            stars = "⭐" * int(p.get("rating", 0)) if p.get("rating") else "—"
            price = p.get("price_level", "?")
            print(f"   {i}. {p['name']}  {stars}  {price}")

    # TripAdvisor
    if plan.get("tripadvisor_venues"):
        print(f"\n⭐ TRIPADVISOR — Polecane miejsca")
        for i, v in enumerate(plan["tripadvisor_venues"][:5], 1):
            rating = v.get("rating", "?")
            reviews = v.get("num_reviews", 0)
            print(f"   {i}. {v['name']}  ⭐{rating}  ({reviews} recenzji)")

    # Yelp
    if plan.get("yelp_venues"):
        print(f"\n🌟 YELP — Najlepiej oceniane")
        for i, v in enumerate(plan["yelp_venues"][:5], 1):
            stars = "⭐" * int(v.get("rating", 0)) if v.get("rating") else "—"
            cats = ", ".join(v.get("categories", [])[:3])
            print(f"   {i}. {v['name']}  {stars}  [{cats}]  {v.get('price', '?')}")

    # Błędy
    if plan.get("errors"):
        print(f"\n⚠️  Uwagi:")
        for e in plan["errors"]:
            print(f"   - {e}")

    print("\n" + "=" * 70)
    print("  Gotowe! Miłej randki! 💝")
    print("=" * 70)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="POV #02: Date Night Planner — Transport + Mapy + Randki"
    )
    parser.add_argument(
        "--origin", default="Gdańsk Wrzeszcz",
        help="Adres startowy (default: Gdańsk Wrzeszcz)"
    )
    parser.add_argument(
        "--destination", default="Gdańsk Śródmieście",
        help="Adres docelowy (default: Gdańsk Śródmieście)"
    )
    parser.add_argument(
        "--budget", type=int, default=2, choices=[1, 2, 3, 4],
        help="Poziom cenowy 1-4 (default: 2)"
    )
    parser.add_argument(
        "--mode", default="DRIVE",
        choices=["DRIVE", "WALK", "BICYCLE", "TRANSIT"],
        help="Środek transportu (default: DRIVE)"
    )
    parser.add_argument(
        "--vibe", default="romantic",
        choices=["romantic", "casual", "fancy", "adventurous"],
        help="Nastrój randki (default: romantic)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Wypisz wynik jako JSON"
    )
    args = parser.parse_args()

    config = Config()

    # W trybie JSON logi idą na stderr, JSON na stdout
    log = sys.stderr if args.json else sys.stdout

    # Sprawdź dostępność API
    print("🔑 Sprawdzanie dostępności API...", file=log)
    apis = {
        "Google Maps": bool(config.google_api_key),
        "Uber": bool(config.uber_client_id),
        "TripAdvisor": bool(config.tripadvisor_api_key),
        "Yelp": bool(config.yelp_api_key),
    }
    for name, available in apis.items():
        status = "✅" if available else "❌ (brak klucza)"
        print(f"  {name}: {status}", file=log)

    if not any(apis.values()):
        print("\n⚠️  Brak kluczy API! Ustaw zmienne środowiskowe:", file=log)
        print("  export GOOGLE_MAPS_API_KEY='...'", file=log)
        print("  export UBER_CLIENT_ID='...'", file=log)
        print("  export UBER_CLIENT_SECRET='...'", file=log)
        print("  export TRIPADVISOR_API_KEY='...'", file=log)
        print("  export YELP_API_KEY='...'", file=log)
        print("\n💡 Demo działa w trybie 'dry-run' — pokazuje strukturę bez API.", file=log)
        print("   Zobacz README.md po instrukcje konfiguracji.", file=log)

    # Planuj
    planner = DateNightPlanner(config)
    plan = planner.plan(
        origin_address=args.origin,
        destination_address=args.destination,
        budget=args.budget,
        travel_mode=args.mode,
        vibe=args.vibe,
        log=log,
    )

    if args.json:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    else:
        print_plan(plan)


if __name__ == "__main__":
    main()
