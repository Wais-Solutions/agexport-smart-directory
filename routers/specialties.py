from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from utils.db_tools import db
import httpx
import os
import time
import re
import asyncio
import openpyxl
import io

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


async def fetch_icd_results(client: httpx.AsyncClient, token: str, q: str, limit: int = 5):
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
        title = re.sub(r'<[^>]+>', '', entity.get("title", ""))
        if code and title:
            results.append({"code": code, "title": title})
        if len(results) >= limit:
            break
    return results


# ── Modelos ───────────────────────────────────────────────────────────────────

class Specialty(BaseModel):
    code: str
    title: str
    uri: Optional[str] = None

class SpecialtiesPayload(BaseModel):
    partner_id: str
    partner_name: str
    username: str
    cie: List[Specialty]


# ── Búsqueda CIE-11 ───────────────────────────────────────────────────────────

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
        title = re.sub(r'<[^>]+>', '', entity.get("title", ""))
        if code and title:
            results.append({"code": code, "title": title})

    return {"results": results[:50]}


# ── Sugerencias basadas en servicios del partner ──────────────────────────────

@router.get("/suggestions/{partner_id}")
async def get_suggestions(partner_id: str):
    partner = db["partners"].find_one({"_id": __import__("bson").ObjectId(partner_id)})
    if not partner:
        return {"suggestions": []}

    services = partner.get("partner_services", [])
    if not services:
        return {"suggestions": []}

    token = await get_icd_token()

    # Buscar en paralelo los servicios
    search_terms = services #[:3]
    seen_codes   = set()
    suggestions  = []

    async with httpx.AsyncClient() as client:
        tasks   = [fetch_icd_results(client, token, term, limit=3) for term in search_terms]
        results = await asyncio.gather(*tasks)

    for batch in results:
        for item in batch:
            if item["code"] not in seen_codes:
                seen_codes.add(item["code"])
                suggestions.append(item)
            if len(suggestions) >= 10:
                break
        if len(suggestions) >= 10:
            break

    return {"suggestions": suggestions, "based_on": search_terms}

# ── POST especialidades de excel de partner ─────────────────────────────────────────

@router.post("/import/{partner_id}")
async def import_from_excel(partner_id: str, file: UploadFile = File(...)):
    contents = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True)
    ws = wb.active

    codes = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        code = str(row[0]).strip() if row[0] else ""
        if code and code != "None":
            codes.append(code)

    if not codes:
        raise HTTPException(status_code=400, detail="No se encontraron códigos en el archivo")

    token = await get_icd_token()
    specialties = []
    not_found   = []

    async with httpx.AsyncClient() as client:
        for code in codes:
            try:
                # Primero obtenemos el stemId
                info_res = await client.get(
                    f"https://id.who.int/icd/release/11/2026-01/mms/codeinfo/{code}",
                    headers={
                        "Authorization":   f"Bearer {token}",
                        "API-Version":     "v2",
                        "Accept-Language": "es",
                        "Accept":          "application/json",
                    },
                )
                if info_res.status_code != 200:
                    not_found.append(code)
                    continue

                info_data = info_res.json()
                stem_id = info_data.get("stemId", "").replace("http://", "https://")

                if not stem_id:
                    not_found.append(code)
                    continue

                # Con el stemId obtenemos el título
                entity_res = await client.get(
                    stem_id,
                    headers={
                        "Authorization":   f"Bearer {token}",
                        "API-Version":     "v2",
                        "Accept-Language": "es",
                        "Accept":          "application/json",
                    },
                )
                if entity_res.status_code != 200:
                    not_found.append(code)
                    continue

                entity_data = entity_res.json()
                title_raw   = entity_data.get("title", {})
                title       = title_raw.get("@value", "") if isinstance(title_raw, dict) else str(title_raw)
                title       = re.sub(r'<[^>]+>', '', title).strip()

                if title:
                    specialties.append({"code": code, "title": title})
                else:
                    not_found.append(code)

            except Exception:
                not_found.append(code)

    return {
        "imported":  specialties,
        "not_found": not_found,
        "total":     len(codes),
    }

# ── GET especialidades de un partner ─────────────────────────────────────────

@router.get("/{partner_id}")
def get_specialties(partner_id: str):
    doc = db["specialties"].find_one({"partner_id": partner_id})
    if not doc:
        return {"partner_id": partner_id, "cie": []}
    return {
        "partner_id":   doc["partner_id"],
        "partner_name": doc.get("partner_name"),
        "username":     doc.get("username"),
        "cie":          doc.get("cie", []),
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
            "cie":          [s.model_dump() for s in body.cie],
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "saved": len(body.cie)}