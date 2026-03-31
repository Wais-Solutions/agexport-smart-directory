from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/services", tags=["services"])

@router.get("/")
async def get_services():
    """
    Retorna todos los servicios médicos disponibles,
    excluyendo los embeddings (solo para uso del chatbot).
    """
    try:
        from utils.db_tools import db
        services_collection = db["services"]

        services = list(services_collection.find(
            {},
            {"_id": 0, "embedding": 0}  # excluir _id y embedding
        ))

        return {"services": services}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))