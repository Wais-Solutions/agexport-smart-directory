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
    user_has_selected_location_method,
    set_location_method,
    set_waiting_for_text_location,
    is_waiting_for_text_location
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

async def send_location_method_menu(sender_id):
    """Send menu to choose location method"""
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {
                "type": "text",
                "text": "Location Setup"
            },
            "body": {
                "text": "To provide you with the best medical referrals, I need to know your location. Please choose how you'd like to share it:"
            },
            "action": {
                "button": "Select Option",
                "sections": [
                    {
                        "title": "Location Options",
                        "rows": [
                            {
                                "id": "gps_location",
                                "title": "📍 Share GPS Location",
                                "description": "Share your exact location using GPS"
                            },
                            {
                                "id": "text_reference",
                                "title": "📝 Type Location Name",
                                "description": "Tell me your city or area name (Ex: 'Antigua Guatemala')"
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        print(f"Location menu sent: {resp.status_code}")
        return resp

async def send_location_request(sender_id):
    # Send a location request message using Whatsapps location request feature
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text": "Please share your GPS location using the button below:"
            },
            "action": {
                "name": "send_location"
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        # print(f"Location request sent: {resp.status_code}")
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
    data = await request.json()
    print("Incoming data:", data)

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
                
                # Check if user has location already
                if user_has_location(sender_id):
                    # User has location, proceed with normal conversation
                    handle_conversation(sender_id, sender_id, text)
                    chat_response = await get_completition(text)
                    handle_conversation(sender_id, "botsito", chat_response)
                    await send_text_message(sender_id, chat_response)
                    
                # Check if were waiting for text location reference
                elif is_waiting_for_text_location(sender_id):
                    # Save the location reference
                    handle_conversation(sender_id, sender_id, text)
                    
                    # Acknowledge receipt 
                    confirmation_message = f"Location reference received: '{text}'. Thank you! I'll process this information and get back to you with medical referrals in your area."
                    handle_conversation(sender_id, "botsito", confirmation_message)
                    await send_text_message(sender_id, confirmation_message)
                    
                    # Set flag that user now has "location" (even if its text reference)
                    location_data = {
                        "lat": None,  # Soon to be extracted
                        "lon": None,  # Soon to be extracted x2
                        "text_description": text
                    }
                    handle_conversation(sender_id, "system", "Location reference saved", location_data)
                    set_waiting_for_text_location(sender_id, False)
                    
                # Check if user hasnt selected location method yet
                elif not user_has_selected_location_method(sender_id):
                    # Save users message first
                    handle_conversation(sender_id, sender_id, text)
                    
                    # Send location method menu
                    await send_location_method_menu(sender_id)
                    
                    # Send explanatory message
                    menu_explanation = "Hello! Before I can help you with medical referrals, I need your location. Please select an option from the menu above."
                    handle_conversation(sender_id, "botsito", menu_explanation)
                    
                else:
                    # User selected method but hasnt provided location yet
                    # Remind them based on their selected method
                    handle_conversation(sender_id, sender_id, text)
                    reminder_message = "Please provide your location using the method you selected previously."
                    handle_conversation(sender_id, "botsito", reminder_message)
                    await send_text_message(sender_id, reminder_message)

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
                text = f"GPS Location received: {location_description}"
                handle_conversation(sender_id, sender_id, text, location_data)

                # Confirm location received and start normal conversation
                confirmation_message = f"Perfect! I've registered your GPS location: {location_description}. I can now help you with medical referrals in your area. How can I assist you?"
                handle_conversation(sender_id, "botsito", confirmation_message)
                await send_text_message(sender_id, confirmation_message)

            elif message_type == "interactive":
                # Handle interactive message responses
                interactive = message.get("interactive", {})
                interactive_type = interactive.get("type", "")
                
                if interactive_type == "list_reply":
                    # User selected from the location method menu
                    list_reply = interactive.get("list_reply", {})
                    selected_id = list_reply.get("id", "")
                    selected_title = list_reply.get("title", "")
                    
                    # Save user's selection
                    handle_conversation(sender_id, sender_id, f"Selected: {selected_title}")
                    set_location_method(sender_id, selected_id)
                    
                    if selected_id == "gps_location":
                        # User chose GPS location
                        await send_location_request(sender_id)
                        response_message = "Great! Please share your GPS location using the button above."
                        handle_conversation(sender_id, "botsito", response_message)
                        
                    elif selected_id == "text_reference":
                        # User chose text reference
                        set_waiting_for_text_location(sender_id, True)
                        response_message = "Perfect! Please type the name of your city or area (for example: 'Antigua Guatemala', 'Guatemala City', 'Quetzaltenango', etc.)"
                        handle_conversation(sender_id, "botsito", response_message)
                        await send_text_message(sender_id, response_message)
                        
                elif interactive_type == "location_request_message":
                    # User clicked on GPS location request but didnt send location yet
                    reminder_message = "Please share your GPS location to continue. I need this information to provide you with the best medical referrals."
                    handle_conversation(sender_id, "botsito", reminder_message)
                    await send_text_message(sender_id, reminder_message)

            else:
                # Other message types
                text = f"Message type {message_type} received"
                handle_conversation(sender_id, sender_id, text)
                
                if not user_has_location(sender_id) and not user_has_selected_location_method(sender_id):
                    # Send location method menu
                    await send_location_method_menu(sender_id)
                    explanation = "I can only process text messages and locations. Please select how you'd like to share your location from the menu above."
                    handle_conversation(sender_id, "botsito", explanation)
                else:
                    response_message = "I can only process text messages and locations. Please send a text message or your location."
                    handle_conversation(sender_id, "botsito", response_message)
                    await send_text_message(sender_id, response_message)

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