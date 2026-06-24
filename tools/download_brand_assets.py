"""
download_brand_assets.py
========================
Downloads brand assets for a client (Instagram profile pic, favicon, etc.)
and saves them to clients/<client>/assets/.

Usage:
    py tools/download_brand_assets.py <client_name>

Output:
    clients/<client_name>/assets/
        profile_pic.jpg     <- Instagram profile picture (square, ideal for avatar)
        favicon.ico/.png    <- Website favicon
        asset_manifest.json <- What was found and where
"""

import sys, os, json, urllib.request, urllib.error, re
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent
CLIENTS_DIR = BASE_DIR / "clients"

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg):  print(f"[download_brand_assets] {msg}")
def ok(msg):   print(f"  [OK] {msg}")
def warn(msg): print(f"  [!]  {msg}")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def fetch_url(url, binary=True):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read() if binary else r.read().decode("utf-8", errors="ignore")

def save_file(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

# ── Instagram profile picture ─────────────────────────────────────────────────

def download_instagram_pic(username, assets_dir):
    """
    Downloads the Instagram profile picture using instaloader (no login needed
    for public accounts). Falls back to og:image HTML scraping if unavailable.
    """
    if not username:
        return None

    username = username.strip("/").split("/")[-1]
    source_url = f"https://www.instagram.com/{username}/"

    # Try instaloader first (most reliable)
    try:
        import instaloader
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError("instaloader timed out")

        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            quiet=True,
            max_connection_attempts=1,
        )
        profile = instaloader.Profile.from_username(L.context, username)
        pic_url = profile.profile_pic_url
        data = fetch_url(pic_url)
        dest = assets_dir / "profile_pic.jpg"
        save_file(data, dest)
        ok(f"Instagram profile picture -> {dest.name}  (@{username})")
        return {"name": "Instagram profile picture", "file": dest.name, "source": source_url}

    except ImportError:
        warn("instaloader not installed -- run: pip install instaloader")
    except Exception as e:
        err = str(e)
        if "429" in err or "Too Many Requests" in err:
            warn("Instagram rate-limited (429) -- wait ~30 min and retry")
        else:
            warn(f"instaloader failed: {e}")

    # Fallback: og:image from HTML
    try:
        html = fetch_url(source_url, binary=False)
        match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if match:
            pic_url = match.group(1).replace("\\u0026", "&")
            data = fetch_url(pic_url)
            dest = assets_dir / "profile_pic.jpg"
            save_file(data, dest)
            ok(f"Instagram profile picture (fallback) -> {dest.name}")
            return {"name": "Instagram profile picture", "file": dest.name, "source": source_url}
    except Exception:
        pass

    warn("Instagram: could not download profile picture")
    return None

# ── Apple touch icon (high-res, square, great for avatar) ────────────────────

def download_apple_touch_icon(website_url, assets_dir):
    if not website_url:
        return None

    website_url = website_url.rstrip("/")
    from urllib.parse import urlparse
    parsed = urlparse(website_url)
    base   = f"{parsed.scheme}://{parsed.netloc}"

    candidates = []
    try:
        html = fetch_url(website_url, binary=False)
        for m in re.finditer(
            r'<link[^>]+rel=["\']apple-touch-icon[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        ):
            href = m.group(1)
            if not href.startswith("http"):
                href = base + "/" + href.lstrip("/")
            candidates.append(href)
    except Exception:
        pass

    candidates.append(f"{base}/apple-touch-icon.png")
    candidates.append(f"{base}/apple-touch-icon-precomposed.png")

    for icon_url in candidates:
        try:
            data = fetch_url(icon_url)
            if len(data) < 100:
                continue
            dest = assets_dir / "apple_touch_icon.png"
            save_file(data, dest)
            ok(f"Apple touch icon -> {dest.name}")
            return {"name": "Apple touch icon", "file": dest.name, "source": icon_url}
        except Exception:
            continue

    return None

# ── Website favicon ───────────────────────────────────────────────────────────

def download_favicon(website_url, assets_dir):
    if not website_url:
        return None

    website_url = website_url.rstrip("/")
    from urllib.parse import urlparse
    parsed = urlparse(website_url)
    base   = f"{parsed.scheme}://{parsed.netloc}"

    candidates = []
    try:
        html = fetch_url(website_url, binary=False)
        for m in re.finditer(
            r'<link[^>]+rel=["\']([^"\']*icon[^"\']*)["\'][^>]+href=["\']([^"\']+)["\']',
            html, re.IGNORECASE
        ):
            href = m.group(2)
            if not href.startswith("http"):
                href = base + "/" + href.lstrip("/")
            candidates.append(href)
        for m in re.finditer(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']([^"\']*icon[^"\']*)["\']',
            html, re.IGNORECASE
        ):
            href = m.group(1)
            if not href.startswith("http"):
                href = base + "/" + href.lstrip("/")
            candidates.append(href)
    except Exception:
        pass

    candidates.append(f"{base}/favicon.ico")
    candidates.append(f"{base}/favicon.png")

    for fav_url in candidates:
        try:
            data = fetch_url(fav_url)
            if len(data) < 50:
                continue
            ext  = Path(fav_url.split("?")[0]).suffix or ".ico"
            dest = assets_dir / f"favicon{ext}"
            save_file(data, dest)
            ok(f"Favicon -> {dest.name}")
            return {"name": "Website favicon", "file": dest.name, "source": fav_url}
        except Exception:
            continue

    warn("Favicon: not found")
    return None

# ── Pick best avatar ──────────────────────────────────────────────────────────

def recommend_avatar(assets):
    priority = ["Instagram profile picture", "Apple touch icon", "Website favicon"]
    for name in priority:
        for a in assets:
            if a["name"] == name:
                return a["file"]
    return None

# ── Main ──────────────────────────────────────────────────────────────────────

def run(client_name):
    client_dir = CLIENTS_DIR / client_name
    if not client_dir.exists():
        print(f"ERROR: Client folder not found: {client_dir}")
        sys.exit(1)

    assets_dir = client_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    sources_file  = client_dir / "sources.txt"
    instagram_url = None
    website_url   = None

    if sources_file.exists():
        for line in sources_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.lower().startswith("instagram:"):
                instagram_url = line.split(":", 1)[1].strip()
            elif line.lower().startswith("website:"):
                website_url = line.split(":", 1)[1].strip()

    scraped_file = client_dir / "scraped_data.json"
    if scraped_file.exists():
        try:
            data = json.loads(scraped_file.read_text(encoding="utf-8"))
            if not instagram_url and data.get("instagram", {}).get("profile_url"):
                instagram_url = data["instagram"]["profile_url"]
            if not website_url:
                website_url = (
                    data.get("website", {}).get("base_url")
                    or data.get("website", {}).get("url")
                )
        except Exception:
            pass

    log(f"Downloading brand assets for: {client_name}")
    log(f"  Instagram : {instagram_url or '--'}")
    log(f"  Website   : {website_url or '--'}")

    found = []

    r = download_instagram_pic(instagram_url, assets_dir)
    if r: found.append(r)

    r = download_apple_touch_icon(website_url, assets_dir)
    if r: found.append(r)

    r = download_favicon(website_url, assets_dir)
    if r: found.append(r)

    avatar = recommend_avatar(found)

    # Auto-crop: remove uniform background borders from the best avatar
    if avatar:
        raw_path    = assets_dir / avatar
        cropped_name = "logo_cropped.png"
        cropped_path = assets_dir / cropped_name
        try:
            import importlib.util, sys as _sys
            spec = importlib.util.spec_from_file_location(
                "process_logo",
                Path(__file__).parent / "process_logo.py"
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.process_logo(str(raw_path), str(cropped_path), padding=8)
            avatar = cropped_name
            ok(f"Logo auto-cropped -> {cropped_name}")
        except Exception as e:
            warn(f"process_logo failed (using raw): {e}")

    # Add white background if logo is a transparent PNG
    if avatar:
        logo_path = assets_dir / avatar
        try:
            from PIL import Image
            img = Image.open(logo_path)
            if img.mode == "RGBA":
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                bg.convert("RGB").save(logo_path)
                ok("White background applied to logo")
        except Exception as e:
            warn(f"Could not apply white background: {e}")

    manifest = {
        "client":             client_name,
        "assets":             found,
        "recommended_avatar": avatar
    }
    (assets_dir / "asset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print()
    log(f"Done. {len(found)} asset(s) -> clients/{client_name}/assets/")
    if avatar:
        log(f"Recommended avatar: {avatar}")
        log(f"Copy it to chatbot/ and set in config.json: \"avatarUrl\": \"{avatar}\"")
    else:
        log("No assets found -- add logo manually to clients/{client_name}/assets/")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py tools/download_brand_assets.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
