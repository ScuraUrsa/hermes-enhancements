"""
Travel MCP Server for Hermes — flights, hotels, restaurants, events, weather.

Usage:
    python travel_mcp_server.py

Requires API keys in environment:
    AMADEUS_API_KEY, AMADEUS_API_SECRET  (flight/hotel search)
    GOOGLE_PLACES_API_KEY                (restaurants, venues)
    EVENTBRITE_API_KEY                   (events)
    OPENWEATHERMAP_API_KEY               (weather)
"""

import os
import json
import sys
from datetime import datetime, timedelta
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import URLError


# ── API Helpers ────────────────────────────────────────────────────────

def _get(url: str, headers: dict | None = None) -> dict:
    """GET request with error handling."""
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except URLError as e:
        return {"error": str(e)}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response"}


# ── Amadeus Flight Search ──────────────────────────────────────────────

class AmadeusAPI:
    """Wrapper for Amadeus Self-Service APIs (test environment)."""

    BASE = "https://test.api.amadeus.com"

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self._token: str | None = None
        self._token_expiry: datetime | None = None

    def _auth(self) -> str:
        """Get OAuth2 token (cached)."""
        if self._token and self._token_expiry and datetime.now() < self._token_expiry:
            return self._token

        data = urlencode({
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret,
        }).encode()
        req = Request(f"{self.BASE}/v1/security/oauth2/token", data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
        self._token = result["access_token"]
        self._token_expiry = datetime.now() + timedelta(seconds=result.get("expires_in", 1800) - 60)
        return self._token

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        max_results: int = 5,
    ) -> dict:
        """Search flights via Amadeus Flight Offers Search.

        Args:
            origin: IATA code (e.g. 'GDN' for Gdańsk)
            destination: IATA code
            departure_date: YYYY-MM-DD
            return_date: YYYY-MM-DD (None = one-way)
            adults: number of passengers
            max_results: max offers to return
        """
        token = self._auth()
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "max": max_results,
        }
        if return_date:
            params["returnDate"] = return_date

        url = f"{self.BASE}/v2/shopping/flight-offers?{urlencode(params)}"
        headers = {"Authorization": f"Bearer {token}"}
        data = _get(url, headers)

        if "error" in data:
            return data

        # Simplify response
        offers = []
        for offer in data.get("data", []):
            itinerary = offer.get("itineraries", [{}])[0]
            segments = itinerary.get("segments", [])
            price = offer.get("price", {})
            offers.append({
                "price": f"{price.get('total', '?')} {price.get('currency', '?')}",
                "segments": [
                    {
                        "from": s.get("departure", {}).get("iataCode", "?"),
                        "to": s.get("arrival", {}).get("iataCode", "?"),
                        "departure": s.get("departure", {}).get("at", "?"),
                        "arrival": s.get("arrival", {}).get("at", "?"),
                        "airline": s.get("carrierCode", "?"),
                        "flight_number": s.get("number", "?"),
                    }
                    for s in segments
                ],
            })
        return {"offers": offers, "count": len(offers)}


# ── Google Places (Restaurants, Venues) ────────────────────────────────

class GooglePlacesAPI:
    """Wrapper for Google Places API (New)."""

    BASE = "https://places.googleapis.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_restaurants(
        self,
        location: str,
        radius_m: int = 2000,
        cuisine: str | None = None,
        max_price: int | None = None,
        min_rating: float = 4.0,
        max_results: int = 10,
    ) -> dict:
        """Search for restaurants near a location.

        Args:
            location: 'Gdańsk, Poland' or '54.3520,18.6466'
            radius_m: search radius in meters
            cuisine: optional cuisine filter (e.g. 'italian', 'polish')
            max_price: 1-4 price level
            min_rating: minimum Google rating (1-5)
            max_results: max places to return
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,places.rating,"
                "places.userRatingCount,places.priceLevel,places.types,"
                "places.websiteUri,places.googleMapsUri,"
                "places.regularOpeningHours,places.photos"
            ),
        }

        # Text search
        query = f"restaurant in {location}"
        if cuisine:
            query = f"{cuisine} restaurant in {location}"

        body = {
            "textQuery": query,
            "maxResultCount": max_results,
            "minRating": min_rating,
        }
        if max_price:
            body["priceLevels"] = [f"PRICE_LEVEL_{'MODERATE' if max_price <= 2 else 'EXPENSIVE'}"]

        req = Request(
            f"{self.BASE}/places:searchText",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except URLError as e:
            return {"error": str(e)}

        places = []
        for p in data.get("places", []):
            name = p.get("displayName", {}).get("text", "?")
            addr = p.get("formattedAddress", "?")
            rating = p.get("rating", "?")
            reviews = p.get("userRatingCount", 0)
            price = p.get("priceLevel", "?")
            website = p.get("websiteUri", "")
            maps = p.get("googleMapsUri", "")

            # Opening hours
            hours = p.get("regularOpeningHours", {})
            open_now = hours.get("openNow", False)

            # First photo
            photo_url = ""
            photos = p.get("photos", [])
            if photos:
                photo_name = photos[0].get("name", "")
                photo_url = (
                    f"https://places.googleapis.com/v1/{photo_name}/media"
                    f"?key={self.api_key}&maxWidthPx=400"
                )

            places.append({
                "name": name,
                "address": addr,
                "rating": rating,
                "reviews": reviews,
                "price_level": price,
                "open_now": open_now,
                "website": website,
                "maps": maps,
                "photo": photo_url,
            })

        return {"places": places, "count": len(places)}

    def search_venues(
        self,
        location: str,
        venue_type: str = "bar",
        max_results: int = 10,
    ) -> dict:
        """Search for bars, clubs, cafes, or other venues.

        Args:
            location: 'Gdańsk, Poland'
            venue_type: 'bar', 'cafe', 'night_club', 'park', 'museum', etc.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,places.rating,"
                "places.userRatingCount,places.priceLevel,places.websiteUri,"
                "places.googleMapsUri,places.regularOpeningHours"
            ),
        }

        body = {
            "textQuery": f"{venue_type} in {location}",
            "maxResultCount": max_results,
        }

        req = Request(
            f"{self.BASE}/places:searchText",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except URLError as e:
            return {"error": str(e)}

        places = []
        for p in data.get("places", []):
            places.append({
                "name": p.get("displayName", {}).get("text", "?"),
                "address": p.get("formattedAddress", "?"),
                "rating": p.get("rating", "?"),
                "reviews": p.get("userRatingCount", 0),
                "price_level": p.get("priceLevel", "?"),
                "open_now": p.get("regularOpeningHours", {}).get("openNow", False),
                "website": p.get("websiteUri", ""),
                "maps": p.get("googleMapsUri", ""),
            })

        return {"places": places, "count": len(places)}


# ── Eventbrite Events ──────────────────────────────────────────────────

class EventbriteAPI:
    """Wrapper for Eventbrite API v3."""

    BASE = "https://www.eventbriteapi.com/v3"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search_events(
        self,
        location: str,
        start_date: str | None = None,
        end_date: str | None = None,
        categories: str | None = None,
        max_results: int = 10,
    ) -> dict:
        """Search events on Eventbrite.

        Args:
            location: 'Gdańsk' or '54.3520,18.6466'
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            categories: comma-separated category IDs
                (103 = music, 101 = business, 102 = food, 104 = film,
                 105 = sports, 106 = health, 107 = art, 108 = fashion,
                 109 = home, 110 = auto, 111 = hobby, 112 = other,
                 113 = school, 114 = religion, 115 = science, 116 = travel,
                 117 = charity, 118 = government, 119 = spirituality)
        """
        params: dict[str, Any] = {
            "location.address": location,
            "expand": "venue",
            "page_size": max_results,
        }
        if start_date:
            params["start_date.range_start"] = f"{start_date}T00:00:00Z"
        if end_date:
            params["start_date.range_end"] = f"{end_date}T23:59:59Z"
        if categories:
            params["categories"] = categories

        url = f"{self.BASE}/events/search/?{urlencode(params)}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = _get(url, headers)

        if "error" in data:
            return data

        events = []
        for e in data.get("events", []):
            name = e.get("name", {}).get("text", "?")
            desc = e.get("description", {}).get("text", "")[:200]
            url_event = e.get("url", "")
            start = e.get("start", {}).get("local", "?")
            end = e.get("end", {}).get("local", "?")
            is_free = e.get("is_free", False)

            venue = e.get("venue", {}) or {}
            venue_name = venue.get("name", "?")
            venue_addr = venue.get("address", {}).get("localized_address_display", "?")

            events.append({
                "name": name,
                "description": desc,
                "url": url_event,
                "start": start,
                "end": end,
                "free": is_free,
                "venue": venue_name,
                "venue_address": venue_addr,
            })

        return {"events": events, "count": len(events)}


# ── Weather ────────────────────────────────────────────────────────────

class WeatherAPI:
    """Wrapper for OpenWeatherMap."""

    BASE = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_forecast(self, city: str, days: int = 5) -> dict:
        """Get weather forecast for a city.

        Args:
            city: 'Gdańsk' or 'Gdansk,PL'
            days: 1-5 days forecast
        """
        params = {
            "q": city,
            "appid": self.api_key,
            "units": "metric",
            "cnt": min(days * 8, 40),  # 3-hour intervals
        }
        url = f"{self.BASE}/forecast?{urlencode(params)}"
        data = _get(url)

        if "error" in data:
            return data

        forecasts = []
        for item in data.get("list", []):
            forecasts.append({
                "time": item.get("dt_txt", "?"),
                "temp": item.get("main", {}).get("temp", "?"),
                "feels_like": item.get("main", {}).get("feels_like", "?"),
                "description": item.get("weather", [{}])[0].get("description", "?"),
                "humidity": item.get("main", {}).get("humidity", "?"),
                "wind_speed": item.get("wind", {}).get("speed", "?"),
            })

        return {
            "city": data.get("city", {}).get("name", city),
            "country": data.get("city", {}).get("country", ""),
            "forecasts": forecasts,
        }


# ── MCP Server ─────────────────────────────────────────────────────────

def handle_request(request: dict) -> dict:
    """Handle an MCP tool call request.

    Expected format:
    {
        "method": "tools/call",
        "params": {
            "name": "search_flights",
            "arguments": {
                "origin": "GDN",
                "destination": "WAW",
                "departure_date": "2026-08-01"
            }
        }
    }
    """
    method = request.get("method", "")
    params = request.get("params", {})
    tool_name = params.get("name", "")
    args = params.get("arguments", {})

    # Lazy init APIs
    amadeus = None
    if os.getenv("AMADEUS_API_KEY"):
        amadeus = AmadeusAPI(
            os.getenv("AMADEUS_API_KEY", ""),
            os.getenv("AMADEUS_API_SECRET", ""),
        )

    places = None
    if os.getenv("GOOGLE_PLACES_API_KEY"):
        places = GooglePlacesAPI(os.getenv("GOOGLE_PLACES_API_KEY", ""))

    eventbrite = None
    if os.getenv("EVENTBRITE_API_KEY"):
        eventbrite = EventbriteAPI(os.getenv("EVENTBRITE_API_KEY", ""))

    weather = None
    if os.getenv("OPENWEATHERMAP_API_KEY"):
        weather = WeatherAPI(os.getenv("OPENWEATHERMAP_API_KEY", ""))

    # Route to tool
    if tool_name == "search_flights":
        if not amadeus:
            return {"error": "AMADEUS_API_KEY not configured"}
        return amadeus.search_flights(
            origin=args.get("origin", ""),
            destination=args.get("destination", ""),
            departure_date=args.get("departure_date", ""),
            return_date=args.get("return_date"),
            adults=args.get("adults", 1),
            max_results=args.get("max_results", 5),
        )

    elif tool_name == "search_restaurants":
        if not places:
            return {"error": "GOOGLE_PLACES_API_KEY not configured"}
        return places.search_restaurants(
            location=args.get("location", ""),
            radius_m=args.get("radius_m", 2000),
            cuisine=args.get("cuisine"),
            max_price=args.get("max_price"),
            min_rating=args.get("min_rating", 4.0),
            max_results=args.get("max_results", 10),
        )

    elif tool_name == "search_venues":
        if not places:
            return {"error": "GOOGLE_PLACES_API_KEY not configured"}
        return places.search_venues(
            location=args.get("location", ""),
            venue_type=args.get("venue_type", "bar"),
            max_results=args.get("max_results", 10),
        )

    elif tool_name == "search_events":
        if not eventbrite:
            return {"error": "EVENTBRITE_API_KEY not configured"}
        return eventbrite.search_events(
            location=args.get("location", ""),
            start_date=args.get("start_date"),
            end_date=args.get("end_date"),
            categories=args.get("categories"),
            max_results=args.get("max_results", 10),
        )

    elif tool_name == "get_weather":
        if not weather:
            return {"error": "OPENWEATHERMAP_API_KEY not configured"}
        return weather.get_forecast(
            city=args.get("city", ""),
            days=args.get("days", 5),
        )

    elif tool_name == "list_tools":
        return {
            "tools": [
                {
                    "name": "search_flights",
                    "description": "Search flights between two airports. Requires AMADEUS_API_KEY.",
                    "parameters": {
                        "origin": "IATA code (e.g. GDN)",
                        "destination": "IATA code (e.g. WAW)",
                        "departure_date": "YYYY-MM-DD",
                        "return_date": "YYYY-MM-DD (optional)",
                        "adults": "int (default 1)",
                        "max_results": "int (default 5)",
                    },
                },
                {
                    "name": "search_restaurants",
                    "description": "Search restaurants near a location. Requires GOOGLE_PLACES_API_KEY.",
                    "parameters": {
                        "location": "City name or lat,lng",
                        "cuisine": "e.g. italian, polish (optional)",
                        "max_price": "1-4 (optional)",
                        "min_rating": "1-5 (default 4.0)",
                        "max_results": "int (default 10)",
                    },
                },
                {
                    "name": "search_venues",
                    "description": "Search bars, clubs, cafes, parks. Requires GOOGLE_PLACES_API_KEY.",
                    "parameters": {
                        "location": "City name or lat,lng",
                        "venue_type": "bar, cafe, night_club, park, museum...",
                        "max_results": "int (default 10)",
                    },
                },
                {
                    "name": "search_events",
                    "description": "Search events on Eventbrite. Requires EVENTBRITE_API_KEY.",
                    "parameters": {
                        "location": "City name",
                        "start_date": "YYYY-MM-DD (optional)",
                        "end_date": "YYYY-MM-DD (optional)",
                        "categories": "comma-separated IDs (optional)",
                        "max_results": "int (default 10)",
                    },
                },
                {
                    "name": "get_weather",
                    "description": "Get weather forecast. Requires OPENWEATHERMAP_API_KEY.",
                    "parameters": {
                        "city": "City name (e.g. Gdańsk)",
                        "days": "1-5 (default 5)",
                    },
                },
            ]
        }

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ── CLI ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Read JSON request from stdin (MCP stdio protocol)
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            # Demo mode — show available tools
            print(json.dumps(handle_request({
                "method": "tools/list",
                "params": {"name": "list_tools", "arguments": {}},
            }), indent=2))
        else:
            request = json.loads(raw)
            response = handle_request(request)
            print(json.dumps(response, indent=2))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
