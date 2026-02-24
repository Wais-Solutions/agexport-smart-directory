from utils.db_tools import (
    log_to_db, get_conversation, set_pending_location_confirmation, 
    get_pending_location_confirmation, clear_pending_location_confirmation,
    increment_location_confirmation_attempts, reset_location_confirmation_attempts,
    save_patient_data
)
from utils.llm import geocode_location, detect_confirmation
from utils.whatsapp import send_initial_location_request
from utils.translation import send_translated_message

async def process_location_message(sender_id, conversation, message_data, location_data):
    if not has_location(conversation):
        pending_location = get_pending_location_confirmation(sender_id)
        
        if pending_location:
            if message_data.get('location'):
                await ask_location_confirmation(sender_id, pending_location)
                return
            
            await handle_location_confirmation(sender_id, message_data, pending_location)
            return
        
        if location_data:
            await update_conversation_location(sender_id, location_data)
            await update_patient_location(sender_id, conversation, location_data)
            reset_location_confirmation_attempts(sender_id)
            
            log_to_db("INFO", "GPS location received and saved", {
                "sender_id": sender_id,
                "lat": location_data.get("lat"),
                "lon": location_data.get("lon"),
                "description": location_data.get("text_description")
            })
            
            from utils.chat import has_symptoms
            conversation_refreshed = get_conversation(sender_id)
            if has_symptoms(conversation_refreshed):
                searching_message = "Thank you for confirming your location! I'm now finding the best medical recommendations for you. This may take a moment..."
                await send_translated_message(sender_id, searching_message)
            else:
                confirmation_message = "Perfect! Your location has been saved."
                await send_translated_message(sender_id, confirmation_message)
        elif message_data.get('location'):
            await process_location_reference(sender_id, message_data['location'])

async def handle_location_confirmation(sender_id, message_data, pending_location):
    """Handle user's response to location confirmation request"""
    message_text = ""
    
    conversation = get_conversation(sender_id)
    if conversation and conversation.get('messages'):
        last_message = conversation['messages'][-1]
        message_text = last_message.get('text', '')
    
    if not message_text:
        await ask_location_confirmation(sender_id, pending_location)
        return
    
    message_lower = message_text.lower().strip()
    simple_yes_words = ['yes', 'si', 'sí', 'correct', 'correcto', 'exacto', 'perfecto', 'ok', 'okay']
    simple_no_words = ['no', 'nope', 'wrong', 'incorrect', 'incorrecto', 'mal']
    
    is_simple_yes = any(word == message_lower or message_lower.startswith(word + ' ') or message_lower.endswith(' ' + word) for word in simple_yes_words)
    is_simple_no = any(word == message_lower or message_lower.startswith(word + ' ') or message_lower.endswith(' ' + word) for word in simple_no_words)
    
    if is_simple_yes or is_simple_no:
        confirmation_result = {
            "is_confirmation": True,
            "confirmed": is_simple_yes
        }
    else:
        confirmation_result = await detect_confirmation(message_text)
    
    if confirmation_result.get('is_confirmation', False):
        if confirmation_result.get('confirmed', False):
            await update_conversation_location(sender_id, pending_location)
            await update_patient_location(sender_id, conversation, pending_location)
            clear_pending_location_confirmation(sender_id)
            reset_location_confirmation_attempts(sender_id)
            
            log_to_db("INFO", "Text location confirmed and saved", {
                "sender_id": sender_id,
                "location": pending_location.get("text_description")
            })
            
            from utils.chat import has_symptoms
            conversation_refreshed = get_conversation(sender_id)
            if has_symptoms(conversation_refreshed):
                searching_message = "Thank you for confirming your location! I'm now finding the best medical recommendations for you. This may take a moment..."
                await send_translated_message(sender_id, searching_message)
            else:
                confirmation_message = "Perfect! Your location has been saved."
                await send_translated_message(sender_id, confirmation_message)
        else:
            clear_pending_location_confirmation(sender_id)
            increment_location_confirmation_attempts(sender_id)
            
            conversation = get_conversation(sender_id)
            attempts = conversation.get('location_confirmation_attempts', 0)
            
            if attempts >= 2:
                rejection_message = "I understand the location wasn't correct. Please use the button below to share your exact GPS location, or I won't be able to help you with location-based referrals."
                await send_translated_message(sender_id, rejection_message)
                await send_initial_location_request(sender_id)
            else:
                rejection_message = "I understand that location wasn't correct. Please try again with the name of your city or municipality, or use the GPS button below."
                await send_translated_message(sender_id, rejection_message)
                await send_initial_location_request(sender_id)
            
            log_to_db("ERROR", "Location rejected by user after confirmation", {
                "sender_id": sender_id,
                "rejected_location": pending_location.get("text_description"),
                "attempts": attempts + 1
            })
    else:
        await ask_location_confirmation(sender_id, pending_location)

async def process_location_reference(sender_id, location_text):
    conversation = get_conversation(sender_id)
    attempts = conversation.get('location_confirmation_attempts', 0)
    
    if attempts >= 2:
        gps_only_message = "Please use the GPS button below to share your exact location. I can no longer accept text-based location references."
        await send_translated_message(sender_id, gps_only_message)
        await send_initial_location_request(sender_id)
        return
    
    try:
        lat, lon, formatted_address = await geocode_location(location_text)
        
        if lat and lon:
            location_data = {
                "lat": lat,
                "lon": lon,
                "text_description": formatted_address,
                "location_type": "text"
            }
            
            set_pending_location_confirmation(sender_id, location_data)
            await ask_location_confirmation(sender_id, location_data)
                
        else:
            increment_location_confirmation_attempts(sender_id)
            
            error_message = "I couldn't find that location in Guatemala. Please try the name of your city or municipality (e.g., 'Guatemala City,' 'Antigua Guatemala,' 'Quetzaltenango'), or use the GPS button below."
            await send_translated_message(sender_id, error_message)
            await send_initial_location_request(sender_id)
            
            log_to_db("ERROR", "Location not found in geocoding", {
                "sender_id": sender_id,
                "location_text": location_text
            })
            
    except Exception as e:
        log_to_db("ERROR", "Error processing location reference", {
            "sender_id": sender_id,
            "location_text": location_text,
            "error": str(e)
        })
        
        error_message = "There was an error processing your location. Please try again or use the GPS button below."
        await send_translated_message(sender_id, error_message)
        await send_initial_location_request(sender_id)

async def ask_location_confirmation(sender_id, location_data):
    """Ask user to confirm if the found location is correct"""
    confirmation_message = f"I found this location: {location_data['text_description']}. Is this correct? Please reply with 'yes' or 'no'."
    await send_translated_message(sender_id, confirmation_message)

async def request_location(sender_id):
    await send_initial_location_request(sender_id)

async def update_conversation_location(sender_id, location_data):
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"location": location_data}}
    )

async def update_patient_location(sender_id, conversation, location_data):
    try:
        current_symptoms = conversation.get("symptoms", [])
        current_language = conversation.get("language")
        
        save_patient_data(
            phone_number=sender_id,
            symptoms=current_symptoms,
            location=location_data,
            language=current_language,
            urgency=None
        )
        
    except Exception as e:
        log_to_db("ERROR", "Error updating patient location", {
            "sender_id": sender_id,
            "error": str(e)
        })

def has_location(conversation): 
    location = conversation.get("location")
    if location:
        lat = location.get("lat")
        lon = location.get("lon")
        return lat is not None and lon is not None
    return False