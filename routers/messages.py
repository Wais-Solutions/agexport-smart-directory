import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime
from pymongo import MongoClient
import httpx

from utils.llm import (
    handle_conversation, 
    get_completition, 
    user_has_location,
    set_waiting_for_location_reference,
    is_waiting_for_location_reference,
    geocode_location,
    log_to_db
)

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

async def send_initial_location_request(sender_id):
    # Send initial location request message at conversation start
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text": "Hello! To provide you with the best medical referrals, I need to know your location. Please share your location using the button below, or simply type the name of your city (e.g., 'Antigua Guatemala')."
            },
            "action": {
                "name": "send_location"
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        # print(f"Initial location request sent: {resp.status_code}")
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

async def process_location_reference(sender_id, location_text):
    # Process location reference using geocoding API
    try:
        # Try to geocode the location
        lat, lon, formatted_address = await geocode_location(location_text)
        
        if lat and lon:
            # Location found in Guatemala
            location_data = {
                "lat": lat,
                "lon": lon,
                "text_description": formatted_address
            }
            
            # Save location to database
            handle_conversation(sender_id, "system", f"Location geocoded: {formatted_address}", location_data)
            
            # Send confirmation
            confirmation_message = f"Great! I've found your location: {formatted_address}. I can now help you with medical referrals in your area. How can I help you?"
            handle_conversation(sender_id, "botsito", confirmation_message)
            await send_text_message(sender_id, confirmation_message)
            
            # Clear waiting flag
            set_waiting_for_location_reference(sender_id, False)
            
            return True
        else:
            # Location not found in Guatemala
            error_message = "I couldn't find that location in Guatemala. Please try the name of your city or municipality (e.g., 'Guatemala City,' 'Antigua Guatemala,' 'Quetzaltenango.')"
            handle_conversation(sender_id, "botsito", error_message)
            await send_text_message(sender_id, error_message)
            
            return False
            
    except Exception as e:
        # print(f"Error processing location reference: {e}")
        error_message = "There was an error processing your location. Please try again."
        handle_conversation(sender_id, "botsito", error_message)
        await send_text_message(sender_id, error_message)
        
        return False

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
            sender_id = message["from"]
            message_type = message.get("type", "text")

            # Check if user has location
            if user_has_location(sender_id):
                # User has location, proceed with normal conversation
                if message_type == "text":
                    text = message.get("text", {}).get("body", "")
                    handle_conversation(sender_id, sender_id, text)
                    chat_response = await get_completition(text)
                    handle_conversation(sender_id, "botsito", chat_response)
                    await send_text_message(sender_id, chat_response)
                else:
                    # Non text message when user already has location
                    text = f"Message type {message_type} received"
                    handle_conversation(sender_id, sender_id, text)
                    response_message = "I can only process text messages. Please send a text message."
                    handle_conversation(sender_id, "botsito", response_message)
                    await send_text_message(sender_id, response_message)
                    
            else:
                # User doesnt have location yet
                if message_type == "text":
                    text = message.get("text", {}).get("body", "")
                    handle_conversation(sender_id, sender_id, text)
                    
                    if is_waiting_for_location_reference(sender_id):
                        # We are waiting for location reference, process it
                        await process_location_reference(sender_id, text)
                    else:
                        # First message from user so the action is to send location request and set waiting flag
                        await send_initial_location_request(sender_id)
                        
                        # Set flag that we are now waiting for location reference
                        set_waiting_for_location_reference(sender_id, True)
                        
                        # Log that we sent the location request so NO procesamos el mensaje como ubicacion todavía
                        initial_request_message = "Initial location request sent to user"
                        handle_conversation(sender_id, "system", initial_request_message)

                elif message_type == "location":
                    # GPS location message received
                    location = message.get("location", {})
                    latitude = location.get("latitude")
                    longitude = location.get("longitude")
                    
                    location_description = f"Coordinates: {latitude}, {longitude}"
                    
                    location_data = {
                        "lat": latitude,
                        "lon": longitude,
                        "text_description": location_description
                    }
                    
                    # Save location message
                    text = f"GPS location received: {location_description}"
                    handle_conversation(sender_id, sender_id, text, location_data)

                    # Confirm location received and start normal conversation
                    confirmation_message = f"Perfect! I've recorded your GPS location: {location_description}. I can now help you with medical referrals in your area. How can I help you?"
                    handle_conversation(sender_id, "botsito", confirmation_message)
                    await send_text_message(sender_id, confirmation_message)
                    
                    # Clear waiting flag
                    set_waiting_for_location_reference(sender_id, False)

                elif message_type == "interactive":
                    # Handle interactive message responses
                    interactive = message.get("interactive", {})
                    interactive_type = interactive.get("type", "")
                    
                    if interactive_type == "location_request_message":
                        # User clicked on location request but didnt send location yet
                        reminder_message = "Please share your GPS location or enter your city name to continue."
                        handle_conversation(sender_id, "botsito", reminder_message)
                        await send_text_message(sender_id, reminder_message)
                        
                        # Set waiting flag
                        set_waiting_for_location_reference(sender_id, True)

                else:
                    # Other message types when user doesnt have location
                    text = f"Message type {message_type} received"
                    handle_conversation(sender_id, sender_id, text)
                    
                    # Send location request
                    await send_initial_location_request(sender_id)
                    explanation = "I need your location so I can help you. Please share your GPS location using the button above, or type in your city name."
                    handle_conversation(sender_id, "botsito", explanation)
                    await send_text_message(sender_id, explanation)
                    
                    # Set waiting flag
                    set_waiting_for_location_reference(sender_id, True)

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