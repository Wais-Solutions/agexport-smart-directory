from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.db_tools import db
import bcrypt

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