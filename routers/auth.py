from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.db_tools import db
import bcrypt
import httpx
import os
from bson import ObjectId

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

# GET /auth/users — listar todos los usuarios
@router.get("/users")
def get_users():
    users = list(db["users"].find({}, {"password": 0}))  # excluir hash
    for u in users:
        u["_id"] = str(u["_id"])
        if u.get("partner_id"):
            u["partner_id"] = str(u["partner_id"])
    return users

# PATCH /auth/users/{username}/password — cambiar contraseña
class PasswordUpdate(BaseModel):
    new_password: str

@router.patch("/users/{username}/password")
def update_password(username: str, body: PasswordUpdate):
    if not body.new_password or len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Contraseña muy corta (mín. 6 caracteres)")
    hashed = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    result = db["users"].update_one(
        {"username": username},
        {"$set": {"password": hashed}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"ok": True}

# DELETE /auth/users/{username} — eliminar usuario
@router.delete("/users/{username}")
def delete_user(username: str):
    if username == "admin":
        raise HTTPException(status_code=403, detail="No se puede eliminar el admin")
    result = db["users"].delete_one({"username": username})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"ok": True}