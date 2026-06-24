"""
scrape_instagram.py
Scrapes a public Instagram profile page for bio, name, and post captions.
Uses Instaloader (no login required for public profiles).

Usage:
    python tools/scrape_instagram.py <username_or_url> <output_json>

Example:
    python tools/scrape_instagram.py https://www.instagram.com/nike/ .tmp/instagram.json
    python tools/scrape_instagram.py nike .tmp/instagram.json
"""

import sys
import json
import re

try:
    import instaloader
except ImportError:
    print("ERROR: Missing dependency. Run: pip install instaloader")
    sys.exit(1)


MAX_POSTS = 20  # Limit to avoid long runtimes


def extract_username(input_str: str) -> str:
    """Accept full URL or plain username."""
    match = re.search(r"instagram\.com/([^/?#]+)", input_str)
    if match:
        return match.group(1).strip("/")
    return input_str.strip().strip("@")


def run(input_str: str, output_path: str) -> None:
    username = extract_username(input_str)
    print(f"[scrape_instagram] Scraping @{username}")

    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    output = {
        "source_type": "instagram",
        "username": username,
        "bio": "",
        "full_name": "",
        "followers": None,
        "following": None,
        "posts_count": None,
        "recent_posts": [],
        "error": None,
    }

    try:
        profile = instaloader.Profile.from_username(loader.context, username)

        output["bio"]         = profile.biography or ""
        output["full_name"]   = profile.full_name or ""
        output["followers"]   = profile.followers
        output["following"]   = profile.followees
        output["posts_count"] = profile.mediacount

        posts = []
        for post in profile.get_posts():
            if len(posts) >= MAX_POSTS:
                break
            posts.append({
                "caption": post.caption or "",
                "likes":   post.likes,
                "date":    post.date_utc.isoformat() if post.date_utc else None,
                "hashtags": list(post.caption_hashtags) if post.caption_hashtags else [],
            })
        output["recent_posts"] = posts

    except instaloader.exceptions.ProfileNotExistsException:
        output["error"] = f"Profile @{username} does not exist or is private."
        print(f"[scrape_instagram] ERROR: {output['error']}")
    except Exception as e:
        output["error"] = str(e)
        print(f"[scrape_instagram] ERROR: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[scrape_instagram] Done. Output: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tools/scrape_instagram.py <username_or_url> <output_json>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
