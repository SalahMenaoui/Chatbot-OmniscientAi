"""
scrape_tiktok.py
Scrapes a public TikTok profile for bio, username, and recent video descriptions.
Uses the unofficial TikTok API via the 'TikTokApi' library.

Usage:
    python tools/scrape_tiktok.py <username_or_url> <output_json>

Example:
    python tools/scrape_tiktok.py https://www.tiktok.com/@nike .tmp/tiktok.json
    python tools/scrape_tiktok.py @nike .tmp/tiktok.json

NOTE: TikTok scraping is fragile. If this fails, manually add info to scraped_data.json.
Requires: pip install TikTokApi playwright
Then run: playwright install chromium
"""

import sys
import json
import re
import asyncio

try:
    from TikTokApi import TikTokApi
except ImportError:
    print("ERROR: Missing dependency. Run: pip install TikTokApi && playwright install chromium")
    sys.exit(1)


MAX_VIDEOS = 20


def extract_username(input_str: str) -> str:
    """Accept full URL or @username or plain username."""
    match = re.search(r"tiktok\.com/@([^/?#]+)", input_str)
    if match:
        return match.group(1)
    return input_str.strip().lstrip("@")


async def scrape(username: str, output_path: str) -> None:
    output = {
        "source_type": "tiktok",
        "username": username,
        "bio": "",
        "nickname": "",
        "followers": None,
        "likes": None,
        "recent_videos": [],
        "error": None,
    }

    try:
        async with TikTokApi() as api:
            await api.create_sessions(num_sessions=1, sleep_after=3, headless=True)

            user = api.user(username=username)
            info = await user.info()

            user_data = info.get("userInfo", {})
            user_obj  = user_data.get("user", {})
            stats     = user_data.get("stats", {})

            output["bio"]       = user_obj.get("signature", "")
            output["nickname"]  = user_obj.get("nickname", "")
            output["followers"] = stats.get("followerCount")
            output["likes"]     = stats.get("heartCount")

            videos = []
            async for video in user.videos(count=MAX_VIDEOS):
                desc = video.as_dict.get("desc", "")
                videos.append({
                    "description": desc,
                    "play_count":  video.as_dict.get("stats", {}).get("playCount"),
                    "like_count":  video.as_dict.get("stats", {}).get("diggCount"),
                    "hashtags":    re.findall(r"#(\w+)", desc),
                })
            output["recent_videos"] = videos

    except Exception as e:
        output["error"] = str(e)
        print(f"[scrape_tiktok] ERROR: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[scrape_tiktok] Done. Output: {output_path}")


def run(input_str: str, output_path: str) -> None:
    username = extract_username(input_str)
    print(f"[scrape_tiktok] Scraping @{username}")
    asyncio.run(scrape(username, output_path))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python tools/scrape_tiktok.py <username_or_url> <output_json>")
        sys.exit(1)
    run(sys.argv[1], sys.argv[2])
