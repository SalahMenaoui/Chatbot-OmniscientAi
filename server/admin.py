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

    body = await request.json()
    url  = (body.get("url") or "").strip()
    if not url:
        return JSONResponse({"error": "URL manquante"}, status_code=400)

    import requests as req
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse
    import anthropic as _anthropic

    HEADERS  = {"User-Agent": "Mozilla/5.0 (compatible; OmniscientBot/1.0)"}
    MAX_PAGES = 8

    def _clean(t): return re.sub(r"\s+", " ", t).strip()

    def _scrape_page(page_url, session):
        try:
            r = session.get(page_url, headers=HEADERS, timeout=12)
            r.raise_for_status()
        except Exception:
            return {}
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header","noscript","iframe"]):
            tag.decompose()
        headings = [_clean(h.get_text()) for h in soup.find_all(["h1","h2","h3"]) if _clean(h.get_text())]
        paras    = [_clean(p.get_text()) for p in soup.find_all("p") if len(_clean(p.get_text())) > 40]
        meta_desc = ""
        m = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if m: meta_desc = m.get("content","")
        og_title = ""
        t = soup.find("meta", attrs={"property": "og:title"})
        if t: og_title = t.get("content","")
        title = _clean(soup.title.string) if soup.title else ""
        return {"url": page_url, "title": title, "og_title": og_title,
                "meta_desc": meta_desc, "headings": headings[:20], "paras": paras[:30]}

    def _crawl(base_url, session):
        domain  = urlparse(base_url).netloc
        visited = {base_url}
        queue   = [base_url]
        pages   = []
        while queue and len(pages) < MAX_PAGES:
            u = queue.pop(0)
            data = _scrape_page(u, session)
            if data: pages.append(data)
            try:
                r = session.get(u, headers=HEADERS, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = urljoin(base_url, a["href"]).split("#")[0].split("?")[0]
                    if urlparse(href).netloc == domain and href not in visited:
                        visited.add(href); queue.append(href)
            except Exception:
                pass
        return pages

    try:
        session = req.Session()
        pages   = _crawl(url, session)
    except Exception as e:
        return JSONResponse({"error": f"Scraping échoué : {e}"}, status_code=500)

    # Build compact text for Claude
    texts = []
    for p in pages:
        texts.append(f"PAGE: {p.get('title') or p.get('og_title','')}")
        if p.get("meta_desc"): texts.append(f"Description: {p['meta_desc']}")
        texts.extend(p.get("headings", []))
        texts.extend(p.get("paras", []))
    scraped_str = "\n".join(texts)[:50_000]

    META_PROMPT = """
Tu es un expert en configuration de chatbots d'entreprise. Voici le contenu scrapé du site web d'une entreprise.
Génère un objet JSON avec exactement ces clés :

1. "botName": Nom court du bot (ex: "Assistant Aqua Services"). Max 4 mots.
2. "systemPrompt": Un system prompt détaillé et personnalisé pour le chatbot. Inclure : identité du bot, services/produits avec prix si disponibles, heures, contact, ton de la marque, que faire si inconnu. Ne pas inventer de détails absents des données. En français si le site est en français.
3. "quickReplies": Tableau de 4 boutons courts (max 4 mots chacun) dans la langue du site.
4. "welcomeMessage": Message de bienvenue chaleureux (1-2 phrases), dans la langue du site.

Données scrapées :
---
{scraped}
---

Réponds uniquement avec du JSON valide. Aucune explication, aucun markdown.
""".strip()

    try:
        claude = _anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY",""))
        msg = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": META_PROMPT.format(scraped=scraped_str)}],
        )
        result = json.loads(msg.content[0].text.strip())
    except Exception as e:
        return JSONResponse({"error": f"Génération IA échouée : {e}"}, status_code=500)

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
