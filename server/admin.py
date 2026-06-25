import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
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
def admin_config_post(
    request:        Request,
    client_key:     str,
    bot_name:       str = Form(...),
    system_prompt:  str = Form(...),
    welcome_message:str = Form(...),
    quick_replies:  str = Form(default=""),
    color_header_bg:str = Form(default="#1a1a2e"),
    color_primary:  str = Form(default="#6c63ff"),
):
    redir = _guard(request)
    if redir: return redir
    replies = [r.strip() for r in quick_replies.splitlines() if r.strip()]
    cfg = {
        "botName":        bot_name.strip(),
        "systemPrompt":   system_prompt.strip(),
        "welcomeMessage": welcome_message.strip(),
        "quickReplies":   replies,
        "colorHeaderBg":  color_header_bg.strip(),
        "colorPrimary":   color_primary.strip(),
        "proxyUrl":       "/api/chat",
    }
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
        auth.create_dashboard_user(client["id"], email, password)
    except Exception as e:
        msg = str(e).replace(" ", "+")
        return RedirectResponse(f"/admin/setup?error={msg}", status_code=302)
    return RedirectResponse("/admin/setup?created=1", status_code=302)
