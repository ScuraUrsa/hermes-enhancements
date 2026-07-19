"""
OpenTable Restaurant Booker — browser automation for Hermes.

Finds restaurants, checks availability, and books tables via OpenTable
using Chrome DevTools Protocol (CDP). No API key required.

Requirements:
    - Chrome/Chromium running with --remote-debugging-port=9222
    - pip install websocket-client (already on hermes-vm)

Usage:
    python opentable_booker.py search "Gdańsk" "italian" 2 "2026-08-01" "19:00"
    python opentable_booker.py availability <restaurant_url> "2026-08-01" "19:00" 2
    python opentable_booker.py details <restaurant_url>
"""

import json
import sys
import time
import argparse
from typing import Any
from urllib.request import urlopen
from urllib.parse import quote

import websocket


class CDPClient:
    """Chrome DevTools Protocol client over WebSocket."""

    def __init__(self, host: str = "localhost", port: int = 9222):
        self.host = host
        self.port = port
        self.ws: websocket.WebSocket | None = None
        self._msg_id = 0
        self._pending: dict[int, dict] = {}

    def connect(self, target_url: str = "about:blank") -> dict:
        """Connect to a Chrome tab via CDP. Returns tab info."""
        resp = urlopen(f"http://{self.host}:{self.port}/json")
        tabs = json.loads(resp.read())

        target = None
        for t in tabs:
            if t.get("type") == "page":
                target = t
                break

        if target is None:
            resp = urlopen(
                __import__("urllib.request").Request(
                    f"http://{self.host}:{self.port}/json/new?{quote(target_url)}",
                    method="PUT",
                )
            )
            target = json.loads(resp.read())

        ws_url = target["webSocketDebuggerUrl"]
        self.ws = websocket.create_connection(ws_url, timeout=10)
        self.ws.settimeout(5)

        # Start reading responses in background
        self._pending = {}
        return target

    def send(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and wait for result."""
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(msg))

        # Read responses until we get our id
        deadline = time.time() + 15.0
        while time.time() < deadline:
            try:
                raw = self.ws.recv()
                if not raw:
                    continue
                resp = json.loads(raw)
                if resp.get("id") == self._msg_id:
                    if "error" in resp:
                        return {"error": resp["error"]}
                    return resp.get("result", {})
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                continue

        return {"error": "timeout"}

    def navigate(self, url: str):
        """Navigate to a URL and wait for load."""
        self.send("Page.enable")
        self.send("Page.navigate", {"url": url})
        time.sleep(3)

    def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript in the page."""
        result = self.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        if "error" in result:
            return None
        return result.get("result", {}).get("value")

    def wait_for_selector(self, selector: str, timeout: float = 10.0) -> bool:
        """Wait for an element to appear."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            found = self.evaluate(f"!!document.querySelector('{selector}')")
            if found:
                return True
            time.sleep(0.5)
        return False

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass


class OpenTableBooker:
    """Search and book restaurants on OpenTable via browser automation."""

    BASE = "https://www.opentable.com"

    def __init__(self, cdp: CDPClient):
        self.cdp = cdp

    def search(
        self,
        location: str,
        cuisine: str | None = None,
        party_size: int = 2,
        date: str = "",
        time_str: str = "19:00",
    ) -> dict:
        """Search restaurants on OpenTable."""
        query = f"Restaurants in {location}"
        if cuisine:
            query = f"{cuisine} {query}"

        url = f"{self.BASE}/s?query={quote(query)}&dateTime={date}T{time_str}&partySize={party_size}"
        self.cdp.navigate(url)

        if not self.cdp.wait_for_selector('[data-test="restaurant-card"], .restaurant-card, [class*="Restaurant"]', timeout=15):
            return {"error": "No results found or page load timeout", "restaurants": []}

        restaurants = self.cdp.evaluate("""
            (() => {
                const cards = document.querySelectorAll(
                    '[data-test="restaurant-card"], [class*="RestaurantCard"], [class*="restaurant-card"]'
                );
                return Array.from(cards).slice(0, 10).map(card => {
                    const name = (card.querySelector('h2, h3, [class*="name"], [class*="Name"]')?.textContent || '').trim();
                    const rating = (card.querySelector('[class*="rating"], [class*="Rating"], [aria-label*="stars"]')?.textContent || '').trim();
                    const cuisine = (card.querySelector('[class*="cuisine"], [class*="Cuisine"]')?.textContent || '').trim();
                    const price = (card.querySelector('[class*="price"], [class*="Price"]')?.textContent || '').trim();
                    const link = card.querySelector('a[href*="/r/"]')?.href || '';
                    return { name, rating, cuisine, price, link };
                }).filter(r => r.name);
            })()
        """)

        return {
            "query": query,
            "date": date,
            "time": time_str,
            "party_size": party_size,
            "restaurants": restaurants or [],
            "count": len(restaurants or []),
        }

    def check_availability(
        self,
        restaurant_url: str,
        date: str,
        time_str: str,
        party_size: int = 2,
    ) -> dict:
        """Check table availability."""
        url = f"{restaurant_url}?dateTime={date}T{time_str}&partySize={party_size}"
        self.cdp.navigate(url)
        time.sleep(3)

        slots = self.cdp.evaluate("""
            (() => {
                const times = document.querySelectorAll(
                    'button[aria-label*="PM"], button[aria-label*="AM"], [data-test="time-slot"], [class*="time-slot"], [class*="TimeSlot"]'
                );
                return Array.from(times).slice(0, 20).map(t =>
                    t.textContent?.trim() || t.getAttribute('aria-label') || ''
                ).filter(Boolean);
            })()
        """)

        has_booking = self.cdp.evaluate(
            "!!document.querySelector('[data-test=\"booking-widget\"], [class*=\"reservation\"], [class*=\"booking\"]')"
        )

        return {
            "restaurant_url": restaurant_url,
            "date": date,
            "time": time_str,
            "party_size": party_size,
            "available_slots": slots or [],
            "bookable": len(slots or []) > 0 or bool(has_booking),
        }

    def get_details(self, restaurant_url: str) -> dict:
        """Get restaurant details."""
        self.cdp.navigate(restaurant_url)
        time.sleep(2)

        details = self.cdp.evaluate("""
            (() => {
                const name = (document.querySelector('h1')?.textContent || '').trim();
                const rating = (document.querySelector('[data-test="rating"], [aria-label*="stars"], [class*="rating"]')?.textContent || '').trim();
                const cuisine = (document.querySelector('[data-test="cuisine"], [class*="cuisine"]')?.textContent || '').trim();
                const price = (document.querySelector('[data-test="price-range"], [class*="price"]')?.textContent || '').trim();
                const address = (document.querySelector('[data-test="address"], [class*="address"]')?.textContent || '').trim();
                const phone = (document.querySelector('[data-test="phone"], [class*="phone"]')?.textContent || '').trim();
                const desc = (document.querySelector('[data-test="description"], [class*="description"]')?.textContent || '').trim().substring(0, 500);
                const photos = Array.from(document.querySelectorAll('img[src*="otstatic.com"], img[src*="opentable"]')).slice(0, 5).map(img => img.src);
                return { name, rating, cuisine, price, address, phone, description: desc, photos };
            })()
        """)

        return details or {"error": "Could not extract details"}


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenTable Restaurant Booker")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("search", help="Search restaurants")
    p.add_argument("location")
    p.add_argument("--cuisine", "-c", default=None)
    p.add_argument("--party", "-p", type=int, default=2)
    p.add_argument("--date", "-d", default="")
    p.add_argument("--time", "-t", default="19:00")

    p = sub.add_parser("availability", help="Check table availability")
    p.add_argument("url")
    p.add_argument("--date", "-d", required=True)
    p.add_argument("--time", "-t", default="19:00")
    p.add_argument("--party", "-p", type=int, default=2)

    p = sub.add_parser("details", help="Get restaurant details")
    p.add_argument("url")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cdp = CDPClient()
    try:
        target = cdp.connect()
        booker = OpenTableBooker(cdp)

        if args.command == "search":
            result = booker.search(args.location, args.cuisine, args.party, args.date, args.time)
        elif args.command == "availability":
            result = booker.check_availability(args.url, args.date, args.time, args.party)
        elif args.command == "details":
            result = booker.get_details(args.url)

        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
    finally:
        cdp.close()


if __name__ == "__main__":
    main()
