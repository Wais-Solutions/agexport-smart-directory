import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime
from pymongo import MongoClient
import httpx

from utils.llm import handle_conversation, get_completition, user_has_location

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

async def send_location_request(sender_id):
    # Send a location request message using Whatsapps location request feature
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text": "To provide you with better medical referrals, I need to know your location. Please share yours."
            },
            "action": {
                "name": "send_location"
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        print(f"Location request sent: {resp.status_code}")
        return resp

async def send_text_message(sender_id, message):
    # Send a normal text message
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "text",
        "text": {
            "body": message
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        return resp

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
            message_type = message.get("type", "text")

            text = ""
            location_data = None

            if message_type == "text":
                # Get the message text
                text = message.get("text", {}).get("body", "")
                
                # Check if user has already provided location
                if not user_has_location(sender_id):
                    # Save the user's message first
                    handle_conversation(sender_id, sender_id, text)
                    
                    # Send location request instead of processing the message
                    await send_location_request(sender_id)
                    
                    # Send explanatory message
                    location_explanation = "Hello! Before I can help you with medical referrals, I need your location. Please share yours using the button above."
                    handle_conversation(sender_id, "botsito", location_explanation)
                    
                else:
                    # User has location, proceed with normal conversation
                    handle_conversation(sender_id, sender_id, text)
                    chat_response = await get_completition(text)
                    handle_conversation(sender_id, "botsito", chat_response)
                    
                    await send_text_message(sender_id, chat_response)

            elif message_type == "location":
                # Location message received
                location = message.get("location", {})
                latitude = location.get("latitude")
                longitude = location.get("longitude")
                # name = location.get("name", "")
                # address = location.get("address", "")
                
                # Create text description of location
                location_description = f"Coordinates: {latitude}, {longitude}"
                
                location_data = {
                    "lat": latitude,
                    "lon": longitude,
                    "text_description": location_description
                }
                
                # Save location message
                text = f"Location sended: {location_description}"
                handle_conversation(sender_id, sender_id, text, location_data)

                # Confirm location received and start normal conversation
                confirmation_message = f"Great! I've registered your location: {location_description}. I can now help you with medical referrals in your area. How can I help you?"
                handle_conversation(sender_id, "botsito", confirmation_message)
                
                await send_text_message(sender_id, confirmation_message)

            elif message_type == "interactive":
                # Handle interactive message responses (like location request responses)
                interactive = message.get("interactive", {})
                interactive_type = interactive.get("type", "")
                
                if interactive_type == "location_request_message":
                    # User clicked on location request but didn't send location yet
                    reminder_message = "Please share your location to continue. I need this information to provide you with the best medical referrals."
                    handle_conversation(sender_id, "botsito", reminder_message)
                    await send_text_message(sender_id, reminder_message)

    except Exception as e:
        print("Error:", e)
        # Send error message to user if possible
        try:
            if 'sender_id' in locals():
                error_message = "Sorry, there was an error processing your message. Please try again."
                await send_text_message(sender_id, error_message)
        except:
            pass

    return {"status": "received"}