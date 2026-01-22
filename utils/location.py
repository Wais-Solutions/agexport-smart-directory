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
    # Process location from message data or GPS coordinates
    if not has_location(conversation):
        # Check if we have a pending location confirmation
        pending_location = get_pending_location_confirmation(sender_id)
        
        if pending_location:
            # User has a pending location confirmation - check if this is a confirmation message
            if message_data.get('location'):
                # User sent another location reference instead of confirming
                # Ignore this and ask them to confirm the pending location
                await ask_location_confirmation(sender_id, pending_location)
                return
            
            # Check if this is a confirmation message
            await handle_location_confirmation(sender_id, message_data, pending_location)
            return
        
        if location_data:
            # Direct GPS location received - save immediately (no confirmation needed for GPS)
            await update_conversation_location(sender_id, location_data)
            
            # Update also in the patient collection
            await update_patient_location(sender_id, conversation, location_data)
            
            reset_location_confirmation_attempts(sender_id)
            
            log_to_db("INFO", "Location updated from GPS", {
                "sender_id": sender_id,
                "location": location_data
            })
            # NOTE: "searching" message is sent by chat.py after this returns
        elif message_data.get('location'):
            # Text reference to location - need to geocode and confirm
            await process_location_reference(sender_id, message_data['location'])

async def handle_location_confirmation(sender_id, message_data, pending_location):
    """Handle user's response to location confirmation request"""
    message_text = ""
    
    # Extract text from message_data if available
    conversation = get_conversation(sender_id)
    if conversation and conversation.get('messages'):
        # Get the last message text
        last_message = conversation['messages'][-1]
        message_text = last_message.get('text', '')
    
    if not message_text:
        # If we can't get the message text, ask for confirmation again
        await ask_location_confirmation(sender_id, pending_location)
        return
    
    # First do a simple keyword check as a fast path
    message_lower = message_text.lower().strip()
    simple_yes_words = ['yes', 'si', 'sí', 'correct', 'correcto', 'exacto', 'perfecto', 'ok', 'okay']
    simple_no_words = ['no', 'nope', 'wrong', 'incorrect', 'incorrecto', 'mal']
    
    is_simple_yes = any(word == message_lower or message_lower.startswith(word + ' ') or message_lower.endswith(' ' + word) for word in simple_yes_words)
    is_simple_no = any(word == message_lower or message_lower.startswith(word + ' ') or message_lower.endswith(' ' + word) for word in simple_no_words)
    
    if is_simple_yes or is_simple_no:
        # Simple confirmation detected - handle immediately without LLM
        log_to_db("DEBUG", "Simple confirmation detected", {
            "sender_id": sender_id,
            "message_text": message_text,
            "is_yes": is_simple_yes,
            "is_no": is_simple_no
        })
        
        confirmation_result = {
            "is_confirmation": True,
            "confirmed": is_simple_yes
        }
    else:
        # Use LLM for more complex messages
        confirmation_result = await detect_confirmation(message_text)
        
        log_to_db("DEBUG", "LLM confirmation detection result", {
            "sender_id": sender_id,
            "message_text": message_text,
            "confirmation_result": confirmation_result
        })
    
    if confirmation_result.get('is_confirmation', False):
        if confirmation_result.get('confirmed', False):
            # User confirmed the location
            await update_conversation_location(sender_id, pending_location)
            
            # Update also in the patient collection
            await update_patient_location(sender_id, conversation, pending_location)
            
            clear_pending_location_confirmation(sender_id)
            reset_location_confirmation_attempts(sender_id)
            
            log_to_db("INFO", "Location confirmed and saved", {
                "sender_id": sender_id,
                "location": pending_location
            })
            
            # Send "searching for recommendations" message if user also has symptoms
            from utils.chat import has_symptoms
            conversation_refreshed = get_conversation(sender_id)
            if has_symptoms(conversation_refreshed):
                searching_message = "Thank you for confirming your location! I'm now finding the best medical recommendations for you. This may take a moment..."
                await send_translated_message(sender_id, searching_message)
            else:
                # Just confirm location was saved
                confirmation_message = "Perfect! Your location has been saved."
                await send_translated_message(sender_id, confirmation_message)
        else:
            # User rejected the location
            clear_pending_location_confirmation(sender_id)
            increment_location_confirmation_attempts(sender_id)
            
            # Check how many attempts they've made
            conversation = get_conversation(sender_id)
            attempts = conversation.get('location_confirmation_attempts', 0)
            
            if attempts >= 2:
                # After 2 failed attempts, only accept GPS location
                rejection_message = "I understand the location wasn't correct. Please use the button below to share your exact GPS location, or I won't be able to help you with location-based referrals."
                await send_translated_message(sender_id, rejection_message)
                await send_initial_location_request(sender_id)
            else:
                # Allow them to try again with text
                rejection_message = "I understand that location wasn't correct. Please try again with the name of your city or municipality, or use the GPS button below."
                await send_translated_message(sender_id, rejection_message)
                await send_initial_location_request(sender_id)
            
            log_to_db("INFO", "Location rejected by user", {
                "sender_id": sender_id,
                "rejected_location": pending_location,
                "attempts": attempts + 1
            })
    else:
        # Not a clear confirmation - log and ask again
        log_to_db("WARNING", "No clear confirmation detected, asking again", {
            "sender_id": sender_id,
            "message_text": message_text,
            "confirmation_result": confirmation_result if 'confirmation_result' in locals() else None
        })
        await ask_location_confirmation(sender_id, pending_location)

async def process_location_reference(sender_id, location_text):
    # Process location reference using geocoding API
    log_to_db("INFO", "Processing location reference", {
        "sender_id": sender_id,
        "location_text": location_text
    })
    
    # Check if user has exceeded confirmation attempts and should only use GPS
    conversation = get_conversation(sender_id)
    attempts = conversation.get('location_confirmation_attempts', 0)
    
    if attempts >= 2:
        # User has failed confirmation twice - only accept GPS
        gps_only_message = "Please use the GPS button below to share your exact location. I can no longer accept text-based location references."
        await send_translated_message(sender_id, gps_only_message)
        await send_initial_location_request(sender_id)
        return
    
    try:
        # Try to geocode the location
        lat, lon, formatted_address = await geocode_location(location_text)
        
        if lat and lon:
            # Location found in Guatemala - ask for confirmation
            location_data = {
                "lat": lat,
                "lon": lon,
                "text_description": formatted_address
            }
            
            # Store as pending confirmation
            set_pending_location_confirmation(sender_id, location_data)
            
            # Ask user to confirm
            await ask_location_confirmation(sender_id, location_data)
            
            log_to_db("INFO", "Location geocoded, asking for confirmation", {
                "sender_id": sender_id,
                "formatted_address": formatted_address,
                "coordinates": {"lat": lat, "lon": lon}
            })
                
        else:
            # Location not found in Guatemala
            increment_location_confirmation_attempts(sender_id)
            
            error_message = "I couldn't find that location in Guatemala. Please try the name of your city or municipality (e.g., 'Guatemala City,' 'Antigua Guatemala,' 'Quetzaltenango'), or use the GPS button below."
            await send_translated_message(sender_id, error_message)
            await send_initial_location_request(sender_id)
            
            log_to_db("WARNING", "Location not found in geocoding", {
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
    
    log_to_db("INFO", "Asked user for location confirmation", {
        "sender_id": sender_id,
        "location_to_confirm": location_data
    })

async def request_location(sender_id):
    # Send interactive location request
    await send_initial_location_request(sender_id)
    log_to_db("INFO", "Requested location from user", {"sender_id": sender_id})

async def update_conversation_location(sender_id, location_data):
    # Update conversation with location data
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"location": location_data}}
    )

# Update the patient's location in the patients collection
async def update_patient_location(sender_id, conversation, location_data):
    try:
        # Get current conversation data
        current_symptoms = conversation.get("symptoms", [])
        current_language = conversation.get("language")
        
        # Save/update to patient collection
        save_patient_data(
            phone_number=sender_id,
            symptoms=current_symptoms,
            location=location_data,
            language=current_language,
            urgency=None  # Always None (for now)
        )
        
        log_to_db("INFO", "Patient location updated in patients collection", {
            "sender_id": sender_id,
            "location": location_data
        })
        
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