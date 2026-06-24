"""
preview_server.py
Local preview server for testing a client chatbot before deployment.
Serves static files + handles /api/chat by proxying to the Anthropic API.

Usage:
    py preview_server.py <client_name> [port]

Example:
    py preview_server.py watches_by_sl
    py preview_server.py watches_by_sl 8080

Then open: http://localhost:8000
"""

import sys
import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    print("ERROR: Run: pip install anthropic python-dotenv")
    sys.exit(1)

load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

if not API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set in .env")
    sys.exit(1)

client_name = sys.argv[1] if len(sys.argv) > 1 else None
port        = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

if not client_name:
    print("Usage: py preview_server.py <client_name> [port]")
    sys.exit(1)

chatbot_dir = os.path.join("clients", client_name, "chatbot")
if not os.path.isdir(chatbot_dir):
    print(f"ERROR: {chatbot_dir} not found. Run inject_prompt.py first.")
    sys.exit(1)

# Load config to get model/maxTokens
config_path = os.path.join(chatbot_dir, "config.json")
with open(config_path, "r", encoding="utf-8-sig") as f:
    config = json.load(f)

model      = config.get("model", "claude-haiku-4-5-20251001")
max_tokens = config.get("maxTokens", 1024)

anthropic_client = anthropic.Anthropic(api_key=API_KEY)


class ChatbotHandler(SimpleHTTPRequestHandler):

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length))

            try:
                response = anthropic_client.messages.create(
                    model      = body.get("model", model),
                    max_tokens = body.get("max_tokens", max_tokens),
                    system     = body.get("system", "You are a helpful assistant."),
                    messages   = body.get("messages", []),
                )
                result = {
                    "content": [{"text": response.content[0].text}]
                }
                self._respond(200, result)
            except Exception as e:
                self._respond(500, {"error": {"message": str(e)}})
        else:
            self.send_response(404)
            self.end_headers()

    def _respond(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # Prevent browser from caching config.json and other assets between clients
        if self.path.endswith(".json") or self.path.startswith("/config.json"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"  [{self.command}] {self.path}")


# Serve from the chatbot directory
os.chdir(chatbot_dir)

print(f"")
print(f"  {config.get('botName', client_name)} — Chatbot Preview")
print(f"  Open in your browser: http://localhost:{port}")
print(f"  Press Ctrl+C to stop.")
print(f"")

HTTPServer(("", port), ChatbotHandler).serve_forever()
