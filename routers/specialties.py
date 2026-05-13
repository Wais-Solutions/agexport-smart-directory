from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from utils.db_tools import db

router = APIRouter()

class Specialty(BaseModel):
    code: str
    title: str
    uri: str

class SpecialtiesPayload(BaseModel):
    partner_id: str
    partner_name: str
    username: str
    specialties: List[Specialty]

@router.get("/{partner_id}")
def get_specialties(partner_id: str):
    doc = db["specialties"].find_one({"partner_id": partner_id})
    if not doc:
        return {"partner_id": partner_id, "specialties": []}
    return {
        "partner_id": doc["partner_id"],
        "partner_name": doc.get("partner_name"),
        "username": doc.get("username"),
        "specialties": doc.get("specialties", []),
        "updated_at": doc.get("updated_at"),
    }

@router.post("/{partner_id}")
def save_specialties(partner_id: str, body: SpecialtiesPayload):
    db["specialties"].update_one(
        {"partner_id": partner_id},
        {"$set": {
            "partner_id": partner_id,
            "partner_name": body.partner_name,
            "username": body.username,
            "specialties": [s.model_dump() for s in body.specialties],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "saved": len(body.specialties)}