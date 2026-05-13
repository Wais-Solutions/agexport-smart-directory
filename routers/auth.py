from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.db_tools import db
import bcrypt
import httpx
import os

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(body: LoginRequest):
    user = db["users"].find_one({"username": body.username})
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not bcrypt.checkpw(body.password.encode(), user["password"].encode()):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    return {
        "role": user["role"],
        "username": user["username"],
        "partner_id": str(user.get("partner_id", "")) 
    }

@router.get("/icd-token")
async def get_icd_token():
    """Proxy para obtener token de la API OMS — evita exponer keys en el frontend."""
    try:
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
        res.raise_for_status()
        data = res.json()
        return {"access_token": data["access_token"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo token ICD: {str(e)}")