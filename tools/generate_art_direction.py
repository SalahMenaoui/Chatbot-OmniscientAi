"""
generate_art_direction.py
Analyzes all available client sources and generates a complete art direction
sheet saved to clients/<name>/art_direction.json.

Usage:
    py tools/generate_art_direction.py <client_name>
"""

import sys
import json
import os
import re
from collections import Counter
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    print("ERROR: Run: pip install anthropic python-dotenv")
    sys.exit(1)

load_dotenv()

# -- Helpers -------------------------------------------------------------------

def extract_colors_from_html(html):
    """Extract the most frequent non-trivial hex colors from raw HTML/CSS."""
    hex_colors = re.findall(r'#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b', html)
    normalized = []
    for c in hex_colors:
        if len(c) == 3:
            c = c[0]*2 + c[1]*2 + c[2]*2
        normalized.append('#' + c.lower())

    # Skip near-black, near-white, pure grays
    trivial = {
        '#ffffff','#000000','#1a1a1a','#111111','#222222','#333333',
        '#444444','#555555','#666666','#777777','#888888','#999999',
        '#aaaaaa','#bbbbbb','#cccccc','#dddddd','#eeeeee','#f0f0f0',
        '#f5f5f5','#fafafa','#e5e5e5','#d4d4d4','#404040','#0a0a0a',
    }
    filtered = [c for c in normalized if c not in trivial]
    counter = Counter(filtered)
    return [color for color, _ in counter.most_common(8)]

def extract_google_fonts_url(html):
    matches = re.findall(r'https://fonts\.googleapis\.com/css[^\s"\'<>]+', html)
    return matches[0] if matches else None

def extract_font_family(html):
    matches = re.findall(r"font-family\s*:\s*([^;}{<\n]+)", html)
    if not matches:
        return None
    counter = Counter(m.strip().strip("'\"") for m in matches)
    # Skip generic fallbacks
    skip = {'sans-serif','serif','monospace','inherit','initial','unset'}
    for family, _ in counter.most_common(5):
        base = family.split(',')[0].strip().strip("'\"")
        if base.lower() not in skip:
            return family.strip()
    return None

def find_logo(client_dir):
    """Return relative path to logo file if one exists in assets/ or chatbot/."""
    for subdir in ["assets", "chatbot"]:
        for ext in ["png", "jpg", "jpeg", "svg", "webp"]:
            for name in ["logo_cropped", "logo_raw", "logo", "icon", "brand", "avatar", "apple_touch_icon"]:
                path = os.path.join(client_dir, subdir, f"{name}.{ext}")
                if os.path.isfile(path):
                    return f"{subdir}/{name}.{ext}"
    return None

# -- Main ----------------------------------------------------------------------

def run(client_name):
    client_dir       = os.path.join("clients", client_name)
    scraped_path     = os.path.join(client_dir, "scraped_data.json")
    visual_path      = os.path.join(client_dir, "visual_analysis.json")
    output_path      = os.path.join(client_dir, "art_direction.json")

    if not os.path.isdir(client_dir):
        print(f"[generate_art_direction] ERROR: Client folder not found: {client_dir}")
        sys.exit(1)

    if not os.path.isfile(scraped_path):
        print(f"[generate_art_direction] ERROR: scraped_data.json not found for {client_name}")
        sys.exit(1)

    print(f"[generate_art_direction] Analyzing brand identity for: {client_name}")

    with open(scraped_path, "r", encoding="utf-8") as f:
        scraped = json.load(f)

    # -- Load visual analysis if available (from analyze_visuals.py) ----------
    visual_analysis = None
    if os.path.isfile(visual_path):
        with open(visual_path, "r", encoding="utf-8") as f:
            visual_analysis = json.load(f)
        print(f"  Visual analysis:   found ({len(visual_analysis.get('images_analyzed', []))} image(s) analyzed)")
    else:
        print(f"  Visual analysis:   not found — run analyze_visuals.py first for better results")

    # -- Extract visual signals from raw HTML (fallback) ----------------------
    raw_html = ""
    website  = scraped.get("website", {})
    raw_html = website.get("raw_html", "") or ""

    extracted_colors     = extract_colors_from_html(raw_html)
    extracted_fonts_url  = extract_google_fonts_url(raw_html)
    extracted_font_fam   = extract_font_family(raw_html)
    logo_path            = find_logo(client_dir)

    print(f"  Extracted colors:  {extracted_colors or 'none found'}")
    print(f"  Google Fonts URL:  {extracted_fonts_url or 'not found'}")
    print(f"  Font family hint:  {extracted_font_fam or 'not found'}")
    print(f"  Logo file:         {logo_path or 'not found'}")

    # -- Build context for Claude ----------------------------------------------
    context_parts = []

    # Business info — try multiple sources for the name
    pages      = website.get("pages", [])
    page_title = pages[0].get("title", "") if pages else ""
    # Strip common suffixes like "- Accueil", "| Home", etc.
    clean_title = re.sub(r'\s*[-|–]\s*(Accueil|Home|Bienvenue|Welcome).*$', '', page_title, flags=re.I).strip()
    business_name = (scraped.get("business_name") or clean_title or website.get("title") or client_name)
    context_parts.append(f"Business name: {business_name}")

    if website.get("description"):
        context_parts.append(f"Website description: {website['description']}")

    if website.get("services") and isinstance(website["services"], list):
        context_parts.append(f"Services: {', '.join(website['services'][:8])}")

    if scraped.get("instagram"):
        ig = scraped["instagram"]
        context_parts.append(f"Instagram bio: {ig.get('bio','')}")
        if ig.get("posts"):
            captions = [p.get("caption","") for p in ig["posts"][:3] if p.get("caption")]
            context_parts.append(f"Instagram post samples: {' | '.join(captions)}")

    if scraped.get("googlemaps"):
        gm = scraped["googlemaps"]
        context_parts.append(f"Google Maps category: {gm.get('category','')}")
        context_parts.append(f"Rating: {gm.get('rating','')}")

    # Visual analysis (highest priority — Claude actually saw the brand images)
    if visual_analysis:
        va     = visual_analysis
        bc     = va.get("brand_colors", {})
        logo_a = va.get("logo_analysis", {})
        typo_d = va.get("typography_direction", {})
        ui_rec = va.get("chatbot_ui_recommendations", {})

        context_parts.append("VISUAL ANALYSIS (Claude analyzed the actual brand images — treat as highest-priority source):")
        context_parts.append(f"  Dominant brand color: {bc.get('dominant')}")
        context_parts.append(f"  Secondary color: {bc.get('secondary')}")
        context_parts.append(f"  Accent color: {bc.get('accent')}")
        context_parts.append(f"  Neutral tones: {', '.join(bc.get('neutrals', []))}")
        context_parts.append(f"  Color mood: {va.get('color_palette_description')}")
        context_parts.append(f"  Design style: {va.get('design_style')}")
        context_parts.append(f"  Brand personality: {', '.join(va.get('brand_personality', []))}")
        context_parts.append(f"  Typography style: {typo_d.get('style')} / {typo_d.get('weight_feel')} — {typo_d.get('personality')}")
        context_parts.append(f"  Logo works on dark backgrounds: {logo_a.get('works_on_dark')}")
        context_parts.append(f"  Logo complexity: {logo_a.get('complexity')}")
        context_parts.append(f"  UI border-radius: {ui_rec.get('border_radius')}")
        context_parts.append(f"  UI spacing: {ui_rec.get('spacing_feel')}")
        context_parts.append(f"  UI button style: {ui_rec.get('button_style')}")
        context_parts.append(f"  UI header: {ui_rec.get('header_treatment')}")
        context_parts.append(f"  Design notes: {va.get('design_notes')}")

    # Visual signals from HTML (fallback, lower priority than visual analysis)
    if extracted_colors:
        label = "Colors detected on website (CSS fallback)" if visual_analysis else "Colors detected on website"
        context_parts.append(f"{label}: {', '.join(extracted_colors)}")
    if extracted_font_fam:
        context_parts.append(f"Font detected on website: {extracted_font_fam}")
    if logo_path:
        context_parts.append(f"Logo file available at: {logo_path}")

    context = "\n".join(context_parts)

    # -- Call Claude API -------------------------------------------------------
    print("  Calling Claude API for art direction... (uses API credits)")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an expert brand designer and UI/UX specialist.

Based on the following business data, generate a complete art direction sheet for a chatbot widget that perfectly represents this brand's visual identity.

BUSINESS DATA:
{context}

Return a JSON object with EXACTLY this structure (no markdown, no explanation, raw JSON only):
{{
  "brand_name": "...",
  "vibe": ["keyword1", "keyword2", "keyword3"],
  "personality_tone": "...",
  "welcome_message": "...",

  "colors": {{
    "primary": "#xxxxxx",
    "primaryDark": "#xxxxxx",
    "primaryContrast": "#xxxxxx",
    "bg": "#xxxxxx",
    "surface": "#xxxxxx",
    "surface2": "#xxxxxx",
    "text": "#xxxxxx",
    "textMuted": "#xxxxxx",
    "border": "#xxxxxx",
    "botBubble": "#xxxxxx",
    "botText": "#xxxxxx",
    "userBubble": "#xxxxxx",
    "userText": "#xxxxxx",
    "headerBg": "#xxxxxx",
    "headerText": "#xxxxxx",
    "headerSubtext": "rgba(...)"
  }},

  "typography": {{
    "fontFamily": "'Font Name', fallback, sans-serif",
    "googleFontsUrl": "https://fonts.googleapis.com/css2?family=...&display=swap"
  }},

  "shape": {{
    "radiusBubble": "18px",
    "radiusInput": "12px",
    "radiusSend": "10px",
    "buttonStyle": "rounded|sharp|pill",
    "spacingFeel": "tight|comfortable|airy"
  }},

  "logo": {{
    "path": "{logo_path or 'null'}",
    "invert": false,
    "displayStyle": "image|initial"
  }},

  "avatarInitial": "X",
  "placeholder": "...",

  "design_notes": "Brief explanation of the design choices made."
}}

Rules:
- If VISUAL ANALYSIS data is present, it is the HIGHEST priority source — it comes from Claude actually seeing the brand images
- Use the exact hex colors from the visual analysis as the basis for the palette; only deviate if you have a strong design reason
- If no visual analysis, use detected website colors as the basis
- primary should be the dominant brand color
- primaryContrast MUST be readable on primaryColor (white on dark, black on light)
- botBubble should be a very light neutral (not white)
- userBubble is typically the primary color
- headerBg is typically the primary color
- Choose a Google Font that matches the brand personality
- welcome_message should be in the same language as the business (French if French business)
- placeholder should match the language
- avatarInitial: first letter of the brand name"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        art_direction = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[generate_art_direction] ERROR: Could not parse Claude response as JSON: {e}")
        print("Raw response:", raw[:500])
        sys.exit(1)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(art_direction, f, indent=2, ensure_ascii=False)

    print(f"\n  Art direction saved to: {output_path}")
    print(f"\n  ---------------------------------------------")
    print(f"  Brand:       {art_direction.get('brand_name')}")
    print(f"  Vibe:        {', '.join(art_direction.get('vibe', []))}")
    print(f"  Primary:     {art_direction.get('colors', {}).get('primary')}")
    print(f"  Font:        {art_direction.get('typography', {}).get('fontFamily')}")
    print(f"  Logo:        {art_direction.get('logo', {}).get('path') or 'initial only'}")
    print(f"  ---------------------------------------------\n")
    print("  Review art_direction.json and approve before running apply_art_direction.py")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py tools/generate_art_direction.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
