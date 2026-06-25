import os
import json
import re
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from server import models, auth

templates      = Jinja2Templates(directory="templates")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
router         = APIRouter()


def _guard(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse("/admin", status_code=302)


@router.get("/admin", response_class=HTMLResponse)
def admin_login_get(request: Request):
    if request.session.get("is_admin"):
        return RedirectResponse("/admin/clients", status_code=302)
    return templates.TemplateResponse(request, "admin/login.html", {"error": None})


@router.post("/admin", response_class=HTMLResponse)
def admin_login_post(request: Request, password: str = Form(...)):
    if not ADMIN_PASSWORD or password != ADMIN_PASSWORD:
        return templates.TemplateResponse(request, "admin/login.html",
                                          {"error": "Mot de passe incorrect."})
    request.session["is_admin"] = True
    return RedirectResponse("/admin/clients", status_code=302)


@router.get("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return RedirectResponse("/admin", status_code=302)


@router.get("/admin/clients", response_class=HTMLResponse)
def admin_clients(request: Request, created: str = "", error: str = ""):
    redir = _guard(request)
    if redir: return redir
    return templates.TemplateResponse(request, "admin/clients.html",
                                      {"clients": models.get_all_clients(),
                                       "created": created, "error": error})


@router.post("/admin/clients/{client_key}/create-user")
def admin_create_user(request: Request, client_key: str,
                      email: str = Form(...), password: str = Form(...)):
    redir = _guard(request)
    if redir: return redir
    client = models.get_client_by_key(client_key)
    if not client:
        return RedirectResponse("/admin/clients?error=Client+introuvable", status_code=302)
    try:
        auth.create_dashboard_user(client_key, email, password)
    except Exception as e:
        msg = str(e).replace(" ", "+")
        return RedirectResponse(f"/admin/clients?error={msg}", status_code=302)
    return RedirectResponse("/admin/clients?created=1", status_code=302)


@router.post("/admin/clients/{client_key}/rename")
def admin_rename_client(request: Request, client_key: str, name: str = Form(...)):
    redir = _guard(request)
    if redir: return redir
    models.rename_client(client_key, name)
    return RedirectResponse("/admin/clients", status_code=302)


@router.post("/admin/clients/{client_key}/delete")
def admin_delete_client(request: Request, client_key: str):
    redir = _guard(request)
    if redir: return redir
    models.delete_client(client_key)
    return RedirectResponse("/admin/clients", status_code=302)


@router.post("/admin/clients/{client_key}/tier")
def admin_set_tier(request: Request, client_key: str, tier: int = Form(...)):
    redir = _guard(request)
    if redir: return redir
    models.set_client_tier(client_key, max(1, min(3, tier)))
    return RedirectResponse("/admin/clients", status_code=302)


# ── Setup page ────────────────────────────────────────────────────────────────

@router.get("/admin/setup", response_class=HTMLResponse)
def admin_setup_get(request: Request, seeded: str = "", created: str = "", added: str = "", error: str = ""):
    redir = _guard(request)
    if redir: return redir
    return templates.TemplateResponse(request, "admin/setup.html", {
        "clients":         models.get_all_clients(),
        "dashboard_users": models.get_dashboard_users(),
        "seeded":          seeded,
        "created":         created,
        "added":           added,
        "error":           error,
    })


@router.post("/admin/api/scrape")
async def admin_scrape(request: Request):
    redir = _guard(request)
    if redir:
        return JSONResponse({"error": "Non authentifié"}, status_code=401)

    body          = await request.json()
    website_url   = (body.get("website") or body.get("url") or "").strip()
    instagram_url = (body.get("instagram") or "").strip()
    googlemaps_url= (body.get("googlemaps") or "").strip()

    if not website_url:
        return JSONResponse({"error": "URL du site web manquante"}, status_code=400)

    try:
        from server.scraper import run as scraper_run
        import asyncio
        result = await asyncio.to_thread(scraper_run, website_url, instagram_url, googlemaps_url)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse(result)


@router.post("/admin/setup/seed")
def admin_setup_seed(request: Request):
    redir = _guard(request)
    if redir: return redir
    models.seed_known_clients()
    return RedirectResponse("/admin/setup?seeded=1", status_code=302)


@router.post("/admin/clients/new")
def admin_new_client(
    request:    Request,
    name:       str = Form(...),
    client_key: str = Form(...),
):
    redir = _guard(request)
    if redir: return redir
    key = client_key.strip()
    try:
        models.create_client(name.strip(), key)
    except Exception as e:
        msg = str(e).replace(" ", "+")
        return RedirectResponse(f"/admin/setup?error={msg}", status_code=302)
    return RedirectResponse(f"/admin/clients/{key}/config?added=1", status_code=302)


@router.get("/admin/clients/{client_key}/config", response_class=HTMLResponse)
def admin_config_get(request: Request, client_key: str, added: str = "", saved: str = ""):
    redir = _guard(request)
    if redir: return redir
    client = models.get_client_by_key(client_key)
    if not client:
        return RedirectResponse("/admin/clients", status_code=302)
    cfg = models.get_client_config(client_key)
    return templates.TemplateResponse(request, "admin/client_config.html", {
        "client": client, "cfg": cfg, "added": added, "saved": saved,
    })


@router.post("/admin/clients/{client_key}/config")
async def admin_config_post(request: Request, client_key: str):
    redir = _guard(request)
    if redir: return redir

    form = await request.form()

    def f(key, default=""):
        return (form.get(key) or default).strip()

    replies = [r.strip() for r in f("quick_replies").splitlines() if r.strip()]

    cfg = {
        "botName":              f("bot_name"),
        "systemPrompt":         f("system_prompt"),
        "welcomeMessage":       f("welcome_message"),
        "quickReplies":         replies,
        "placeholder":          f("placeholder"),
        "avatarInitial":        f("avatar_initial"),
        "avatarUrl":            f("avatar_url"),
        "colorHeaderBg":        f("color_header_bg",       "#1a1a2e"),
        "colorPrimary":         f("color_primary",          "#6c63ff"),
        "colorPrimaryDark":     f("color_primary_dark",     ""),
        "colorPrimaryContrast": f("color_primary_contrast", "#ffffff"),
        "colorBg":              f("color_bg",               "#ffffff"),
        "colorSurface":         f("color_surface",          "#f8f8f8"),
        "colorBotBubble":       f("color_bot_bubble",       "#f0f0f0"),
        "colorBotText":         f("color_bot_text",         "#1a1a1a"),
        "colorUserBubble":      f("color_user_bubble",      ""),
        "colorUserText":        f("color_user_text",        "#ffffff"),
        "colorHeaderText":      f("color_header_text",      "#ffffff"),
        "colorHeaderSubtext":   f("color_header_subtext",   "rgba(255,255,255,0.7)"),
        "fontFamily":           f("font_family"),
        "googleFontsUrl":       f("google_fonts_url"),
        "radiusBubble":         f("radius_bubble",          "18px"),
        "radiusInput":          f("radius_input",           "12px"),
        "radiusSend":           f("radius_send",            "10px"),
        "proxyUrl":             "/api/chat",
    }
    # Clean empty optional values
    cfg = {k: v for k, v in cfg.items() if v != ""}
    cfg["proxyUrl"] = "/api/chat"

    models.save_client_config(client_key, cfg)
    return RedirectResponse(f"/admin/clients/{client_key}/config?saved=1", status_code=302)


@router.post("/admin/setup/user")
def admin_setup_user(
    request:   Request,
    client_id: int = Form(...),
    email:     str = Form(...),
    password:  str = Form(...),
):
    redir = _guard(request)
    if redir: return redir
    with models.get_conn() as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    client = dict(row) if row else None
    if not client:
        return RedirectResponse("/admin/setup?error=Client+introuvable", status_code=302)
    try:
        auth.create_dashboard_user(client["client_key"], email, password)
    except Exception as e:
        msg = str(e).replace(" ", "+")
        return RedirectResponse(f"/admin/setup?error={msg}", status_code=302)
    return RedirectResponse("/admin/setup?created=1", status_code=302)
