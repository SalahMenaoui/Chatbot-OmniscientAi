import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server import models

router = APIRouter()

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def _validate_email(email: str) -> str | None:
    """Return error message string if invalid, None if OK."""
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return "Format d'email invalide."
    domain = email.split("@")[1]
    try:
        import dns.resolver
        dns.resolver.resolve(domain, "MX")
    except Exception as e:
        err = str(e)
        if "NXDOMAIN" in err or "NoNameservers" in err:
            return f"Le domaine '{domain}' n'existe pas."
        if "NoAnswer" in err:
            return f"'{domain}' ne peut pas recevoir d'emails."
        # Network timeout or other transient error — let it through
    return None


class CaptureRequest(BaseModel):
    client_key: str
    name: str
    email: str


@router.post("/api/capture")
def capture(req: CaptureRequest):
    client = models.get_client_by_key(req.client_key)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    if client["tier"] < 2:
        raise HTTPException(status_code=403, detail="Capture not enabled for this client.")
    if not req.name.strip() or not req.email.strip():
        raise HTTPException(status_code=400, detail="Name and email are required.")

    email_error = _validate_email(req.email)
    if email_error:
        raise HTTPException(status_code=422, detail=email_error)

    visitor_id, conversation_id = models.create_visitor(
        client["id"], req.name.strip(), req.email.strip().lower()
    )
    return {"visitor_id": visitor_id, "conversation_id": conversation_id}


@router.get("/api/client-config/{client_key}")
def client_config(client_key: str):
    client = models.get_client_by_key(client_key)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return {"tier": client["tier"], "client_key": client_key}
