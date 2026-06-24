"""
merge_scraped_data.py
Merges all individual scraped JSON files from .tmp/ into a single
clients/<client_name>/scraped_data.json.

Called automatically at the end of scrape_sources workflow.

Usage:
    python tools/merge_scraped_data.py <client_name>

Example:
    python tools/merge_scraped_data.py acme_bakery

Reads:   .tmp/website.json, .tmp/instagram.json, .tmp/tiktok.json, .tmp/googlemaps.json
         (only files that exist are included)

Writes:  clients/<client_name>/scraped_data.json
"""

import sys
import json
import os
from datetime import datetime


SOURCE_FILES = {
    "website":      ".tmp/website.json",
    "instagram":    ".tmp/instagram.json",
    "tiktok":       ".tmp/tiktok.json",
    "google_maps":  ".tmp/googlemaps.json",
    "dm_responses": ".tmp/dm_responses.json",
}


def run(client_name: str) -> None:
    client_dir  = os.path.join("clients", client_name)
    output_path = os.path.join(client_dir, "scraped_data.json")

    os.makedirs(client_dir, exist_ok=True)

    merged = {
        "client":    client_name,
        "scraped_at": datetime.utcnow().isoformat(),
        "sources":   [],
    }

    for key, path in SOURCE_FILES.items():
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged[key] = data
            merged["sources"].append(key)
            print(f"[merge_scraped_data] Merged: {path}")
        else:
            print(f"[merge_scraped_data] Skipped (not found): {path}")

    if not merged["sources"]:
        print("ERROR: No scraped data files found in .tmp/. Run scrapers first.")
        sys.exit(1)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[merge_scraped_data] Done. Merged {len(merged['sources'])} source(s) -> {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/merge_scraped_data.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
