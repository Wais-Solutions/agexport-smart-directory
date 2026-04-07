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

def _log_whatsapp_response(sender_id, message_type, resp):
    """Log WhatsApp API response, using ERROR level for non-200 status codes"""
    level = "INFO" if resp.status_code == 200 else "ERROR"
    log_to_db(level, f"WhatsApp API response [{message_type}]", {
        "sender_id": sender_id,
        "status_code": resp.status_code,
        "response": resp.text
    })

async def send_text_message(sender_id, message):
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
        _log_whatsapp_response(sender_id, "text", resp)
        if resp.status_code == 200:
            from utils.db_tools import log_bot_message
            log_bot_message(sender_id, message, message_type="text")
        return resp

async def send_initial_location_request(sender_id):
    from utils.translation import get_user_language, translate_message
    
    default_message = "To give you the best medical referrals, I need to know your location. Please share your location using the button below, or simply type the name of your city (e.g., 'Antigua Guatemala')."
    
    user_language = await get_user_language(sender_id)
    if user_language and user_language.lower() not in ['english', 'en']:
        translated_message = await translate_message(default_message, user_language, sender_id)
    else:
        translated_message = default_message
    
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "interactive",
        "interactive": {
            "type": "location_request_message",
            "body": {
                "text": translated_message
            },
            "action": {
                "name": "send_location"
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        _log_whatsapp_response(sender_id, "location_request", resp)
        if resp.status_code == 200:
            from utils.db_tools import log_bot_message
            log_bot_message(sender_id, translated_message, message_type="location_request")
        return resp

async def echo_message(message): 
    sender_id = message["from"]
    payload = {
        "messaging_product": "whatsapp",
        "to": sender_id,
        "type": "text",
        "text": {
            "body": message.get("text", {}).get("body", "")
        }
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        _log_whatsapp_response(sender_id, "echo", resp)
        return resp

async def send_template_message(recipient_number, template_name, parameters, language_code="es"):
    """
    Send a WhatsApp template message
    """
    try:
        components = []
        
        if parameters:
            body_parameters = []
            for i, param in enumerate(parameters, 1):
                body_parameters.append({
                    "type": "text",
                    "text": str(param)
                })
            
            components.append({
                "type": "body",
                "parameters": body_parameters
            })
        
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code
                },
                "components": components
            }
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
            _log_whatsapp_response(recipient_number, f"template:{template_name}", resp)
            return resp
            
    except Exception as e:
        log_to_db("ERROR", "Error sending template message", {
            "sender_id": recipient_number,
            "template_name": template_name,
            "error": str(e)
        })
        return None