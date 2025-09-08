import os
import httpx
from utils.db_tools import log_to_db

ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

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

async def send_initial_location_request(sender_id):
    # Send initial location request message with interactive button
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text": "To give you the best medical referrals, I need to know your location. Please share your location using the button below, or simply type the name of your city (e.g., 'Antigua Guatemala')."
            },
            "action": {
                "name": "send_location"
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        log_to_db("DEBUG", "Location request sent", {
            "sender_id": sender_id,
            "response_status": resp.status_code
        })
        return resp

async def echo_message(message): 
    # Send a normal text message (legacy function)
    payload = {
        "messaging_product": "whatsapp",
        "to": message["from"],
        "type": "text",
        "text": {
            "body": message.get("text", {}).get("body", "")
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        return resp