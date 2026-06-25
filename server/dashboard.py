import os
import csv
import io
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from server import models, auth

templates = Jinja2Templates(directory="templates")
router    = APIRouter()


def _cid(request: Request):
    return request.session.get("dashboard_client_id")


def _cname(request: Request):
    return request.session.get("dashboard_client_name", "")


def _ctier(request: Request) -> int:
    cid = _cid(request)
    if not cid:
        return 0
    with models.get_conn() as conn:
        row = conn.execute("SELECT tier FROM clients WHERE id = ?", (cid,)).fetchone()
    return dict(row)["tier"] if row else 0


@router.get("/dashboard/login", response_class=HTMLResponse)
def login_get(request: Request):
    if _cid(request):
        return RedirectResponse("/dashboard/", status_code=302)
    return templates.TemplateResponse(request, "dashboard/login.html", {"error": None})


@router.post("/dashboard/login", response_class=HTMLResponse)
def login_post(request: Request,
               email: str    = Form(...),
               password: str = Form(...)):
    user = auth.authenticate_dashboard_user(email, password)
    if not user:
        return templates.TemplateResponse(request, "dashboard/login.html",
                                          {"error": "Email ou mot de passe incorrect."})
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


_PERIOD_LABELS = {
    "1h":  "Dernière heure",
    "24h": "Dernières 24h",
    "7d":  "7 derniers jours",
    "30d": "30 derniers jours",
}

@router.get("/dashboard/", response_class=HTMLResponse)
def visitors(request: Request, q: str = "", period: str = ""):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    cid = _cid(request)
    return templates.TemplateResponse(request, "dashboard/visitors.html", {
        "visitors":     models.get_visitors(cid, search=q, period=period),
        "stats":        models.get_stats(cid, period=period),
        "activity":     models.get_daily_activity(cid, days=30),
        "search":       q,
        "period":       period,
        "period_label": _PERIOD_LABELS.get(period, "Total"),
        "client_name":  _cname(request),
        "client_tier":  _ctier(request),
        "active":       "visitors",
    })


@router.get("/dashboard/export.csv")
def export_csv(request: Request, q: str = "", period: str = ""):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    rows = models.get_visitors(_cid(request), search=q, period=period)
    buf  = io.StringIO()
    w    = csv.writer(buf)
    w.writerow(["Nom", "Email", "Messages", "Capturé le", "Dernière activité"])
    for v in rows:
        w.writerow([
            v["name"], v["email"], v["message_count"] or 0,
            (v["created_at"] or "")[:16],
            (v["last_seen"]  or "")[:16],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


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
    return templates.TemplateResponse(request, "dashboard/conversation.html", {
        "visitor":       visitor,
        "conversations": conversations,
        "client_name":   _cname(request),
        "client_tier":   _ctier(request),
        "active":        "visitors",
    })


@router.get("/dashboard/settings", response_class=HTMLResponse)
def settings_get(request: Request):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    if _ctier(request) < 3:
        return RedirectResponse("/dashboard/", status_code=302)
    return templates.TemplateResponse(request, "dashboard/settings.html", {
        "settings":    models.get_email_settings(_cid(request)),
        "client_name": _cname(request),
        "client_tier": 3,
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
    if _ctier(request) < 3:
        return RedirectResponse("/dashboard/", status_code=302)
    models.save_email_settings(
        _cid(request),
        enabled     = (enabled == "on"),
        delay_hours = max(1, min(168, delay_hours)),
        tone        = tone,
        from_name   = from_name.strip(),
        from_email  = from_email.strip(),
    )
    return templates.TemplateResponse(request, "dashboard/settings.html", {
        "settings":    models.get_email_settings(_cid(request)),
        "client_name": _cname(request),
        "client_tier": 3,
        "active":      "settings",
        "saved":       True,
    })


@router.get("/dashboard/emails", response_class=HTMLResponse)
def email_logs(request: Request):
    if not _cid(request):
        return RedirectResponse("/dashboard/login", status_code=302)
    if _ctier(request) < 3:
        return RedirectResponse("/dashboard/", status_code=302)
    return templates.TemplateResponse(request, "dashboard/email_logs.html", {
        "logs":        models.get_email_logs(_cid(request)),
        "client_name": _cname(request),
        "client_tier": 3,
        "active":      "emails",
    })
