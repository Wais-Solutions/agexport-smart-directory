from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from utils.db_tools import db
import httpx
import os
import time
import re

router = APIRouter()

# ── Cache del token ICD ───────────────────────────────────────────────────────
_token_cache = {"token": None, "expires_at": 0}

async def get_icd_token():
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://icdaccessmanagement.who.int/connect/token",
            data={
                "client_id":     os.getenv("ICD_CLIENT_ID"),
                "client_secret": os.getenv("ICD_CLIENT_SECRET"),
                "scope":         "icdapi_access",
                "grant_type":    "client_credentials",
            },
        )
        data = res.json()
        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = now + 50 * 60
        return _token_cache["token"]


# ── Modelos ───────────────────────────────────────────────────────────────────

class Specialty(BaseModel):
    code: str
    title: str
    uri: Optional[str] = None

class SpecialtiesPayload(BaseModel):
    partner_id: str
    partner_name: str
    username: str
    specialties: List[Specialty]


# ── Búsqueda CIE-11 (debe ir ANTES de /{partner_id}) ─────────────────────────

@router.get("/search")
async def search_specialties(q: str):
    if not q or len(q.strip()) < 2:
        return {"results": []}

    token = await get_icd_token()

    async with httpx.AsyncClient() as client:
        res = await client.get(
            "https://id.who.int/icd/release/11/2026-01/mms/search",
            params={"q": q, "flatResults": "true", "highlighting": "false"},
            headers={
                "Authorization":   f"Bearer {token}",
                "API-Version":     "v2",
                "Accept-Language": "es",
                "Accept":          "application/json",
            },
        )
        data = res.json()

    results = []
    for entity in data.get("destinationEntities", []):
        code  = entity.get("theCode", "")
        title = entity.get("title", "")
        # Limpiar tags HTML del highlighting
        title = re.sub(r'<[^>]+>', '', title)
        if code and title:
            results.append({"code": code, "title": title})

    return {"results": results[:50]}


# ── GET especialidades de un partner ─────────────────────────────────────────

@router.get("/{partner_id}")
def get_specialties(partner_id: str):
    doc = db["specialties"].find_one({"partner_id": partner_id})
    if not doc:
        return {"partner_id": partner_id, "specialties": []}
    return {
        "partner_id":   doc["partner_id"],
        "partner_name": doc.get("partner_name"),
        "username":     doc.get("username"),
        "specialties":  doc.get("specialties", []),
        "updated_at":   doc.get("updated_at"),
    }


# ── POST guardar especialidades ───────────────────────────────────────────────

@router.post("/{partner_id}")
def save_specialties(partner_id: str, body: SpecialtiesPayload):
    db["specialties"].update_one(
        {"partner_id": partner_id},
        {"$set": {
            "partner_id":   partner_id,
            "partner_name": body.partner_name,
            "username":     body.username,
            "specialties":  [s.model_dump() for s in body.specialties],
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "saved": len(body.specialties)}