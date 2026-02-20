from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId
from utils.db_tools import db  #reutilizar conexion existente

router = APIRouter()

COLLECTIONS = [
    "debugging-logs",
    "historical_conversations",
    "ongoing_conversations",
    "partners",
    "patients",
    "referrals",
]

def serialize(doc):
    doc["_id"] = str(doc["_id"])
    return doc

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
        "data": [serialize(d) for d in docs],
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