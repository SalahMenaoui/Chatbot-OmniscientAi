import os
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from server import models, auth

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
router    = APIRouter()


def _cid(request: Request):
    return request.session.get("dashboard_client_id")


def _cname(request: Request):
    return request.session.get("dashboard_client_name", "")


@router.get("/dashboard/login", response_class=HTMLResponse)
def login_get(request: Request):
    if _cid(request):
        return RedirectResponse("/dashboard/", status_code=302)
    return templates.TemplateResponse("dashboard/login.html",
                                      {"request": request, "error": None})


@router.post("/dashboard/login", response_class=HTMLResponse)
def login_post(request: Request,
               email: str    = Form(...),
               password: str = Form(...)):
    user = auth.authenticate_dashboard_user(email, password)
    if not user:
        return templates.TemplateResponse("dashboard/login.html",
                                          {"request": request,
                                           "error": "Email ou mot de passe incorrect."})
    with models.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (user["client_id"],)
        ).fetchone()
    client = dict(row) if row else {}
    request.session["dashboard_client_id"]   = user["client_id"]
    request.session["dashboard_client_name"] = client.get("name", "")
    return RedirectResponse("/dashboard/", status_code=302)


@router.get("/dashboard/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/dashboard/login", status_code=302)


@router.get("/dashboard/", response_class=HTMLResponse)
def visitors(request: Request, q: str = ""):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    return templates.TemplateResponse("dashboard/visitors.html", {
        "request":     request,
        "visitors":    models.get_visitors(_cid(request), search=q),
        "search":      q,
        "client_name": _cname(request),
        "active":      "visitors",
    })


@router.get("/dashboard/visitor/{visitor_id}", response_class=HTMLResponse)
def visitor_detail(request: Request, visitor_id: int):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    visitor = models.get_visitor(visitor_id, _cid(request))
    if not visitor:
        return RedirectResponse("/dashboard/", status_code=302)
    conversations = models.get_conversations(visitor_id)
    for conv in conversations:
        conv["messages"] = models.get_messages(conv["id"])
    return templates.TemplateResponse("dashboard/conversation.html", {
        "request":       request,
        "visitor":       visitor,
        "conversations": conversations,
        "client_name":   _cname(request),
        "active":        "visitors",
    })


@router.get("/dashboard/settings", response_class=HTMLResponse)
def settings_get(request: Request):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    return templates.TemplateResponse("dashboard/settings.html", {
        "request":     request,
        "settings":    models.get_email_settings(_cid(request)),
        "client_name": _cname(request),
        "active":      "settings",
        "saved":       False,
    })


@router.post("/dashboard/settings", response_class=HTMLResponse)
def settings_post(request: Request,
                  enabled:     str = Form(default="off"),
                  delay_hours: int = Form(default=24),
                  tone:        str = Form(default="professional"),
                  from_name:   str = Form(default=""),
                  from_email:  str = Form(default="")):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    models.save_email_settings(
        _cid(request),
        enabled     = (enabled == "on"),
        delay_hours = max(1, min(168, delay_hours)),
        tone        = tone,
        from_name   = from_name.strip(),
        from_email  = from_email.strip(),
    )
    return templates.TemplateResponse("dashboard/settings.html", {
        "request":     request,
        "settings":    models.get_email_settings(_cid(request)),
        "client_name": _cname(request),
        "active":      "settings",
        "saved":       True,
    })


@router.get("/dashboard/emails", response_class=HTMLResponse)
def email_logs(request: Request):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    return templates.TemplateResponse("dashboard/email_logs.html", {
        "request":     request,
        "logs":        models.get_email_logs(_cid(request)),
        "client_name": _cname(request),
        "active":      "emails",
    })
