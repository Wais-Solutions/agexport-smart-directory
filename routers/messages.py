import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime
from pymongo import MongoClient


from utils.chat import handle_message, send_text_message, echo_message
from utils.db import log_to_db

router = APIRouter() 
WHATSAPP_HOOK_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")

#### API PING
@router.get("/")
def home(): 
    return "Messages router is live"

#### META VERIFICATION ENDPOINT 
@router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        log_to_db("INFO", "Webhook verification attempt", {
            "mode": mode,
            "token_provided": token,
            "expected_token": WHATSAPP_HOOK_TOKEN
        })
        
        if mode == "subscribe" and token == WHATSAPP_HOOK_TOKEN:
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        raise HTTPException(status_code=400, detail="Missing parameters")

#### MAIN     
@router.post("/webhook")
async def callback(request: Request): 
    data = await request.json()
    # print("Incoming data:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            message = messages[0]
            await echo_message(message)

    except Exception as e:
        print("Error:", e)
        # Send error message to user if possible
        try:
            if 'sender_id' in locals():
                error_message = "Sorry, there was an error processing your message. Please try again."
                await send_text_message(message["from"], error_message)
        except:
            pass

    return {"status": "received"}