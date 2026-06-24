# Workflow — Art Direction & Visual Personalization

Run this workflow **after** `generate_prompt.md` and **before** `qa_chatbot.md`.

---

## Prerequisites
- `clients/<name>/scraped_data.json` exists
- `clients/<name>/system_prompt.txt` exists

---

## Step 0 — Download Brand Assets

```
py tools/download_brand_assets.py <client_name>
```

Downloads the best available logo automatically (Instagram profile pic → Apple touch icon → favicon).
Runs `process_logo.py` on the result to auto-crop any uniform background border.

Output: `clients/<name>/assets/logo_cropped.png` (or best available)

> Skip if the client has already provided a logo manually in `clients/<name>/assets/`.

---

## Step 1 — Analyze Brand Visuals (RECOMMENDED)

```
py tools/analyze_visuals.py <client_name>
```

Sends all brand images (logo, icons) to Claude's vision API. Claude analyzes
the actual visual identity: exact brand colors, design style, typography direction,
and chatbot UI recommendations.

Output: `clients/<name>/visual_analysis.json`

> Skip only if there are no images in `assets/` yet.

---

## Step 2 — Generate Art Direction

```
py tools/generate_art_direction.py <client_name>
```

Combines the visual analysis (if available) with scraped business data and calls
Claude to generate a complete design sheet. When `visual_analysis.json` exists,
it is treated as the highest-priority source for colors and design direction.

Output: `clients/<name>/art_direction.json`

---

## Step 3 — Review Art Direction (REQUIRED)

Open `clients/<name>/art_direction.json` and review:

- [ ] `colors.primary` — correct brand color?
- [ ] `colors.primaryContrast` — readable on primary? (white on dark, black on light)
- [ ] `typography.fontFamily` — matches brand personality?
- [ ] `typography.googleFontsUrl` — valid Google Fonts URL?
- [ ] `welcome_message` — correct language and tone?
- [ ] `placeholder` — correct language?
- [ ] `logo.invert` — if logo is dark on white, set to `true` for dark backgrounds
- [ ] `vibe` — does it match the brand?

**Do not proceed until you are satisfied with the art direction.**

Adjust any values manually before moving to Step 4.

---

## Step 4 — Apply Art Direction

```
py tools/apply_art_direction.py <client_name>
```

This copies the base template, injects all brand colors/fonts/logo, and writes
a fully themed `clients/<name>/chatbot/config.json`.

---

## Step 5 — Visual Review

```
py preview_server.py <client_name>
```

Open http://localhost:8000 and check:

- [ ] Header color and logo look correct
- [ ] Font is applied properly
- [ ] Bot bubble color is readable
- [ ] User bubble color is readable
- [ ] Send button matches brand
- [ ] Overall feel matches the brand vibe
- [ ] Welcome message is correct

---

## Step 6 — Manual Tweaks (if needed)

Edit `clients/<name>/chatbot/config.json` directly to adjust any value.
Reload the browser to see changes instantly (no server restart needed).

Common tweaks:
- Adjust `colorBotBubble` if it looks too similar to the background
- Adjust `radiusBubble` for sharper (`8px`) or rounder (`24px`) bubbles
- Change `welcomeMessage` for better tone/language
- Set `avatarInvert: true` if logo needs to be inverted on dark header

---

## Step 7 — Final Approval

Once the chatbot looks correct visually, proceed to:

```
workflows/qa_chatbot.md
```

---

## Notes

- `apply_art_direction.py` always does a **clean rebuild** of `chatbot/` from the base template
- If you run it again, all manual edits to `chatbot/config.json` are overwritten — edit `art_direction.json` instead, then re-apply
- The base template (`templates/base_chatbot/`) is **never modified** — all theming lives in `config.json`
