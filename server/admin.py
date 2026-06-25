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
    return templates.TemplateResponse("admin/login.html",
                                      {"request": request, "error": None})


@router.post("/admin", response_class=HTMLResponse)
def admin_login_post(request: Request, password: str = Form(...)):
    if not ADMIN_PASSWORD or password != ADMIN_PASSWORD:
        return templates.TemplateResponse("admin/login.html",
                                          {"request": request,
                                           "error": "Mot de passe incorrect."})
    request.session["is_admin"] = True
    return RedirectResponse("/admin/clients", status_code=302)


@router.get("/admin/logout")
def admin_logout(request: Request):
    request.session.pop("is_admin", None)
    return RedirectResponse("/admin", status_code=302)


@router.get("/admin/clients", response_class=HTMLResponse)
def admin_clients(request: Request):
    redir = _guard(request)
    if redir: return redir
    return templates.TemplateResponse("admin/clients.html",
                                      {"request": request,
                                       "clients": models.get_all_clients()})


@router.post("/admin/clients/{client_key}/tier")
def admin_set_tier(request: Request, client_key: str, tier: int = Form(...)):
    redir = _guard(request)
    if redir: return redir
    models.set_client_tier(client_key, max(1, min(3, tier)))
    return RedirectResponse("/admin/clients", status_code=302)


# ── Setup page ────────────────────────────────────────────────────────────────

@router.get("/admin/setup", response_class=HTMLResponse)
def admin_setup_get(request: Request, seeded: str = "", created: str = "", error: str = ""):
    redir = _guard(request)
    if redir: return redir
    return templates.TemplateResponse("admin/setup.html", {
        "request":        request,
        "clients":        models.get_all_clients(),
        "dashboard_users": models.get_dashboard_users(),
        "seeded":         seeded,
        "created":        created,
        "error":          error,
    })


@router.post("/admin/setup/seed")
def admin_setup_seed(request: Request):
    redir = _guard(request)
    if redir: return redir
    models.seed_known_clients()
    return RedirectResponse("/admin/setup?seeded=1", status_code=302)


@router.post("/admin/setup/user")
def admin_setup_user(
    request:    Request,
    client_key: str = Form(...),
    email:      str = Form(...),
    password:   str = Form(...),
):
    redir = _guard(request)
    if redir: return redir
    client = models.get_client_by_key(client_key)
    if not client:
        return RedirectResponse("/admin/setup?error=Client+introuvable", status_code=302)
    try:
        auth.create_dashboard_user(client["id"], email, password)
    except Exception as e:
        msg = str(e).replace(" ", "+")
        return RedirectResponse(f"/admin/setup?error={msg}", status_code=302)
    return RedirectResponse("/admin/setup?created=1", status_code=302)
