"""
generate_system_prompt.py
Reads all scraped JSON files for a client and calls the Claude API
to generate a rich, personalized system prompt for their chatbot.

Usage:
    python tools/generate_system_prompt.py <client_name>

Example:
    python tools/generate_system_prompt.py acme_bakery

Reads:   clients/<client_name>/scraped_data.json
Writes:  clients/<client_name>/system_prompt.txt
Requires: ANTHROPIC_API_KEY in .env
"""

import sys
import json
import os

try:
    import anthropic
    from dotenv import load_dotenv
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install anthropic python-dotenv")
    sys.exit(1)


load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

META_PROMPT = """
You are an expert AI chatbot configurator. Based on the scraped business data below, produce a JSON object with exactly two keys:

1. "systemPrompt": A detailed, high-quality system prompt for the business chatbot. Guidelines:
   - Open with a clear identity statement: who the bot is, what business it represents.
   - List all services/products with any available pricing.
   - Include business hours, location, contact info.
   - Capture the business's tone and communication style from the data.
   - Instruct the bot to handle common questions proactively.
   - Include instructions for what to do when the bot doesn't know something (e.g., "invite the user to call or visit").
   - Use positive language that reflects the brand.
   - Keep it focused — do not hallucinate details not present in the data.
   - Format as plain paragraphs and bullet lists (no markdown headers).
   - End with a clear instruction on how to close conversations helpfully.

2. "quickReplies": An array of exactly 4 short button labels (max 4 words each) in the business's primary language. These are the most common things a visitor would want to ask. Examples: "Nos services", "Obtenir une soumission", "Zone desservie", "Notre équipe".

Scraped business data:
---
{scraped_data}
---

Respond with valid JSON only. No explanation, no markdown fences.
""".strip()


def run(client_name: str) -> None:
    if not API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client_dir = os.path.join("clients", client_name)
    input_path = os.path.join(client_dir, "scraped_data.json")
    output_path = os.path.join(client_dir, "system_prompt.txt")

    if not os.path.exists(input_path):
        print(f"ERROR: {input_path} not found. Run scrape_sources first.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        scraped_data = json.load(f)

    # Condense to a readable string (trim very long fields)
    scraped_str = json.dumps(scraped_data, ensure_ascii=False, indent=2)
    if len(scraped_str) > 60_000:
        scraped_str = scraped_str[:60_000] + "\n...[truncated]"

    print(f"[generate_system_prompt] Generating prompt for: {client_name}")
    print("  Calling Claude API... (this uses API credits)")

    client = anthropic.Anthropic(api_key=API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": META_PROMPT.format(scraped_data=scraped_str),
            }
        ],
    )

    raw = message.content[0].text.strip()

    try:
        parsed = json.loads(raw)
        system_prompt = parsed["systemPrompt"].strip()
        quick_replies = parsed.get("quickReplies", [])
    except Exception:
        # Fallback: treat entire response as system prompt
        system_prompt = raw
        quick_replies = []
        print("  [WARN] Could not parse JSON response — saving raw text as system prompt.")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(system_prompt)

    quick_replies_path = os.path.join(client_dir, "quick_replies.json")
    with open(quick_replies_path, "w", encoding="utf-8") as f:
        json.dump(quick_replies, f, ensure_ascii=False, indent=2)

    print(f"[generate_system_prompt] Done. Prompt written to: {output_path}")
    print(f"  Quick replies: {quick_replies}")
    print(f"  Tokens used — input: {message.usage.input_tokens}, output: {message.usage.output_tokens}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/generate_system_prompt.py <client_name>")
        sys.exit(1)
    run(sys.argv[1])
