import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException
from fastapi.responses import PlainTextResponse
from datetime import datetime
import httpx
from groq import AsyncGroq

router = APIRouter() 
WHATSAPP_HOOK_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")

@router.get("/")
def home(): 
    return "Messages router is live"

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        print(f"Comparing {WHATSAPP_HOOK_TOKEN} with {token}")
        if mode == "subscribe" and token == WHATSAPP_HOOK_TOKEN:
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        raise HTTPException(status_code=400, detail="Missing parameters")