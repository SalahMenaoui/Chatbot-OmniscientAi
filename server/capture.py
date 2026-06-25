from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from server import models

router = APIRouter()


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
    visitor_id, conversation_id = models.create_visitor(
        client["id"], req.name.strip(), req.email.strip()
    )
    return {"visitor_id": visitor_id, "conversation_id": conversation_id}


@router.get("/api/client-config/{client_key}")
def client_config(client_key: str):
    client = models.get_client_by_key(client_key)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return {"tier": client["tier"], "client_key": client_key}
