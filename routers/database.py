from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from utils.db_tools import db  # reutilizar conexion existente

router = APIRouter()

COLLECTIONS = [
    "debugging-logs",
    "historical_conversations",
    "ongoing_conversations",
    "partners",
    "patients",
    "referrals",
]

def serialize(value):
    """Recursivamente serializa tipos de MongoDB a tipos JSON-compatibles."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


# ── Modelo para edición de partners ──────────────────────────────
class PartnerUpdate(BaseModel):
    partner_name: Optional[str] = None
    partner_category: Optional[str] = None
    partner_services: Optional[List[str]] = None


@router.get("/")
def list_collections():
    return {"collections": COLLECTIONS}


@router.get("/{collection}")
def get_collection(
    collection: str,
    limit: int = Query(default=100, le=500),
    skip: int = Query(default=0),
):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Colección '{collection}' no encontrada")

    docs = list(db[collection].find().sort("_id", -1).skip(skip).limit(limit))
    return {
        "collection": collection,
        "total": db[collection].count_documents({}),
        "returned": len(docs),
        "data": [serialize(doc) for doc in docs],
    }


@router.get("/{collection}/{id}")
def get_document(collection: str, id: str):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Colección '{collection}' no encontrada")
    try:
        doc = db[collection].find_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return serialize(doc)


@router.patch("/partners/{id}")
def update_partner(id: str, body: PartnerUpdate):
    """Edita solo partner_name, partner_category y partner_services."""
    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    # Solo incluir campos que vienen en el body (no None)
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    result = db["partners"].update_one({"_id": oid}, {"$set": fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Socio no encontrado")

    updated = db["partners"].find_one({"_id": oid})
    return serialize(updated)


@router.delete("/{collection}/{id}")
def delete_document(collection: str, id: str):
    if collection not in COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Colección '{collection}' no encontrada")
    try:
        result = db[collection].delete_one({"_id": ObjectId(id)})
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return {"deleted": True, "id": id}


@router.delete("/{collection}")
def clear_collection(collection: str):
    if collection not in ["debugging-logs"]:
        raise HTTPException(status_code=403, detail="Solo se puede limpiar 'debugging-logs'")
    result = db[collection].delete_many({})
    return {"deleted_count": result.deleted_count}