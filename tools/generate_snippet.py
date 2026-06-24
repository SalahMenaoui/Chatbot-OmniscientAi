"""
generate_snippet.py
Generates the embeddable JavaScript snippet that a client pastes into their website
to add the chatbot as a floating widget.

Usage:
    python tools/generate_snippet.py <client_name> [--proxy-url URL] [--chatbot-url URL]

Options:
    --proxy-url   URL of the server-side proxy (e.g. https://api.yourdomain.com/api/chat)
    --chatbot-url URL where the chatbot/ folder is hosted (e.g. https://yourdomain.com/clients/acme/chatbot/)

Example:
    python tools/generate_snippet.py acme_bakery \\
        --proxy-url https://api.yourdomain.com/api/chat \\
        --chatbot-url https://yourdomain.com/clients/acme_bakery/chatbot/

Reads:   clients/<client_name>/chatbot/config.json
Writes:  clients/<client_name>/snippet.js
         clients/<client_name>/DELIVERY.md
"""

import sys
import json
import os
from datetime import datetime


SNIPPET_TEMPLATE = """\
/**
 * {bot_name} Chatbot Widget
 * Generated: {date}
 * Client: {client_name}
 *
 * INSTALLATION:
 * Paste this entire script tag just before </body> in your website's HTML.
 * Make sure to host the chatbot files and set CHATBOT_URL below.
 *
 * <script src="https://your-domain.com/chatbot/snippet.js"></script>
 */

(function () {{
  var CHATBOT_URL = "{chatbot_url}";  // ← UPDATE THIS to where you host the chatbot files
  var PRIMARY_COLOR = "{primary_color}";
  var BOT_NAME = "{bot_name}";
  var AVATAR_INITIAL = "{avatar_initial}";

  // Inject iframe styles
  var style = document.createElement("style");
  style.textContent = [
    "#chatbot-launcher {{",
    "  position: fixed; bottom: 24px; right: 24px; z-index: 99999;",
    "  width: 56px; height: 56px; border-radius: 50%;",
    "  background: " + PRIMARY_COLOR + "; color: #fff;",
    "  border: none; cursor: pointer; box-shadow: 0 4px 20px rgba(0,0,0,0.2);",
    "  font-size: 24px; display: flex; align-items: center; justify-content: center;",
    "  transition: transform 0.2s;",
    "}}",
    "#chatbot-launcher:hover {{ transform: scale(1.08); }}",
    "#chatbot-iframe-wrapper {{",
    "  display: none; position: fixed; bottom: 92px; right: 24px; z-index: 99998;",
    "  width: 420px; height: 620px; max-width: calc(100vw - 32px);",
    "  max-height: calc(100vh - 108px);",
    "  border-radius: 16px; overflow: hidden;",
    "  box-shadow: 0 8px 40px rgba(0,0,0,0.2);",
    "  animation: chatSlideIn 0.25s ease;",
    "}}",
    "@keyframes chatSlideIn {{",
    "  from {{ opacity: 0; transform: translateY(16px); }}",
    "  to   {{ opacity: 1; transform: translateY(0); }}",
    "}}",
    "#chatbot-iframe {{ width: 100%; height: 100%; border: none; }}",
  ].join("\\n");
  document.head.appendChild(style);

  // Create launcher button
  var btn = document.createElement("button");
  btn.id = "chatbot-launcher";
  btn.title = "Chat with " + BOT_NAME;
  btn.innerHTML = "&#x1F4AC;";
  document.body.appendChild(btn);

  // Create iframe wrapper
  var wrapper = document.createElement("div");
  wrapper.id = "chatbot-iframe-wrapper";

  var iframe = document.createElement("iframe");
  iframe.id = "chatbot-iframe";
  iframe.src = CHATBOT_URL;
  iframe.allow = "clipboard-write";
  wrapper.appendChild(iframe);
  document.body.appendChild(wrapper);

  // Toggle open/close
  var isOpen = false;
  btn.addEventListener("click", function () {{
    isOpen = !isOpen;
    wrapper.style.display = isOpen ? "block" : "none";
    btn.innerHTML = isOpen ? "&#x2715;" : "&#x1F4AC;";
    btn.title = isOpen ? "Close chat" : ("Chat with " + BOT_NAME);
  }});

  // Close on outside click
  document.addEventListener("click", function (e) {{
    if (isOpen && !wrapper.contains(e.target) && e.target !== btn) {{
      isOpen = false;
      wrapper.style.display = "none";
      btn.innerHTML = "&#x1F4AC;";
    }}
  }});
}})();
"""


def parse_args():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("client_name")
    p.add_argument("--proxy-url",   default=None, help="Production proxy URL")
    p.add_argument("--chatbot-url", default=None, help="URL where chatbot/ folder is hosted")
    return p.parse_args()


def run(client_name: str, proxy_url_override: str = None, chatbot_url_override: str = None) -> None:
    client_dir  = os.path.join("clients", client_name)
    config_path = os.path.join(client_dir, "chatbot", "config.json")
    output_path = os.path.join(client_dir, "snippet.js")

    if not os.path.exists(config_path):
        print(f"ERROR: {config_path} not found. Run apply_art_direction.py first.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    bot_name       = config.get("botName", client_name.replace("_", " ").title())
    primary_color  = config.get("colorPrimary") or config.get("primaryColor", "#2563eb")
    avatar_initial = config.get("avatarInitial", bot_name[0].upper())

    # Apply overrides to config.json if proxy URL was provided
    if proxy_url_override:
        config["proxyUrl"] = proxy_url_override
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"  Updated proxyUrl in config.json → {proxy_url_override}")

    chatbot_url = chatbot_url_override or f"https://YOUR_DOMAIN/clients/{client_name}/chatbot/"
    is_ready    = proxy_url_override and chatbot_url_override

    snippet = SNIPPET_TEMPLATE.format(
        bot_name       = bot_name,
        client_name    = client_name,
        date           = datetime.utcnow().strftime("%Y-%m-%d"),
        chatbot_url    = chatbot_url,
        primary_color  = primary_color,
        avatar_initial = avatar_initial,
        proxy_url      = config.get("proxyUrl", "/api/chat"),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(snippet)

    # Delivery instructions for SaaS model — the client just pastes the snippet
    delivery_path = os.path.join(client_dir, "DELIVERY.md")
    with open(delivery_path, "w", encoding="utf-8") as f:
        f.write(f"# Chatbot — Instructions d'installation\n\n")
        f.write(f"**Client :** {bot_name}  \n")
        f.write(f"**Date :** {datetime.utcnow().strftime('%Y-%m-%d')}  \n\n")
        f.write("---\n\n")
        f.write("## Une seule étape : coller le snippet\n\n")
        f.write("Demandez à votre développeur web (ou faites-le vous-même dans le CMS) ")
        f.write("de coller le code ci-dessous **juste avant la balise `</body>`** ")
        f.write("sur toutes les pages où vous voulez afficher le chatbot.\n\n")
        f.write(f"```html\n<script src=\"{chatbot_url}snippet.js\"></script>\n```\n\n")
        f.write("C'est tout. Le chatbot apparaîtra automatiquement en bas à droite de votre site.\n\n")
        f.write("---\n\n")
        f.write("## Ce qui est inclus\n\n")
        f.write(f"- Widget personnalisé aux couleurs de **{bot_name}**\n")
        f.write("- Assistant formé sur les informations de votre entreprise\n")
        f.write("- Hébergé et maintenu par nous — aucune maintenance de votre côté\n\n")
        f.write("---\n\n")
        f.write("## Questions ?\n\n")
        f.write("Contactez-nous et nous vous guiderons pas à pas.\n")

    print(f"[generate_snippet] Done.")
    print(f"  Snippet:  {output_path}")
    print(f"  Delivery: {delivery_path}")
    if not is_ready:
        print(f"\n  ⚠️  Placeholders actifs — relancer avec --proxy-url et --chatbot-url avant livraison.")
    else:
        print(f"\n  ✅ Prêt à livrer.")


if __name__ == "__main__":
    args = parse_args()
    run(args.client_name, args.proxy_url, args.chatbot_url)
