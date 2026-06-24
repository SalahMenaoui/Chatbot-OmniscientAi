"""
apply_art_direction.py
Takes art_direction.json and fully rebuilds the client chatbot with brand theming.
Copies the base template, injects system prompt + all visual config.

Usage:
    py tools/apply_art_direction.py <client_name>
"""

import sys
import json
import os
import shutil

# -- Main ----------------------------------------------------------------------

def run(client_name):
    client_dir    = os.path.join("clients", client_name)
    art_path      = os.path.join(client_dir, "art_direction.json")
    prompt_path   = os.path.join(client_dir, "system_prompt.txt")
    chatbot_dir   = os.path.join(client_dir, "chatbot")
    template_dir  = os.path.join("templates", "base_chatbot")
    config_path   = os.path.join(chatbot_dir, "config.json")

    # -- Validate --------------------------------------------------------------
    if not os.path.isdir(client_dir):
        print(f"[apply_art_direction] ERROR: Client folder not found: {client_dir}")
        sys.exit(1)

    if not os.path.isfile(art_path):
        print(f"[apply_art_direction] ERROR: art_direction.json not found.")
        print(f"  Run: py tools/generate_art_direction.py {client_name}")
        sys.exit(1)

    if not os.path.isfile(prompt_path):
        print(f"[apply_art_direction] ERROR: system_prompt.txt not found.")
        print(f"  Run: py tools/generate_system_prompt.py {client_name}")
        sys.exit(1)

    print(f"[apply_art_direction] Applying art direction for: {client_name}")

    with open(art_path,    "r", encoding="utf-8") as f:
        art = json.load(f)

    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    # -- Copy base template ----------------------------------------------------
    if os.path.isdir(chatbot_dir):
        shutil.rmtree(chatbot_dir)
    shutil.copytree(template_dir, chatbot_dir)
    print(f"  Base template copied to {chatbot_dir}")

    # -- Copy logo if available ------------------------------------------------
    logo_src_rel = art.get("logo", {}).get("path")
    avatar_url   = None

    if logo_src_rel and logo_src_rel != "null":
        logo_src = os.path.join(client_dir, logo_src_rel)
        if os.path.isfile(logo_src):
            logo_filename = os.path.basename(logo_src)
            logo_dst      = os.path.join(chatbot_dir, logo_filename)
            shutil.copy2(logo_src, logo_dst)
            avatar_url = logo_filename
            print(f"  Logo copied: {logo_filename}")
        else:
            print(f"  Logo not found at {logo_src}, skipping")

    # -- Build config.json -----------------------------------------------------
    colors = art.get("colors", {})
    typo   = art.get("typography", {})
    shape  = art.get("shape", {})
    logo   = art.get("logo", {})

    config = {
        # Core
        "botName":       art.get("brand_name", client_name),
        "welcomeMessage": art.get("welcome_message", "Hi! How can I help you today?"),
        "placeholder":   art.get("placeholder", "Type your message..."),
        "systemPrompt":  system_prompt,

        # API
        "proxyUrl":  "/api/chat",
        "model":     "claude-haiku-4-5-20251001",
        "maxTokens": 1024,

        # Branding
        "avatarInitial": art.get("avatarInitial", art.get("brand_name", "A")[0].upper()),
        "avatarUrl":     avatar_url,
        "avatarInvert":  logo.get("invert", False),
        "colorAvatarBg": art.get("avatarBg"),

        # Fonts
        "googleFontsUrl": typo.get("googleFontsUrl"),
        "fontFamily":     typo.get("fontFamily"),

        # Colors
        "colorPrimary":         colors.get("primary"),
        "colorPrimaryDark":     colors.get("primaryDark"),
        "colorPrimaryContrast": colors.get("primaryContrast"),
        "colorBg":              colors.get("bg"),
        "colorSurface":         colors.get("surface"),
        "colorSurface2":        colors.get("surface2"),
        "colorText":            colors.get("text"),
        "colorTextMuted":       colors.get("textMuted"),
        "colorBorder":          colors.get("border"),
        "colorBotBubble":       colors.get("botBubble"),
        "colorBotText":         colors.get("botText"),
        "colorUserBubble":      colors.get("userBubble"),
        "colorUserText":        colors.get("userText"),
        "colorHeaderBg":        colors.get("headerBg"),
        "colorHeaderText":      colors.get("headerText"),
        "colorHeaderSubtext":   colors.get("headerSubtext"),

        # Shape
        "radiusBubble": shape.get("radiusBubble"),
        "radiusInput":  shape.get("radiusInput"),
        "radiusSend":   shape.get("radiusSend"),
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"  config.json written")

    # -- Summary ---------------------------------------------------------------
    print(f"\n  ---------------------------------------------")
    print(f"  Done: {chatbot_dir}")
    print(f"  Bot name:  {config['botName']}")
    print(f"  Primary:   {colors.get('primary')}")
    print(f"  Font:      {typo.get('fontFamily')}")
    print(f"  Avatar:    {'logo image' if avatar_url else 'initial letter'}")
    print(f"  ---------------------------------------------")
    print(f"\n  Next: py preview_server.py {client_name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py tools/apply_art_direction.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
