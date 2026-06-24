"""
proxy.py
Server-side API proxy for all chatbot widgets.
Receives requests from client browsers and forwards them to the Anthropic API.
The API key never leaves this server.

Deploy once — all client chatbots point to this single endpoint.

Usage (local):
    pip install -r requirements.txt
    uvicorn proxy:app --host 0.0.0.0 --port 8080

Production: deploy to Railway, Render, or any VPS.
Set ANTHROPIC_API_KEY as an environment variable on the host.
"""

import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import anthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Chatbot Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if not api_key:
    raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

claude = anthropic.Anthropic(api_key=api_key)

ALLOWED_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
}
DEFAULT_MODEL   = "claude-haiku-4-5-20251001"
MAX_TOKENS_CAP  = 2048


@app.post("/api/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    model      = body.get("model", DEFAULT_MODEL)
    max_tokens = min(int(body.get("max_tokens", 1024)), MAX_TOKENS_CAP)
    system     = body.get("system", "")
    messages   = body.get("messages", [])

    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL

    if not messages:
        raise HTTPException(status_code=400, detail="messages array is required.")

    log.info("chat model=%s tokens=%d messages=%d", model, max_tokens, len(messages))

    response = claude.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )

    return JSONResponse(content=response.model_dump())


@app.get("/health")
async def health():
    return {"status": "ok"}
