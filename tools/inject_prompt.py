"""
inject_prompt.py
Copies the base chatbot template into a client's folder and injects
the generated system prompt into config.json.

Usage:
    python tools/inject_prompt.py <client_name>

Example:
    python tools/inject_prompt.py acme_bakery

Reads:
  - templates/base_chatbot/          (source template)
  - clients/<client_name>/system_prompt.txt
  - clients/<client_name>/scraped_data.json  (for bot name, colors if available)

Writes:
  - clients/<client_name>/chatbot/   (full copy of template with injected config)
"""

import sys
import json
import os
import shutil


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _detect_language(scraped: dict) -> str:
    """Return 'fr' or 'en' based on website text content."""
    fr_markers = ["bonjour", "nous offrons", "nos services", "contactez", "soumission",
                  "accueil", "à propos", "entreprise", "devis", "bienvenue", "appelez"]
    text = ""
    for page in scraped.get("website", {}).get("pages", []):
        text += page.get("text", "").lower()
    if not text:
        text = str(scraped).lower()
    fr_count = sum(text.count(w) for w in fr_markers)
    return "fr" if fr_count >= 2 else "en"


def run(client_name: str) -> None:
    template_dir = os.path.join("templates", "base_chatbot")
    client_dir   = os.path.join("clients", client_name)
    output_dir   = os.path.join(client_dir, "chatbot")
    prompt_path       = os.path.join(client_dir, "system_prompt.txt")
    scraped_path      = os.path.join(client_dir, "scraped_data.json")
    quick_replies_path = os.path.join(client_dir, "quick_replies.json")

    # Validate inputs
    if not os.path.isdir(template_dir):
        print(f"ERROR: Template not found at {template_dir}")
        sys.exit(1)

    if not os.path.exists(prompt_path):
        print(f"ERROR: system_prompt.txt not found at {prompt_path}")
        print("  Run generate_system_prompt.py first.")
        sys.exit(1)

    # Copy template
    if os.path.exists(output_dir):
        print(f"[inject_prompt] WARNING: {output_dir} already exists — overwriting.")
        shutil.rmtree(output_dir)

    shutil.copytree(template_dir, output_dir)
    print(f"[inject_prompt] Copied template -> {output_dir}")

    # Load system prompt
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read().strip()

    # Load existing config
    config_path = os.path.join(output_dir, "config.json")
    config = load_json(config_path)

    # Try to infer bot name from scraped data
    scraped = load_json(scraped_path)
    bot_name = (
        scraped.get("google_maps", {}).get("name", "")
        or scraped.get("instagram", {}).get("full_name", "")
        or client_name.replace("_", " ").title()
    )

    # Detect language from website content (default to French if any French detected)
    lang = _detect_language(scraped)

    # Welcome message per language
    if lang == "fr":
        welcome = f"Bonjour ! Je suis l'assistant virtuel de {bot_name}. Comment puis-je vous aider ?"
    else:
        welcome = f"Hi! I'm the virtual assistant for {bot_name}. How can I help you today?"

    # Auto-detect and copy logo from assets/
    logo_src = os.path.join(client_dir, "assets", "logo_cropped.png")
    logo_dst = os.path.join(output_dir, "logo.png")
    avatar_url = None
    if os.path.exists(logo_src):
        shutil.copy2(logo_src, logo_dst)
        avatar_url = "logo.png"
        print(f"[inject_prompt] Logo copied: assets/logo_cropped.png -> chatbot/logo.png")

    # Inject
    config["systemPrompt"]    = system_prompt
    config["botName"]         = bot_name
    config["placeholder"]     = "Votre message..." if lang == "fr" else "Your message..."
    config["avatarInitial"]   = bot_name[0].upper() if bot_name else "A"
    config["welcomeMessage"]  = welcome
    if avatar_url:
        config["avatarUrl"]   = avatar_url

    # Load quick replies if available
    if os.path.exists(quick_replies_path):
        with open(quick_replies_path, "r", encoding="utf-8") as f:
            quick_replies = json.load(f)
        if quick_replies:
            config["quickReplies"] = quick_replies

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"[inject_prompt] Injected system prompt into config.json")
    print(f"[inject_prompt] Bot name set to: {bot_name}")

    # Flag for manual review
    review_path = os.path.join(client_dir, "REVIEW_NEEDED.md")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(f"# Manual Review Checklist — {client_name}\n\n")
        f.write("Before proceeding to QA, review the following:\n\n")
        f.write("- [ ] Open `chatbot/config.json` and verify the system prompt reads naturally\n")
        f.write("- [ ] Check `botName` and `welcomeMessage` are correct\n")
        f.write("- [ ] Adjust `primaryColor` / `secondaryColor` to match brand colors\n")
        f.write("- [ ] Remove any hallucinated details from the system prompt\n")
        f.write("- [ ] Add any missing info the scraper may have missed\n")
        f.write("- [ ] Verify contact info (phone, email, address) is accurate\n")
        f.write("- [ ] Set `proxyUrl` in config.json to the client's server endpoint\n\n")
        f.write("Once satisfied, delete this file and run workflows/qa_chatbot.md.\n")

    print(f"[inject_prompt] Review checklist created: {review_path}")
    print(f"[inject_prompt] Done.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/inject_prompt.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
