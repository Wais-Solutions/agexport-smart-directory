import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime
from pymongo import MongoClient
import httpx

from utils.llm import handle_conversation, get_completition


router = APIRouter() 

ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
WHATSAPP_HOOK_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
# "https://graph.facebook.com/v18.0/739443625915932/messages"


headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

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
    
@router.post("/webhook")
async def callback(request: Request): 
    # print("callback is beign called")
    data = await request.json()
    # print("Incoming data:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            message = messages[0]
            sender_id = message["from"]

            # Get the message text
            text = message.get("text", {}).get("body", "")

            # Handle conversation (insert message into MongoDB)
            handle_conversation(sender_id, sender_id, text)

            chat_response = await get_completition(text)

            handle_conversation(sender_id, "botsito", chat_response)

            # Prepare response message payload
            payload = {
                "messaging_product": "whatsapp",
                "to": sender_id,
                "type": "text",
                "text": {
                    "body": chat_response
                }
            }

            # Send message back to the user
            async with httpx.AsyncClient() as client:
                resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
                # print("Response from WhatsApp:", resp.status_code, resp.text)

    except Exception as e:
        print("Error:", e)

    return {"status": "received"}