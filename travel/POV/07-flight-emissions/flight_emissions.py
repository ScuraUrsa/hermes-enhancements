"""
Google Travel Impact Model (TIM) — flight carbon emissions.

Estimates CO2 emissions per passenger for flights. Same model used
by Google Flights, Booking.com, Skyscanner, and Travelport.

API: Free, no key required. Rate limit: 100 req/min.
Docs: https://developers.google.com/travel/impact-model

Usage:
    python flight_emissions.py GDN BCN  # Gdańsk → Barcelona
    python flight_emissions.py WAW JFK --class premium_economy
"""

import json
import sys
import argparse
from urllib.request import Request, urlopen
from urllib.parse import urlencode


BASE = "https://travelimpactmodel.googleapis.com/v1"


def estimate_emissions(
    origin: str,
    destination: str,
    cabin_class: str = "economy",
) -> dict:
    """Estimate flight emissions per passenger.

    Args:
        origin: IATA airport code (e.g. 'GDN')
        destination: IATA airport code
        cabin_class: 'economy', 'premium_economy', 'business', 'first'

    Returns:
        {
            "route": "GDN→BCN",
            "emissions_kg": 123.4,
            "distance_km": 1800,
            "cabin_class": "economy",
            "comparison": "23% below average for this route"
        }
    """
    params = {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "cabinClass": cabin_class.upper(),
    }
    url = f"{BASE}/flights:estimateEmissions?{urlencode(params)}"

    try:
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

    if "error" in data:
        return data

    emissions = data.get("flightEmissions", [{}])[0]
    grams = emissions.get("emissionsGramsPerPax", {})
    co2_kg = grams.get("co2", 0) / 1000.0

    return {
        "route": f"{origin.upper()}→{destination.upper()}",
        "cabin_class": cabin_class,
        "emissions_kg": round(co2_kg, 1),
        "emissions_grams": grams.get("co2", 0),
        "distance_km": emissions.get("distanceKm", 0),
        "flight_type": emissions.get("flight", {}).get("type", "?"),
        "aircraft": emissions.get("flight", {}).get("aircraft", {}).get("name", "?"),
        "contrail_impact": emissions.get("contrailImpact", "UNKNOWN"),
        "model_version": data.get("modelVersion", {}).get("major", "?"),
    }


def compare_routes(routes: list[tuple[str, str]], cabin_class: str = "economy") -> dict:
    """Compare emissions across multiple routes."""
    results = []
    for origin, dest in routes:
        r = estimate_emissions(origin, dest, cabin_class)
        results.append(r)

    # Sort by emissions
    results.sort(key=lambda x: x.get("emissions_kg", float("inf")))

    return {
        "routes": results,
        "count": len(results),
        "best": results[0] if results else None,
        "worst": results[-1] if results else None,
    }


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Flight carbon emissions estimator (Google TIM)"
    )
    parser.add_argument("origin", help="Origin IATA code (e.g. GDN)")
    parser.add_argument("destination", help="Destination IATA code (e.g. BCN)")
    parser.add_argument(
        "--class", "-c", dest="cabin_class",
        choices=["economy", "premium_economy", "business", "first"],
        default="economy",
    )
    parser.add_argument("--json", "-j", action="store_true", help="Raw JSON output")
    args = parser.parse_args()

    result = estimate_emissions(args.origin, args.destination, args.cabin_class)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    co2 = result["emissions_kg"]
    dist = result["distance_km"]

    # Context: average car emits ~120g CO2/km, train ~14g/km
    car_equiv = co2 / 0.12  # km equivalent by car
    tree_days = co2 / 0.06  # trees absorb ~60g CO2/day

    print(f"✈️  {result['route']} ({result['cabin_class']})")
    print(f"   Distance: {dist} km")
    print(f"   CO₂: {co2} kg per passenger")
    print(f"   Aircraft: {result['aircraft']}")
    print(f"   Contrail impact: {result['contrail_impact']}")
    print()
    print(f"🌍 Context:")
    print(f"   = driving {car_equiv:.0f} km by car")
    print(f"   = {tree_days:.0f} days of one tree's CO₂ absorption")
    print()
    print(f"💡 API: Free, no key required. 100 req/min.")


if __name__ == "__main__":
    main()
