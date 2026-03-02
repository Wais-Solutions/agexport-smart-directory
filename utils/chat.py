import os
from utils.db_tools import get_conversation, new_conversation, log_to_db, save_patient_data, reset_conversation
from utils.llm import extract_data
from utils.location import process_location_message, request_location
from utils.symptoms import process_symptoms_message, request_symptoms
from utils.medical_referral import provide_medical_referral
from utils.whatsapp import send_text_message
from utils.language import process_language_message

async def handle_message(message): 
    sender_id = message["from"]
    message_type = message.get("type", "text")

    # Retrieve existing conversation or create a new one
    conversation = get_conversation(sender_id=sender_id)
    
    if not conversation: 
        conversation = new_conversation(sender_id=sender_id)
        log_to_db("INFO", "New conversation started", {"sender_id": sender_id})

    # Initialize variables
    message_data = {"location": None, "symptoms": None, "language": None}
    location_data = None
    message_text = ""

    # Extract data based on message type
    if message_type == "text": 
        message_text = message.get("text", {}).get("body", "")
        
        # Check if message is the reset command
        if message_text.strip() == "/reset":
            success = reset_conversation(sender_id)
            
            if success:
                from utils.translation import send_translated_message
                confirmation_msg = "Your conversation has been reset. All your previous information (symptoms, location, language) has been cleared. You can start fresh now!"
                await send_translated_message(sender_id, confirmation_msg)
            else:
                await send_text_message(sender_id, "There was an issue resetting your conversation. Please try again.")
            
            return
        
        # Check if we're waiting for another referral response
        if conversation.get('waiting_for_another_referral', False):
            await handle_another_referral_response(sender_id, conversation, message_text)
            return
        
        message_data = await extract_data(message_text)
        
        # Save patient data if any information was extracted
        await save_patient_data_from_extraction(sender_id, conversation, message_data)
        
        # Store the message in conversation for reference
        from utils.db_tools import ongoing_conversations
        ongoing_conversations.update_one(
            {"sender_id": sender_id},
            {"$push": {"messages": {"sender": sender_id, "text": message_text}}}
        )
    
    elif message_type == "location": 
        location = message.get("location", {})
        latitude = location.get("latitude")
        longitude = location.get("longitude")
    
        location_data = {
            "lat": latitude,
            "lon": longitude,
            "text_description": f"Coordinates {latitude}, {longitude}",
            "location_type": "gps"
        }
        
        # Save GPS location to patient data
        await save_patient_data_from_gps(sender_id, conversation, location_data)
        
        # Store the GPS message
        from utils.db_tools import ongoing_conversations
        ongoing_conversations.update_one(
            {"sender_id": sender_id},
            {"$push": {"messages": {"sender": sender_id, "text": f"GPS location: {latitude}, {longitude}"}}}
        )

    # Check if user had location before processing
    had_location_before = has_location(conversation)
    
    # Process language FIRST (before location) so confirmation messages use correct language
    await process_language_message(sender_id, conversation, message_data)
    
    # Process symptoms
    await process_symptoms_message(sender_id, conversation, message_data)
    
    # Process location (will use language from above for confirmation messages)
    await process_location_message(sender_id, conversation, message_data, location_data)
    
    # Refresh conversation
    conversation = get_conversation(sender_id=sender_id)
    
    # Check conditions
    has_location_now = has_location(conversation)
    referral_provided = conversation.get("referral_provided", False)
    pending_location = conversation.get("pending_location_confirmation")
    
    location_just_obtained = (not had_location_before and has_location_now) or (has_location_now and not pending_location and not had_location_before)
    
    if not referral_provided and has_symptoms(conversation) and has_location_now and (location_just_obtained or had_location_before):
        await provide_medical_referral(sender_id, conversation)
        
        from utils.db_tools import ongoing_conversations
        ongoing_conversations.update_one(
            {"sender_id": sender_id},
            {"$set": {"referral_provided": True}}
        )
    else:
        if not pending_location:
            if not has_symptoms(conversation):
                await request_symptoms(sender_id)
            elif not has_location_now:
                await request_location(sender_id)

# Saves the patient data extracted from the text message
async def save_patient_data_from_extraction(sender_id, conversation, message_data):
    try:
        current_symptoms = conversation.get("symptoms", [])
        current_location = conversation.get("location")
        current_language = conversation.get("language")
        
        new_symptoms = message_data.get("symptoms", [])
        new_location_text = message_data.get("location")
        new_language = message_data.get("language")
        
        all_symptoms = list(set(current_symptoms + new_symptoms)) if new_symptoms else current_symptoms
        
        location_to_save = current_location
        if new_location_text and not current_location:
            location_to_save = {
                "lat": None,
                "lon": None,
                "text_description": new_location_text
            }
        
        language_to_save = new_language if new_language else current_language
        
        if new_symptoms or new_location_text or new_language:
            save_patient_data(
                phone_number=sender_id,
                symptoms=all_symptoms,
                location=location_to_save,
                language=language_to_save,
                urgency=None
            )
            
    except Exception as e:
        log_to_db("ERROR", "Error saving patient data", {
            "sender_id": sender_id,
            "sender_id": sender_id,
            "error": str(e)
        })

# Saves patient data when GPS location is received
async def save_patient_data_from_gps(sender_id, conversation, location_data):
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
        log_to_db("ERROR", "Error saving GPS data", {
            "sender_id": sender_id,
            "sender_id": sender_id,
            "error": str(e)
        })

def has_symptoms(conversation): 
    symptoms = conversation.get("symptoms")
    if symptoms:
        return len(symptoms) > 0
    return False

def has_location(conversation): 
    location = conversation.get("location")
    if location:
        lat = location.get("lat")
        lon = location.get("lon")
        return lat is not None and lon is not None
    return False

async def handle_another_referral_response(sender_id, conversation, message_text):
    """Handle user response when asked if they need another referral"""
    from utils.db_tools import (
        copy_conversation_to_history, reset_symptoms_only, 
        set_waiting_for_another_referral, get_conversation
    )
    from utils.llm import detect_confirmation
    from utils.symptoms import request_symptoms
    from utils.translation import send_translated_message
    
    message_lower = message_text.lower().strip()
    simple_yes_words = ['yes', 'si', 'sí', 'correct', 'correcto', 'exacto', 'perfecto', 'ok', 'okay', 'claro']
    simple_no_words = ['no', 'nope', 'wrong', 'incorrect', 'incorrecto', 'mal', 'nop']
    
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
            log_to_db("INFO", "User requested another referral", {
                "sender_id": sender_id,
                "referral_count": conversation.get('referral_count', 0)
            })
            
            copy_success = copy_conversation_to_history(sender_id)
            
            if copy_success:
                reset_symptoms_only(sender_id)
                
                symptoms_message = "Great! I'll help you with another referral. Please tell me your new symptoms."
                await send_translated_message(sender_id, symptoms_message)
            else:
                log_to_db("ERROR", "Failed to copy conversation to history for another referral", {
                    "sender_id": sender_id
                })
                error_message = "There was an error processing your request. Please try again."
                await send_translated_message(sender_id, error_message)
        else:
            set_waiting_for_another_referral(sender_id, False)
            
            goodbye_message = "Okay, I'm here if you need another recommendation. Feel free to contact me anytime!"
            await send_translated_message(sender_id, goodbye_message)
    else:
        clarification_message = "I didn't understand your response. Do you need another medical referral for different symptoms? Please reply 'yes' or 'no'."
        await send_translated_message(sender_id, clarification_message)