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

    print(f"sending {payload} - {WHATSAPP_API_URL} to {sender_id}")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        print(f"resp - {resp}")
        return resp

async def send_initial_location_request(sender_id):
    # Send initial location request message with interactive button
    # Get user's language and translate the message
    from utils.translation import get_user_language, translate_message
    
    default_message = "To give you the best medical referrals, I need to know your location. Please share your location using the button below, or simply type the name of your city (e.g., 'Antigua Guatemala')."
    
    # Get user's language and translate if needed
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
        log_to_db("DEBUG", "Location request sent", {
            "sender_id": sender_id,
            "response_status": resp.status_code,
            "language_used": user_language or "English"
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

async def send_template_message(recipient_number, template_name, parameters, language_code="es"):
    """
    Send a WhatsApp template message
    
    Args:
        recipient_number: Phone number to send the template to (e.g., "50212345678")
        template_name: Name of the template (e.g., "bot_referral_notification")
        parameters: List of parameter values for the template (e.g., ["50212345678", "headache, fever", "Spanish"])
        language_code: Language code for the template (default: "es" for Spanish)
    
    Returns:
        Response from WhatsApp API
    """
    try:
        # Build the components array with parameters
        components = []
        
        if parameters:
            # Build body component with parameters
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
        
        log_to_db("INFO", "Sending template message", {
            "recipient": recipient_number,
            "template_name": template_name,
            "parameters": parameters,
            "language_code": language_code
        })
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
            
            if resp.status_code == 200:
                log_to_db("INFO", "Template message sent successfully", {
                    "recipient": recipient_number,
                    "template_name": template_name,
                    "response": resp.json()
                })
            else:
                log_to_db("ERROR", "Failed to send template message", {
                    "recipient": recipient_number,
                    "template_name": template_name,
                    "status_code": resp.status_code,
                    "response": resp.text
                })
            
            return resp
            
    except Exception as e:
        log_to_db("ERROR", "Error sending template message", {
            "recipient": recipient_number,
            "template_name": template_name,
            "error": str(e)
        })
        return None