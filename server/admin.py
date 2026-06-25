import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from server import models

BASE_DIR       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates      = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
router         = APIRouter()


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
    if not request.session.get("is_admin"):
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("admin/clients.html",
                                      {"request": request,
                                       "clients": models.get_all_clients()})


@router.post("/admin/clients/{client_key}/tier")
def admin_set_tier(request: Request, client_key: str, tier: int = Form(...)):
    if not request.session.get("is_admin"):
        return RedirectResponse("/admin", status_code=302)
    models.set_client_tier(client_key, max(1, min(3, tier)))
    return RedirectResponse("/admin/clients", status_code=302)
