"""
scraper.py — Multi-source scraper + AI config generator.
Called from admin.py POST /admin/api/scrape.
"""
import os, re, json, base64
from io import BytesIO


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OmniscientBot/1.0)"}

TRIVIAL_COLORS = {
    '#ffffff','#000000','#111111','#1a1a1a','#222222','#333333','#444444',
    '#555555','#666666','#777777','#888888','#999999','#aaaaaa','#bbbbbb',
    '#cccccc','#dddddd','#eeeeee','#f0f0f0','#f5f5f5','#fafafa','#e5e5e5',
    '#d4d4d4','#0a0a0a','#404040',
}


def _clean(t):
    return re.sub(r"\s+", " ", t).strip()


# ── Website ────────────────────────────────────────────────────────────────────

def scrape_website(url: str) -> dict:
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse
    from collections import Counter

    session = requests.Session()
    domain  = urlparse(url).netloc
    visited = {url}
    queue   = [url]
    pages   = []
    raw_html_first = ""

    while queue and len(pages) < 8:
        u = queue.pop(0)
        try:
            r = session.get(u, headers=HEADERS, timeout=12)
            r.raise_for_status()
            html = r.text
            if not raw_html_first:
                raw_html_first = html

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script","style","nav","footer","header","noscript","iframe"]):
                tag.decompose()

            title    = _clean(soup.title.string) if soup.title else ""
            headings = [_clean(h.get_text()) for h in soup.find_all(["h1","h2","h3"]) if _clean(h.get_text())]
            paras    = [_clean(p.get_text()) for p in soup.find_all("p") if len(_clean(p.get_text())) > 40]

            og_image  = (soup.find("meta", attrs={"property": "og:image"}) or {}).get("content","")
            meta_desc = (
                soup.find("meta", attrs={"name":"description"}) or
                soup.find("meta", attrs={"property":"og:description"}) or {}
            ).get("content","")

            pages.append({"url": u, "title": title, "meta_desc": meta_desc,
                          "og_image": og_image, "headings": headings[:20], "paras": paras[:30]})

            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"]).split("#")[0].split("?")[0]
                if urlparse(href).netloc == domain and href not in visited:
                    visited.add(href); queue.append(href)
        except Exception:
            pass

    # Extract colors from first page CSS
    colors = []
    if raw_html_first:
        hex_raw    = re.findall(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b', raw_html_first)
        normalized = ['#' + (c[0]*2+c[1]*2+c[2]*2 if len(c)==3 else c).lower() for c in hex_raw]
        filtered   = [c for c in normalized if c not in TRIVIAL_COLORS]
        colors     = [c for c,_ in Counter(filtered).most_common(8)]

    fonts_url = ""
    if raw_html_first:
        m = re.findall(r'https://fonts\.googleapis\.com/css[^\s"\'<>]+', raw_html_first)
        if m: fonts_url = m[0]

    full_text = " ".join(str(p.get("paras",[])) for p in pages)
    emails    = list(set(re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", full_text)))[:5]
    phones    = list(set(re.findall(r"\+?[\d\s\-().]{7,20}", full_text)))[:5]
    og_image  = next((p["og_image"] for p in pages if p.get("og_image")), "")

    return {
        "base_url":      url,
        "pages_scraped": len(pages),
        "pages":         [{"title": p["title"], "meta_desc": p["meta_desc"],
                           "headings": p["headings"], "paras": p["paras"]} for p in pages],
        "og_image":      og_image,
        "colors":        colors,
        "fonts_url":     fonts_url,
        "emails":        emails,
        "phones":        phones,
    }


# ── Instagram ──────────────────────────────────────────────────────────────────

def scrape_instagram(url_or_handle: str) -> dict:
    try:
        import instaloader
        m        = re.search(r"instagram\.com/([^/?#]+)", url_or_handle)
        username = m.group(1).strip("/") if m else url_or_handle.strip().strip("@")

        L = instaloader.Instaloader(
            download_pictures=False, download_videos=False,
            download_video_thumbnails=False, download_geotags=False,
            download_comments=False, save_metadata=False,
            quiet=True, max_connection_attempts=1,
        )
        profile = instaloader.Profile.from_username(L.context, username)

        posts = []
        for post in profile.get_posts():
            if len(posts) >= 15: break
            posts.append({
                "caption":  (post.caption or "")[:300],
                "hashtags": list(post.caption_hashtags) if post.caption_hashtags else [],
            })

        return {
            "username":        username,
            "full_name":       profile.full_name or "",
            "bio":             profile.biography or "",
            "followers":       profile.followers,
            "profile_pic_url": profile.profile_pic_url,
            "recent_posts":    posts,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Google Maps ────────────────────────────────────────────────────────────────

def scrape_googlemaps(url: str) -> dict:
    import requests
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return {"error": "GOOGLE_PLACES_API_KEY manquante — ajoutez-la dans Railway"}

    try:
        resolved = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=10).url
    except Exception:
        resolved = url

    place_id = None
    m = re.search(r"place_id=([A-Za-z0-9_-]+)", resolved)
    if m: place_id = m.group(1)

    if not place_id:
        m = re.search(r"/place/([^/]+)", resolved)
        query  = m.group(1).replace("+", " ") if m else url
        try:
            r = requests.get("https://maps.googleapis.com/maps/api/place/textsearch/json",
                             params={"query": query, "key": api_key}, timeout=10)
            results = r.json().get("results", [])
            if results: place_id = results[0].get("place_id")
        except Exception:
            pass

    if not place_id:
        return {"error": "Impossible d'extraire le place_id de cette URL"}

    try:
        r = requests.get("https://maps.googleapis.com/maps/api/place/details/json",
                         params={"place_id": place_id,
                                 "fields": "name,formatted_address,formatted_phone_number,website,opening_hours,rating,user_ratings_total,reviews",
                                 "key": api_key}, timeout=10)
        d = r.json().get("result", {})
        hours = {}
        for line in (d.get("opening_hours") or {}).get("weekday_text", []):
            parts = line.split(": ", 1)
            if len(parts) == 2: hours[parts[0]] = parts[1]
        reviews = [{"author": rv.get("author_name",""), "rating": rv.get("rating"),
                    "text": (rv.get("text",""))[:200]}
                   for rv in d.get("reviews",[])[:5]]
        return {
            "name": d.get("name",""), "address": d.get("formatted_address",""),
            "phone": d.get("formatted_phone_number",""), "website": d.get("website",""),
            "rating": d.get("rating"), "total_reviews": d.get("user_ratings_total"),
            "hours": hours, "reviews": reviews,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Logo download ──────────────────────────────────────────────────────────────

def download_logo(website_url: str, instagram_data: dict) -> str | None:
    """Download best logo, return base64 PNG string or None."""
    import urllib.request

    def fetch(url):
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read()

    def to_b64(data: bytes) -> str | None:
        try:
            from PIL import Image
            img = Image.open(BytesIO(data))
            img.thumbnail((128, 128), Image.LANCZOS)
            if img.mode in ("RGBA", "LA"):
                bg = Image.new("RGBA", img.size, (255,255,255,255))
                bg.paste(img, mask=img.split()[-1])
                img = bg.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, "PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except Exception:
            return None

    candidates = []

    # Instagram profile pic (best quality for avatar)
    if instagram_data and not instagram_data.get("error") and instagram_data.get("profile_pic_url"):
        candidates.append(instagram_data["profile_pic_url"])

    # Website: apple-touch-icon, og:image, favicon
    if website_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(website_url)
            base   = f"{parsed.scheme}://{parsed.netloc}"
            html   = fetch(website_url).decode("utf-8", errors="ignore")

            for m in re.finditer(
                r'<link[^>]+rel=["\']apple-touch-icon[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
                html, re.I
            ):
                href = m.group(1)
                if not href.startswith("http"): href = base + "/" + href.lstrip("/")
                candidates.append(href)

            m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html)
            if m: candidates.append(m.group(1))

            for fav in [f"{base}/apple-touch-icon.png", f"{base}/favicon.ico", f"{base}/favicon.png"]:
                candidates.append(fav)
        except Exception:
            pass

    for url in candidates:
        try:
            data = fetch(url)
            if len(data) < 200: continue
            b64 = to_b64(data)
            if b64: return b64
        except Exception:
            continue

    return None


# ── Claude: generate full config ───────────────────────────────────────────────

def generate_config(website_data: dict, instagram_data: dict, googlemaps_data: dict) -> dict:
    import anthropic as _anthropic

    parts = []

    # Website
    pages = website_data.get("pages", [])
    if pages:
        parts.append(f"SITE WEB ({website_data.get('base_url','')}):")
        parts.append(f"Titre: {pages[0].get('title','')}")
        if pages[0].get("meta_desc"): parts.append(f"Description: {pages[0]['meta_desc']}")
        for p in pages[:6]:
            parts.extend(p.get("headings", [])[:8])
            parts.extend(p.get("paras", [])[:8])
    if website_data.get("colors"):
        parts.append(f"Couleurs CSS détectées sur le site: {', '.join(website_data['colors'])}")
    if website_data.get("fonts_url"):
        parts.append(f"Google Fonts URL du site: {website_data['fonts_url']}")
    if website_data.get("emails"):
        parts.append(f"Emails: {', '.join(website_data['emails'])}")
    if website_data.get("phones"):
        parts.append(f"Téléphones: {', '.join(website_data['phones'])}")

    # Instagram
    if instagram_data and not instagram_data.get("error"):
        parts.append(f"\nINSTAGRAM (@{instagram_data.get('username','')}):")
        if instagram_data.get("full_name"): parts.append(f"Nom: {instagram_data['full_name']}")
        if instagram_data.get("bio"):       parts.append(f"Bio: {instagram_data['bio']}")
        if instagram_data.get("followers"): parts.append(f"Abonnés: {instagram_data['followers']}")
        captions = [p["caption"] for p in instagram_data.get("recent_posts",[])[:5] if p.get("caption")]
        if captions: parts.append(f"Captions récentes: {' | '.join(captions)}")

    # Google Maps
    if googlemaps_data and not googlemaps_data.get("error") and googlemaps_data.get("name"):
        gm = googlemaps_data
        parts.append(f"\nGOOGLE MAPS: {gm.get('name','')}")
        if gm.get("address"):  parts.append(f"Adresse: {gm['address']}")
        if gm.get("phone"):    parts.append(f"Téléphone: {gm['phone']}")
        if gm.get("rating"):   parts.append(f"Note: {gm['rating']}/5 ({gm.get('total_reviews','')} avis)")
        if gm.get("hours"):
            parts.append("Horaires: " + ", ".join(f"{k}: {v}" for k,v in list(gm["hours"].items())[:7]))
        for rv in gm.get("reviews",[])[:3]:
            parts.append(f"Avis: \"{rv.get('text','')}\"")

    context = "\n".join(parts)[:50_000]

    prompt = f"""Tu es un expert en branding et configuration de chatbots.

Données récupérées pour une entreprise:
---
{context}
---

Génère un JSON valide avec EXACTEMENT ces clés (aucun markdown, JSON brut uniquement):
{{
  "botName": "Nom court du bot (ex: Assistant Plombier Expert)",
  "systemPrompt": "System prompt complet et détaillé. Inclure: identité du bot, tous les services avec prix si disponibles, horaires, contact, ton de la marque, quoi faire si inconnu. Langue = langue du site.",
  "welcomeMessage": "Message de bienvenue chaleureux 1-2 phrases. Même langue que le site.",
  "quickReplies": ["Bouton 1", "Bouton 2", "Bouton 3", "Bouton 4"],
  "placeholder": "Placeholder de la zone de texte. Même langue.",
  "avatarInitial": "Première lettre du nom de l'entreprise",
  "colorHeaderBg": "#xxxxxx",
  "colorPrimary": "#xxxxxx",
  "colorPrimaryDark": "#xxxxxx",
  "colorPrimaryContrast": "#ffffff ou #000000",
  "colorBg": "#ffffff",
  "colorSurface": "#f8f8f8",
  "colorBotBubble": "#f0f0f0",
  "colorBotText": "#1a1a1a",
  "colorUserBubble": "même que colorPrimary",
  "colorUserText": "même que colorPrimaryContrast",
  "colorHeaderText": "#ffffff ou #000000",
  "colorHeaderSubtext": "rgba(255,255,255,0.75)",
  "fontFamily": "'Nom Font', sans-serif",
  "googleFontsUrl": "https://fonts.googleapis.com/css2?family=...&display=swap",
  "radiusBubble": "18px",
  "radiusInput": "12px",
  "radiusSend": "10px"
}}

Règles:
- colorPrimary = couleur dominante de la marque. Utilise les couleurs détectées du site comme base.
- colorPrimaryContrast = blanc (#fff) si primary est foncé, noir (#000) si primary est clair
- colorUserBubble = colorPrimary, colorUserText = colorPrimaryContrast
- Choisis une Google Font qui correspond à la personnalité de la marque
- Si site en français → tout en français. Si en anglais → tout en anglais."""

    client = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return json.loads(raw)


# ── Main entry point ───────────────────────────────────────────────────────────

def run(website_url: str, instagram_url: str = "", googlemaps_url: str = "") -> dict:
    errors = {}

    website_data = {}
    if website_url:
        try:
            website_data = scrape_website(website_url)
        except Exception as e:
            errors["website"] = str(e)

    instagram_data = {}
    if instagram_url:
        instagram_data = scrape_instagram(instagram_url)
        if instagram_data.get("error"):
            errors["instagram"] = instagram_data["error"]

    googlemaps_data = {}
    if googlemaps_url:
        googlemaps_data = scrape_googlemaps(googlemaps_url)
        if googlemaps_data.get("error"):
            errors["googlemaps"] = googlemaps_data["error"]

    logo_b64 = download_logo(website_url, instagram_data)

    config = generate_config(website_data, instagram_data, googlemaps_data)

    if logo_b64:
        config["avatarUrl"] = f"data:image/png;base64,{logo_b64}"

    config["proxyUrl"] = "/api/chat"
    config["_scrape_errors"] = errors

    return config
