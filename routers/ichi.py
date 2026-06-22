from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from utils.db_tools import db
import openpyxl
import io

router = APIRouter()


# ── Modelos ───────────────────────────────────────────────────────────────────

class ICHIClass(BaseModel):
    code: str
    title: str

class ICHIPayload(BaseModel):
    partner_id:   str
    partner_name: str
    username:     str
    ichi_classes: List[ICHIClass]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _doc_to_ichi_class(doc: dict) -> Optional[dict]:
    """Convierte un documento de la colección 'ichi' al formato {code, title}."""
    code  = doc.get("code") or doc.get("block_id")
    title = doc.get("titulo_limpio_es") or doc.get("titulo_limpio") or doc.get("titulo") or ""
    if not code or not title:
        return None
    return {"code": code, "title": title}


# ── GET: buscar en colección ichi (índice $text sobre titulo_limpio) ────────

@router.get("/search")
def search_ichi(q: str):
    if not q or len(q.strip()) < 2:
        return {"results": []}

    cursor = db["ichi"].find(
        {"$text": {"$search": q.strip()}},
        {"_id": 0, "code": 1, "block_id": 1, "titulo_limpio_es": 1, "titulo_limpio": 1, "titulo": 1,
         "score": {"$meta": "textScore"}},
    ).sort([("score", {"$meta": "textScore"})]).limit(50)

    results = []
    for doc in cursor:
        item = _doc_to_ichi_class(doc)
        if item:
            results.append(item)

    return {"results": results}


# ── GET: sugerencias basadas en servicios del partner ────────────────────────

@router.get("/suggestions/{partner_id}")
def get_suggestions(partner_id: str):
    import bson
    try:
        partner = db["partners"].find_one({"_id": bson.ObjectId(partner_id)})
    except Exception:
        return {"suggestions": [], "based_on": []}

    if not partner:
        return {"suggestions": [], "based_on": []}

    services = partner.get("partner_services", [])
    if not services:
        return {"suggestions": [], "based_on": []}

    seen_codes  = set()
    suggestions = []

    for term in services:
        cursor = db["ichi"].find(
            {"$text": {"$search": term.strip()}},
            {"_id": 0, "code": 1, "block_id": 1, "titulo_limpio_es": 1, "titulo_limpio": 1, "titulo": 1,
             "score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(3)

        for doc in cursor:
            item = _doc_to_ichi_class(doc)
            if item and item["code"] not in seen_codes:
                seen_codes.add(item["code"])
                suggestions.append(item)
            if len(suggestions) >= 10:
                break
        if len(suggestions) >= 10:
            break

    return {"suggestions": suggestions, "based_on": services}


# ── GET: obtener ichi_classes guardadas de un partner ────────────────────────

@router.get("/{partner_id}")
def get_ichi(partner_id: str):
    doc = db["specialties"].find_one({"partner_id": partner_id})
    if not doc:
        return {"partner_id": partner_id, "ichi_classes": []}
    return {
        "partner_id":   doc["partner_id"],
        "partner_name": doc.get("partner_name"),
        "username":     doc.get("username"),
        "ichi_classes": doc.get("ichi", []),
        "updated_at":   doc.get("updated_at"),
    }


# ── POST: guardar ichi_classes de un partner ─────────────────────────────────

@router.post("/{partner_id}")
def save_ichi(partner_id: str, body: ICHIPayload):
    db["specialties"].update_one(
        {"partner_id": partner_id},
        {"$set": {
            "ichi":       [s.model_dump() for s in body.ichi_classes],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True, "saved": len(body.ichi_classes)}


# ── POST: importar desde Excel ────────────────────────────────────────────────

@router.post("/import/{partner_id}")
async def import_from_excel(partner_id: str, file: UploadFile = File(...)):
    contents = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True)
    ws = wb.active

    codes = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # saltar encabezado
        code = str(row[0]).strip() if row[0] else ""
        if code and code != "None":
            codes.append(code)

    if not codes:
        raise HTTPException(status_code=400, detail="No se encontraron códigos en el archivo")

    imported  = []
    not_found = []

    for code in codes:
        doc = db["ichi"].find_one(
            {"$or": [{"code": code}, {"block_id": code}]},
            {"_id": 0, "code": 1, "block_id": 1, "titulo_limpio_es": 1, "titulo_limpio": 1, "titulo": 1},
        )
        if doc:
            item = _doc_to_ichi_class(doc)
            if item:
                imported.append(item)
            else:
                not_found.append(code)
        else:
            not_found.append(code)

    return {
        "imported":  imported,
        "not_found": not_found,
        "total":     len(codes),
    }