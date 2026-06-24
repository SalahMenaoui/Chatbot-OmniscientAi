# Workflow: scrape_sources

## Objective
Scrape all available online sources for a client and consolidate the data into a single `scraped_data.json` file.

## Inputs Required
- Client name (used as folder name, e.g. `acme_bakery`)
- `clients/<client_name>/sources.txt` — one URL per line, labeled with source type

### sources.txt format
```
website: https://acmebakery.com
instagram: https://www.instagram.com/acmebakery/
tiktok: https://www.tiktok.com/@acmebakery
googlemaps: https://maps.google.com/?cid=12345
```

## Steps

### 1. Read sources.txt
Open `clients/<client_name>/sources.txt` and parse each line.
Skip lines that are empty or start with `#`.

### 2. Scrape each source
Run the relevant tool for each source type found. If a source type is not listed, skip it.

**Website:**
```
python tools/scrape_website.py <website_url> .tmp/website.json
```

**Instagram:**
```
python tools/scrape_instagram.py <instagram_url> .tmp/instagram.json
```

**TikTok:**
```
python tools/scrape_tiktok.py <tiktok_url> .tmp/tiktok.json
```

**Google Maps:**
```
python tools/scrape_googlemaps.py <googlemaps_url> .tmp/googlemaps.json
```

### 3. Handle scraping failures
- If a scraper fails, log the error and continue with the remaining sources.
- A partial scrape is acceptable — do not abort the entire workflow.
- Note any failures in your response so I can manually fill in the gaps.

### 4. Merge all results
```
python tools/merge_scraped_data.py <client_name>
```
This reads all `.tmp/*.json` files and writes `clients/<client_name>/scraped_data.json`.

### 5. Confirm output
- Confirm `clients/<client_name>/scraped_data.json` was created.
- Report which sources were scraped successfully and which failed.
- Flag any fields that look incomplete or suspicious.

## Expected Output
- `clients/<client_name>/scraped_data.json` — merged data from all sources
- `.tmp/` files — intermediate data (disposable)

## Edge Cases
- **Private Instagram/TikTok accounts** — log as unavailable, continue.
- **No Google Maps API key** — log warning, continue with other sources.
- **Website blocked by bot detection** — log warning, note for manual review.
- **Missing sources.txt** — ask for URLs before proceeding.

## Next Step
Once complete, proceed to → `workflows/generate_prompt.md`
