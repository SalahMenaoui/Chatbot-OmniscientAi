"""
analyze_visuals.py
Uses Claude's vision API to analyze all available brand images and produce a
rich visual brand analysis saved to clients/<name>/visual_analysis.json.

Run this BEFORE generate_art_direction.py for best results.

Usage:
    py tools/analyze_visuals.py <client_name>
"""

import sys
import json
import os
import base64
import re
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    print("ERROR: Run: pip install anthropic python-dotenv")
    sys.exit(1)

load_dotenv()

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MEDIA_TYPE_MAP = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

# Priority order when selecting images from assets/
IMAGE_PRIORITY = [
    "logo_cropped", "logo_raw", "logo", "icon",
    "brand", "avatar", "apple_touch_icon", "favicon",
]


def encode_image(path):
    ext = os.path.splitext(path)[1].lower()
    media_type = MEDIA_TYPE_MAP.get(ext, "image/png")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def collect_images(client_dir):
    """Return up to 4 brand images from assets/, highest-priority first."""
    assets_dir = os.path.join(client_dir, "assets")
    if not os.path.isdir(assets_dir):
        return []

    found = {}
    for fname in os.listdir(assets_dir):
        base, ext = os.path.splitext(fname)
        if ext.lower() in SUPPORTED_EXTENSIONS:
            found[base.lower()] = os.path.join(assets_dir, fname)

    ordered, seen = [], set()
    for key in IMAGE_PRIORITY:
        if key in found:
            ordered.append(found[key])
            seen.add(key)
    for key, path in found.items():
        if key not in seen:
            ordered.append(path)

    return ordered[:4]


def run(client_name):
    client_dir   = os.path.join("clients", client_name)
    output_path  = os.path.join(client_dir, "visual_analysis.json")
    scraped_path = os.path.join(client_dir, "scraped_data.json")

    if not os.path.isdir(client_dir):
        print(f"[analyze_visuals] ERROR: Client folder not found: {client_dir}")
        sys.exit(1)

    images = collect_images(client_dir)
    if not images:
        print(f"[analyze_visuals] No images found in {client_dir}/assets/ — skipping.")
        sys.exit(0)

    print(f"[analyze_visuals] Analyzing brand visuals for: {client_name}")
    for img in images:
        print(f"  Image: {os.path.relpath(img, client_dir)}")

    # Load business context
    business_name = client_name
    business_type = ""
    if os.path.isfile(scraped_path):
        with open(scraped_path, "r", encoding="utf-8") as f:
            scraped = json.load(f)
        business_name = scraped.get("business_name") or scraped.get("client") or client_name
        website = scraped.get("website", {})
        business_type = website.get("service_type") or website.get("category") or ""

    # Build message content: all images first, then text prompt
    content = []
    image_refs = []
    for path in images:
        data, media_type = encode_image(path)
        rel_path = os.path.relpath(path, client_dir)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            }
        })
        image_refs.append(rel_path)

    prompt = f"""You are an expert brand designer with deep knowledge of color theory, typography, and visual identity.

Business name: {business_name}
Business type: {business_type or "unknown"}

The images above are the brand's visual assets. Analyze them carefully and return a complete visual brand analysis.

Return a JSON object with EXACTLY this structure (raw JSON only, no markdown, no explanation):
{{
  "images_analyzed": {json.dumps(image_refs)},

  "brand_colors": {{
    "dominant": "#xxxxxx",
    "secondary": "#xxxxxx",
    "accent": "#xxxxxx",
    "neutrals": ["#xxxxxx", "#xxxxxx"]
  }},

  "color_palette_description": "One sentence describing the overall color mood.",

  "logo_analysis": {{
    "has_icon": true,
    "has_text": true,
    "background": "transparent|white|colored",
    "icon_style": "geometric|organic|illustrative|typographic|emblem",
    "complexity": "simple|moderate|detailed",
    "works_on_dark": true,
    "works_on_light": true
  }},

  "brand_personality": ["keyword1", "keyword2", "keyword3"],

  "design_style": "minimal|corporate|bold|artisan|playful|elegant|technical|warm",

  "typography_direction": {{
    "style": "geometric-sans|humanist-sans|serif|slab-serif|display|rounded",
    "weight_feel": "light|regular|medium|bold",
    "personality": "One sentence on what font personality fits this brand."
  }},

  "chatbot_ui_recommendations": {{
    "border_radius": "4px|8px|12px|18px|24px",
    "spacing_feel": "tight|comfortable|airy",
    "button_style": "rounded|sharp|pill",
    "header_treatment": "solid|gradient|subtle",
    "bubble_style": "flat|soft-shadow|bordered"
  }},

  "design_notes": "2-3 sentences explaining the brand visual identity and how it should translate to the chatbot UI."
}}

Rules:
- Extract exact hex values of colors you can actually see in the images
- dominant = the most prominent brand color (not white or transparent backgrounds)
- If the logo sits on a white background, identify the actual brand colors within the artwork
- brand_personality must be exactly 3 adjectives describing the brand feeling
- works_on_dark / works_on_light: will the logo be legible on those backgrounds?
- design_notes should give a clear direction to the person styling the chatbot widget"""

    content.append({"type": "text", "text": prompt})

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    print("  Calling Claude Vision API... (uses API credits)")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        analysis = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[analyze_visuals] ERROR: Could not parse Claude response as JSON: {e}")
        print("Raw response:", raw[:500])
        sys.exit(1)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    colors = analysis.get("brand_colors", {})
    logo   = analysis.get("logo_analysis", {})
    print(f"\n  Visual analysis saved to: {output_path}")
    print(f"\n  ---------------------------------------------")
    print(f"  Dominant color:  {colors.get('dominant')}")
    print(f"  Secondary:       {colors.get('secondary')}")
    print(f"  Design style:    {analysis.get('design_style')}")
    print(f"  Personality:     {', '.join(analysis.get('brand_personality', []))}")
    print(f"  Logo on dark:    {'yes' if logo.get('works_on_dark') else 'no'}")
    print(f"  Logo on light:   {'yes' if logo.get('works_on_light') else 'no'}")
    print(f"  ---------------------------------------------\n")
    print(f"  Next: py tools/generate_art_direction.py {client_name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py tools/analyze_visuals.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
