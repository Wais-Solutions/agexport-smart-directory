import os
from utils.db_tools import get_conversation, new_conversation, log_to_db, save_patient_data
from utils.llm import extract_data
from utils.location import process_location_message, request_location
from utils.symptoms import process_symptoms_message, request_symptoms
from utils.medical_referral import provide_medical_referral
from utils.whatsapp import send_text_message
from utils.language import process_language_message
from utils.translation import send_translated_message

async def handle_message(message): 
    sender_id = message["from"]
    message_type = message.get("type", "text")

    # Retrieve existing conversation or create a new one
    conversation = get_conversation(sender_id=sender_id)
    
    if not conversation: 
        conversation = new_conversation(sender_id=sender_id)
        log_to_db("INFO", "New conversation created", {"sender_id": sender_id})

    # Initialize variables
    message_data = {"location": None, "symptoms": None, "language": None}
    location_data = None
    message_text = ""

    # Extract data based on message type
    if message_type == "text": 
        message_text = message.get("text", {}).get("body", "")
        message_data = await extract_data(message_text)
        log_to_db("DEBUG", "Data extracted from text", {
            "sender_id": sender_id,
            "message_text": message_text,
            "extracted_data": message_data
        })
        
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
            "text_description": f"Coordinates {latitude}, {longitude}"
        }
        log_to_db("INFO", "GPS location received", {
            "sender_id": sender_id,
            "location_data": location_data
        })
        
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
    
    # Process symptoms
    await process_symptoms_message(sender_id, conversation, message_data)
    
    # Process location with the message text for confirmation handling
    # NOTE: location.py sends the "searching" message immediately when location is obtained
    await process_location_message(sender_id, conversation, message_data, location_data)
    
    # Process language
    await process_language_message(sender_id, conversation, message_data)
    
    # Refresh conversation to get updated data
    conversation = get_conversation(sender_id=sender_id)
    
    # Check if user now has location (after processing)
    has_location_now = has_location(conversation)
    
    # Check if referral was already provided (use .get() with default False for old documents)
    referral_provided = conversation.get("referral_provided", False)
    
    # Determine if location was JUST obtained in this message
    location_just_obtained = not had_location_before and has_location_now
    
    log_to_db("DEBUG", "Checking referral conditions", {
        "sender_id": sender_id,
        "had_location_before": had_location_before,
        "has_location_now": has_location_now,
        "location_just_obtained": location_just_obtained,
        "has_symptoms": has_symptoms(conversation),
        "referral_provided": referral_provided
    })
    
    # Only provide referral if:
    # 1. Referral not already provided
    # 2. Has symptoms
    # 3. Has location now
    # 4. Location was JUST obtained (prevents double execution)
    if not referral_provided and has_symptoms(conversation) and has_location_now and location_just_obtained:
        # NOTE: "searching" message was already sent by location.py
        # Just provide the referral
        await provide_medical_referral(sender_id, conversation)
        
        # Mark referral as provided
        from utils.db_tools import ongoing_conversations
        ongoing_conversations.update_one(
            {"sender_id": sender_id},
            {"$set": {"referral_provided": True}}
        )
        
        log_to_db("INFO", "Referral provided and marked as complete", {
            "sender_id": sender_id
        })
    elif referral_provided:
        # Referral already provided - don't send again
        log_to_db("DEBUG", "Referral already provided, skipping", {
            "sender_id": sender_id
        })
    else:
        # Missing data - ask for what's missing (only if not waiting for confirmation)
        pending_location = conversation.get("pending_location_confirmation")
        if not pending_location:  # Only ask for missing data if not waiting for confirmation
            if not has_symptoms(conversation):
                await request_symptoms(sender_id)
            elif not has_location_now:
                await request_location(sender_id)

# Saves the patient data extracted from the text message
async def save_patient_data_from_extraction(sender_id, conversation, message_data):
    try:
        # Obtain current patient data (if any)
        current_symptoms = conversation.get("symptoms", [])
        current_location = conversation.get("location")
        current_language = conversation.get("language")
        
        # Combine new and existing data
        new_symptoms = message_data.get("symptoms", [])
        new_location_text = message_data.get("location")
        new_language = message_data.get("language")
        
        # Symptoms: Adding new ones to existing ones (no duplicates)
        all_symptoms = list(set(current_symptoms + new_symptoms)) if new_symptoms else current_symptoms
        
        # Location: Keep existing if there is no new one
        location_to_save = current_location
        if new_location_text and not current_location:
            # We only save the location text if we dont have coordinates yet
            location_to_save = {
                "lat": None,
                "lon": None,
                "text_description": new_location_text
            }
        
        # Language: use new if exists, otherwise keep current
        language_to_save = new_language if new_language else current_language
        
        # Save only if there is new information worth saving
        if new_symptoms or new_location_text or new_language:
            save_patient_data(
                phone_number=sender_id,
                symptoms=all_symptoms,
                location=location_to_save,
                language=language_to_save,
                urgency=None  # Always None (for now)
            )
            
            log_to_db("INFO", "Patient data updated from text extraction", {
                "sender_id": sender_id,
                "new_symptoms": new_symptoms,
                "new_location": new_location_text,
                "new_language": new_language
            })
            
    except Exception as e:
        log_to_db("ERROR", "Error saving patient data from extraction", {
            "sender_id": sender_id,
            "error": str(e)
        })

# Saves patient data when GPS location is received
async def save_patient_data_from_gps(sender_id, conversation, location_data):
    try:
        # Obtain current patient data
        current_symptoms = conversation.get("symptoms", [])
        current_language = conversation.get("language")
        
        # Save with the new GPS location
        save_patient_data(
            phone_number=sender_id,
            symptoms=current_symptoms,
            location=location_data,
            language=current_language,
            urgency=None  # Always None (for now)
        )
        
        log_to_db("INFO", "Patient data updated with GPS location", {
            "sender_id": sender_id,
            "location": location_data
        })
        
    except Exception as e:
        log_to_db("ERROR", "Error saving patient data from GPS", {
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