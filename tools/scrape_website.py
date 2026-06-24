"""
scrape_website.py
Scrapes a business website and extracts structured content:
services, prices, contact info, FAQ, about text, tone.

Usage:
    python tools/scrape_website.py <url> <output_json>

Example:
    python tools/scrape_website.py https://example.com .tmp/website.json
"""

import sys
import json
import re
from urllib.parse import urljoin, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

MAX_PAGES   = 10     # Max internal pages to follow
MIN_TEXT_LEN = 50    # Ignore very short text blocks


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_emails(text: str) -> list[str]:
    return list(set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)))


def extract_phones(text: str) -> list[str]:
    return list(set(re.findall(r"\+?[\d\s\-().]{7,20}", text)))


def scrape_page(url: str, session: requests.Session) -> dict:
    """Fetch and parse a single page. Returns structured dict."""
    result = {"url": url, "title": "", "headings": [], "paragraphs": [], "lists": []}
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"  [WARN] Could not fetch {url}: {e}")
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove nav/footer/script/style noise
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
        tag.decompose()

    result["title"] = clean_text(soup.title.string if soup.title else "")

    # Headings
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        t = clean_text(tag.get_text())
        if t:
            result["headings"].append(t)

    # Paragraphs
    for p in soup.find_all("p"):
        t = clean_text(p.get_text())
        if len(t) >= MIN_TEXT_LEN:
            result["paragraphs"].append(t)

    # Lists
    for ul in soup.find_all(["ul", "ol"]):
        items = [clean_text(li.get_text()) for li in ul.find_all("li") if clean_text(li.get_text())]
        if items:
            result["lists"].append(items)

    return result


def discover_links(base_url: str, session: requests.Session, max_pages: int) -> list[str]:
    """BFS on internal links from home page."""
    base_domain = urlparse(base_url).netloc
    visited = {base_url}
    queue   = [base_url]
    pages   = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        pages.append(url)
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = urljoin(base_url, a["href"]).split("#")[0].split("?")[0]
                parsed = urlparse(href)
                if parsed.netloc == base_domain and href not in visited:
                    visited.add(href)
                    queue.append(href)
        except Exception:
            pass

    return pages


def run(url: str, output_path: str) -> None:
    print(f"[scrape_website] Starting: {url}")
    session = requests.Session()

    pages_to_scrape = discover_links(url, session, MAX_PAGES)
    print(f"[scrape_website] Found {len(pages_to_scrape)} page(s) to scrape.")

    all_pages = []
    all_text  = []

    for page_url in pages_to_scrape:
        print(f"  Scraping: {page_url}")
        data = scrape_page(page_url, session)
        all_pages.append(data)
        all_text.append(" ".join(data["headings"] + data["paragraphs"]))

    full_text = " ".join(all_text)

    output = {
        "source_type": "website",
        "base_url": url,
        "pages_scraped": len(all_pages),
        "pages": all_pages,
        "extracted": {
            "emails": extract_emails(full_text),
            "phones": extract_phones(full_text),
        },
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[scrape_website] Done. Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        # Legacy: python tools/scrape_website.py <url> <output_json>
        run(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        # New: python tools/scrape_website.py <url>  → saves to .tmp/website.json
        import os; os.makedirs(".tmp", exist_ok=True)
        run(sys.argv[1], ".tmp/website.json")
    else:
        print("Usage: python tools/scrape_website.py <url> [output_json]")
        sys.exit(1)
