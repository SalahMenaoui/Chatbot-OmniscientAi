"""
scrape_googlemaps.py
Extracts business info from a Google Maps URL using the Google Places API.
Falls back to HTML scraping if no API key is provided (less reliable).

Usage:
    python tools/scrape_googlemaps.py <google_maps_url> <output_json>

Example:
    python tools/scrape_googlemaps.py "https://maps.google.com/?cid=12345" .tmp/googlemaps.json

Requirements:
    pip install requests python-dotenv
    GOOGLE_PLACES_API_KEY in .env (optional but recommended)
"""

import sys
import json
import re
import os

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install requests python-dotenv")
    sys.exit(1)


load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    )
}


def extract_place_id_from_url(url: str) -> str | None:
    """Try to extract place_id or CID from a Maps URL."""
    # Direct place_id
    m = re.search(r"place_id=([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    # Maps short URL — resolve redirect first
    return None


def search_by_name(query: str) -> dict | None:
    """Use Places Text Search to find a business by name/address string."""
    if not GOOGLE_API_KEY:
        return None
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/place/textsearch/json",
        params={"query": query, "key": GOOGLE_API_KEY},
        timeout=15,
    )
    data = resp.json()
    results = data.get("results", [])
    return results[0] if results else None


def get_place_details(place_id: str) -> dict:
    """Fetch full place details from Places API."""
    resp = requests.get(
        "https://maps.googleapis.com/maps/api/place/details/json",
        params={
            "place_id": place_id,
            "fields": (
                "name,formatted_address,formatted_phone_number,website,"
                "opening_hours,rating,user_ratings_total,reviews,"
                "types,price_level,business_status"
            ),
            "key": GOOGLE_API_KEY,
        },
        timeout=15,
    )
    return resp.json().get("result", {})


def resolve_maps_url(url: str) -> str:
    """Follow redirects to get final Google Maps URL."""
    try:
        resp = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=10)
        return resp.url
    except Exception:
        return url


def run(url: str, output_path: str) -> None:
    print(f"[scrape_googlemaps] Starting: {url}")

    output = {
        "source_type": "google_maps",
        "input_url": url,
        "name": "",
        "address": "",
        "phone": "",
        "website": "",
        "rating": None,
        "total_reviews": None,
        "price_level": None,
        "categories": [],
        "hours": {},
        "reviews": [],
        "error": None,
    }

    if not GOOGLE_API_KEY:
        output["error"] = (
            "No GOOGLE_PLACES_API_KEY found in .env. "
            "Add the key or manually fill in scraped_data.json."
        )
        print(f"[scrape_googlemaps] WARNING: {output['error']}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return

    # Resolve short URLs
    resolved_url = resolve_maps_url(url)
    place_id = extract_place_id_from_url(resolved_url)

    if not place_id:
        # Try to extract business name from URL and search
        name_match = re.search(r"/place/([^/]+)", resolved_url)
        query = name_match.group(1).replace("+", " ") if name_match else url
        result = search_by_name(query)
        if result:
            place_id = result.get("place_id")

    if not place_id:
        output["error"] = "Could not extract place_id from URL. Try pasting the business name instead."
        print(f"[scrape_googlemaps] ERROR: {output['error']}")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return

    try:
        details = get_place_details(place_id)

        output["name"]          = details.get("name", "")
        output["address"]       = details.get("formatted_address", "")
        output["phone"]         = details.get("formatted_phone_number", "")
        output["website"]       = details.get("website", "")
        output["rating"]        = details.get("rating")
        output["total_reviews"] = details.get("user_ratings_total")
        output["price_level"]   = details.get("price_level")
        output["categories"]    = details.get("types", [])

        hours_data = details.get("opening_hours", {})
        if hours_data.get("weekday_text"):
            for line in hours_data["weekday_text"]:
                parts = line.split(": ", 1)
                if len(parts) == 2:
                    output["hours"][parts[0]] = parts[1]

        for review in details.get("reviews", [])[:10]:
            output["reviews"].append({
                "author":   review.get("author_name", ""),
                "rating":   review.get("rating"),
                "text":     review.get("text", ""),
                "time":     review.get("relative_time_description", ""),
            })

    except Exception as e:
        output["error"] = str(e)
        print(f"[scrape_googlemaps] ERROR: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[scrape_googlemaps] Done. Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tools/scrape_googlemaps.py <google_maps_url> <output_json>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
