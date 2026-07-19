"""
Ticketmaster Discovery API wrapper — events, venues, attractions.

Free tier: 5000 calls/day, 5 RPS. No credit card required.
Register: https://developer.ticketmaster.com/

Usage:
    python ticketmaster_events.py search "Gdańsk" --date 2026-08-01
    python ticketmaster_events.py venue "K1nZbvpB"  # Venue ID
"""

import json
import sys
import os
import argparse
from urllib.request import Request, urlopen
from urllib.parse import urlencode


class TicketmasterAPI:
    """Minimal Ticketmaster Discovery API v2 wrapper."""

    BASE = "https://app.ticketmaster.com/discovery/v2"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get(self, path: str, params: dict) -> dict:
        params["apikey"] = self.api_key
        url = f"{self.BASE}{path}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            return {"error": str(e)}

    def search_events(
        self,
        city: str | None = None,
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        classification: str | None = None,
        size: int = 10,
        page: int = 0,
    ) -> dict:
        """Search events.

        Args:
            city: 'Gdańsk' or 'Gdansk'
            keyword: 'concert', 'festival', 'comedy'
            start_date: YYYY-MM-DDTHH:mm:ssZ
            end_date: YYYY-MM-DDTHH:mm:ssZ
            classification: 'music', 'sports', 'arts', 'film', 'food'
            size: results per page (max 200)
        """
        params: dict = {"size": min(size, 200), "page": page}
        if city:
            params["city"] = city
        if keyword:
            params["keyword"] = keyword
        if start_date:
            params["startDateTime"] = start_date
        if end_date:
            params["endDateTime"] = end_date
        if classification:
            params["classificationName"] = classification

        data = self._get("/events.json", params)
        if "error" in data:
            return data

        events = []
        embedded = data.get("_embedded", {})
        for e in embedded.get("events", []):
            name = e.get("name", "?")
            url = e.get("url", "")
            dates = e.get("dates", {})
            start = dates.get("start", {})

            # Venue
            venues = e.get("_embedded", {}).get("venues", [])
            venue_name = venues[0].get("name", "?") if venues else "?"
            venue_city = venues[0].get("city", {}).get("name", "?") if venues else "?"

            # Price range
            price_ranges = e.get("priceRanges", [])
            price_info = ""
            if price_ranges:
                p = price_ranges[0]
                price_info = f"{p.get('min', '?')}-{p.get('max', '?')} {p.get('currency', '?')}"

            # Classification
            classifications = e.get("classifications", [{}])
            genre = classifications[0].get("genre", {}).get("name", "")
            subgenre = classifications[0].get("subGenre", {}).get("name", "")

            # Image
            images = e.get("images", [])
            image_url = images[0].get("url", "") if images else ""

            events.append({
                "name": name,
                "url": url,
                "date": start.get("localDate", "?"),
                "time": start.get("localTime", "?"),
                "venue": venue_name,
                "city": venue_city,
                "genre": genre,
                "subgenre": subgenre,
                "price": price_info,
                "image": image_url,
            })

        return {
            "events": events,
            "count": len(events),
            "total": data.get("page", {}).get("totalElements", 0),
            "page": data.get("page", {}).get("number", 0),
            "total_pages": data.get("page", {}).get("totalPages", 0),
        }

    def search_venues(self, keyword: str, size: int = 10) -> dict:
        """Search venues by keyword."""
        data = self._get("/venues.json", {"keyword": keyword, "size": size})
        if "error" in data:
            return data

        venues = []
        for v in data.get("_embedded", {}).get("venues", []):
            venues.append({
                "id": v.get("id", ""),
                "name": v.get("name", "?"),
                "city": v.get("city", {}).get("name", "?"),
                "country": v.get("country", {}).get("name", "?"),
                "address": v.get("address", {}).get("line1", "?"),
                "url": v.get("url", ""),
            })

        return {"venues": venues, "count": len(venues)}

    def get_venue(self, venue_id: str) -> dict:
        """Get venue details by ID."""
        data = self._get(f"/venues/{venue_id}.json", {})
        if "error" in data:
            return data

        v = data
        return {
            "id": v.get("id", ""),
            "name": v.get("name", "?"),
            "city": v.get("city", {}).get("name", "?"),
            "country": v.get("country", {}).get("name", "?"),
            "address": v.get("address", {}).get("line1", "?"),
            "postal_code": v.get("postalCode", ""),
            "url": v.get("url", ""),
            "box_office": v.get("boxOfficeInfo", {}).get("phoneNumberDetail", ""),
            "parking": v.get("parkingDetail", ""),
            "accessible": v.get("accessibleSeatingDetail", ""),
        }


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ticketmaster Discovery API")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("search", help="Search events")
    p.add_argument("city", nargs="?", default=None)
    p.add_argument("--keyword", "-k", default=None)
    p.add_argument("--date", "-d", default=None, help="YYYY-MM-DD")
    p.add_argument("--end-date", default=None, help="YYYY-MM-DD")
    p.add_argument("--classification", "-c", default=None,
                   choices=["music", "sports", "arts", "film", "food", "comedy"])
    p.add_argument("--size", "-n", type=int, default=10)

    p = sub.add_parser("venue", help="Get venue details")
    p.add_argument("venue_id")

    p = sub.add_parser("venues", help="Search venues")
    p.add_argument("keyword")

    args = parser.parse_args()
    api_key = os.getenv("TICKETMASTER_API_KEY", "")

    if not api_key:
        print(json.dumps({
            "error": "TICKETMASTER_API_KEY not set. Get one at https://developer.ticketmaster.com/",
            "note": "Free tier: 5000 calls/day, 5 RPS, no credit card required",
        }, indent=2))
        return

    api = TicketmasterAPI(api_key)

    if args.command == "search":
        start = f"{args.date}T00:00:00Z" if args.date else None
        end = f"{args.end_date}T23:59:59Z" if args.end_date else None
        result = api.search_events(
            city=args.city,
            keyword=args.keyword,
            start_date=start,
            end_date=end,
            classification=args.classification,
            size=args.size,
        )
    elif args.command == "venue":
        result = api.get_venue(args.venue_id)
    elif args.command == "venues":
        result = api.search_venues(args.keyword)
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
