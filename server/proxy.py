"""
proxy.py — Central API proxy + server entrypoint.
Forwards chat requests to Anthropic, logs messages for Tier 2+ clients,
and mounts the dashboard, admin, and capture routers.
"""

import os
import logging
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import anthropic
from dotenv import load_dotenv

from server import models
from server.capture import router as capture_router
from server.dashboard import router as dashboard_router
from server.admin import router as admin_router
from server.email_worker import start_scheduler

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

models.init_db()

app = FastAPI(title="Chatbot Proxy")

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "change-me-in-production"),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
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
DEFAULT_MODEL  = "claude-haiku-4-5-20251001"
MAX_TOKENS_CAP = 2048


@app.on_event("startup")
async def startup():
    start_scheduler()


app.include_router(capture_router)
app.include_router(dashboard_router)
app.include_router(admin_router)


@app.post("/api/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    model           = body.get("model", DEFAULT_MODEL)
    max_tokens      = min(int(body.get("max_tokens", 1024)), MAX_TOKENS_CAP)
    system          = body.get("system", "")
    messages        = body.get("messages", [])
    conversation_id = body.get("conversation_id")

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

    reply = response.content[0].text if response.content else ""

    if conversation_id:
        try:
            user_content = messages[-1].get("content", "") if messages else ""
            models.log_message(int(conversation_id), "user",      user_content)
            models.log_message(int(conversation_id), "assistant", reply)
        except Exception as e:
            log.warning("Message logging failed: %s", e)

    return JSONResponse(content=response.model_dump())


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(status_code=500, content={"error": repr(exc), "trace": traceback.format_exc()})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/clients")
async def debug_clients():
    from server import models
    return {"clients": models.get_all_clients()}


@app.get("/debug/env")
async def debug_env():
    import sys, os
    cwd = os.getcwd()
    tmpl_rel = os.path.exists("templates")
    tmpl_abs = os.path.join(cwd, "templates")
    try:
        import jinja2
        jinja2_ver = jinja2.__version__
    except ImportError:
        jinja2_ver = "NOT INSTALLED"
    try:
        import itsdangerous
        itsd_ver = itsdangerous.__version__
    except ImportError:
        itsd_ver = "NOT INSTALLED"
    try:
        import bcrypt
        bcrypt_ver = bcrypt.__version__
    except Exception:
        bcrypt_ver = "NOT INSTALLED"
    admin_login = os.path.exists("templates/admin/login.html")
    dash_login  = os.path.exists("templates/dashboard/login.html")
    try:
        from fastapi.templating import Jinja2Templates as J2T
        t = J2T(directory="templates")
        t.get_template("admin/login.html")
        render_ok = True
        render_err = None
    except Exception as exc:
        render_ok  = False
        render_err = repr(exc)
    return {
        "cwd": cwd,
        "templates_relative_exists": tmpl_rel,
        "templates_abs_path": tmpl_abs,
        "admin_login_html": admin_login,
        "dashboard_login_html": dash_login,
        "jinja2": jinja2_ver,
        "itsdangerous": itsd_ver,
        "bcrypt": bcrypt_ver,
        "python": sys.version,
        "template_render_ok": render_ok,
        "template_render_err": render_err,
    }


clients_dir = os.path.join(os.path.dirname(__file__), "..", "clients")
if os.path.isdir(clients_dir):
    app.mount("/clients", StaticFiles(directory=clients_dir, html=True), name="clients")
