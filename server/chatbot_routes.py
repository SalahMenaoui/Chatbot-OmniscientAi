from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from server import models

router    = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/clients/{client_key}/chatbot/", response_class=HTMLResponse)
def chatbot_page(request: Request, client_key: str):
    client = models.get_client_by_key(client_key)
    if not client:
        return HTMLResponse("<h1>Client introuvable</h1>", status_code=404)
    return templates.TemplateResponse(request, "base_chatbot/index.html", {})


@router.get("/clients/{client_key}/chatbot/config.json")
def chatbot_config(client_key: str):
    client = models.get_client_by_key(client_key)
    if not client:
        return JSONResponse({"error": "not found"}, status_code=404)
    cfg = models.get_client_config(client_key)
    return JSONResponse(cfg)
