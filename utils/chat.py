import os
from utils.db_tools import get_conversation, new_conversation, log_to_db
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
        
        # Store the GPS message
        from utils.db_tools import ongoing_conversations
        ongoing_conversations.update_one(
            {"sender_id": sender_id},
            {"$push": {"messages": {"sender": sender_id, "text": f"GPS location: {latitude}, {longitude}"}}}
        )

    # Process symptoms
    await process_symptoms_message(sender_id, conversation, message_data)
    
    # Process location with the message text for confirmation handling
    await process_location_message(sender_id, conversation, message_data, location_data)
    
    # Process language
    await process_language_message(sender_id, conversation, message_data)
    
    # Check if we have all required data and provide referral
    conversation = get_conversation(sender_id=sender_id)  # Refresh conversation
    if has_symptoms(conversation) and has_location(conversation):
        await provide_medical_referral(sender_id, conversation)
    else:
        # Missing data - ask for what's missing (only if not waiting for confirmation)
        pending_location = conversation.get("pending_location_confirmation")
        if not pending_location:  # Only ask for missing data if not waiting for confirmation
            if not has_symptoms(conversation):
                await request_symptoms(sender_id)
            elif not has_location(conversation):
                await request_location(sender_id)

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


#     async with httpx.AsyncClient() as client:
#         resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
#         return resp
#                 sender_id = message["from"]
#             message_type = message.get("type", "text")

#             # Check if user has location
#             if user_has_location(sender_id):
#                 # User has location, proceed with normal conversation
#                 if message_type == "text":
#                     text = message.get("text", {}).get("body", "")
#                     handle_conversation(sender_id, sender_id, text)
#                     chat_response = await get_completition(text)
#                     handle_conversation(sender_id, "botsito", chat_response)
#                     await send_text_message(sender_id, chat_response)
#                 else:
#                     # Non text message when user already has location
#                     text = f"Message type {message_type} received"
#                     handle_conversation(sender_id, sender_id, text)
#                     response_message = "I can only process text messages. Please send a text message."
#                     handle_conversation(sender_id, "botsito", response_message)
#                     await send_text_message(sender_id, response_message)
                    
#             else:
#                 # User doesnt have location yet
#                 if message_type == "text":
#                     text = message.get("text", {}).get("body", "")
#                     handle_conversation(sender_id, sender_id, text)
                    
#                     if is_waiting_for_location_reference(sender_id):
#                         # We are waiting for location reference, process it
#                         await process_location_reference(sender_id, text)
#                     else:
#                         # First message from user so the action is to send location request and set waiting flag
#                         await send_initial_location_request(sender_id)
                        
#                         # Set flag that we are now waiting for location reference
#                         set_waiting_for_location_reference(sender_id, True)
                        
#                         # Log that we sent the location request so NO procesamos el mensaje como ubicacion todavía
#                         initial_request_message = "Initial location request sent to user"
#                         handle_conversation(sender_id, "system", initial_request_message)

#                 elif message_type == "location":
#                     # GPS location message received
#                     location = message.get("location", {})
#                     latitude = location.get("latitude")
#                     longitude = location.get("longitude")
                    
#                     location_description = f"Coordinates: {latitude}, {longitude}"
                    
#                     location_data = {
#                         "lat": latitude,
#                         "lon": longitude,
#                         "text_description": location_description
#                     }
                    
#                     # Save location message
#                     text = f"GPS location received: {location_description}"
#                     handle_conversation(sender_id, sender_id, text, location_data)

#                     # Confirm location received and start normal conversation
#                     confirmation_message = f"Perfect! I've recorded your GPS location: {location_description}. I can now help you with medical referrals in your area. How can I help you?"
#                     handle_conversation(sender_id, "botsito", confirmation_message)
#                     await send_text_message(sender_id, confirmation_message)
                    
#                     # Clear waiting flag
#                     set_waiting_for_location_reference(sender_id, False)

#                 elif message_type == "interactive":
#                     # Handle interactive message responses
#                     interactive = message.get("interactive", {})
#                     interactive_type = interactive.get("type", "")
                    
#                     if interactive_type == "location_request_message":
#                         # User clicked on location request but didnt send location yet
#                         reminder_message = "Please share your GPS location or enter your city name to continue."
#                         handle_conversation(sender_id, "botsito", reminder_message)
#                         await send_text_message(sender_id, reminder_message)
                        
#                         # Set waiting flag
#                         set_waiting_for_location_reference(sender_id, True)

#                 else:
#                     # Other message types when user doesnt have location
#                     text = f"Message type {message_type} received"
#                     handle_conversation(sender_id, sender_id, text)
                    
#                     # Send location request
#                     await send_initial_location_request(sender_id)
#                     explanation = "I need your location so I can help you. Please share your GPS location using the button above, or type in your city name."
#                     handle_conversation(sender_id, "botsito", explanation)
#                     await send_text_message(sender_id, explanation)
                    
#                     # Set waiting flag
#                     set_waiting_for_location_reference(sender_id, True)
#     pass 

# async def send_initial_location_request(sender_id):
#     # Send initial location request message at conversation start
#     payload = {
#         "messaging_product": "whatsapp",
#         "to": sender_id,
#         "type": "interactive",
#         "interactive": {
#             "type": "location_request_message",
#             "body": {
#                 "text": "Hello! To provide you with the best medical referrals, I need to know your location. Please share your location using the button below, or simply type the name of your city (e.g., 'Antigua Guatemala')."
#             },
#             "action": {
#                 "name": "send_location"
#             }
#         }
#     }
    
#     async with httpx.AsyncClient() as client:
#         resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
#         # print(f"Initial location request sent: {resp.status_code}")
#         return resp


# async def process_location_reference(sender_id, location_text):
#     # Process location reference using geocoding API
#     try:
#         # Try to geocode the location
#         lat, lon, formatted_address = await geocode_location(location_text)
        
#         if lat and lon:
#             # Location found in Guatemala
#             location_data = {
#                 "lat": lat,
#                 "lon": lon,
#                 "text_description": formatted_address
#             }
            
#             # Save location to database
#             handle_conversation(sender_id, "system", f"Location geocoded: {formatted_address}", location_data)
            
#             # Send confirmation
#             confirmation_message = f"Great! I've found your location: {formatted_address}. I can now help you with medical referrals in your area. How can I help you?"
#             handle_conversation(sender_id, "botsito", confirmation_message)
#             await send_text_message(sender_id, confirmation_message)
            
#             # Clear waiting flag
#             set_waiting_for_location_reference(sender_id, False)
            
#             return True
#         else:
#             # Location not found in Guatemala
#             error_message = "I couldn't find that location in Guatemala. Please try the name of your city or municipality (e.g., 'Guatemala City,' 'Antigua Guatemala,' 'Quetzaltenango.')"
#             handle_conversation(sender_id, "botsito", error_message)
#             await send_text_message(sender_id, error_message)
            
#             return False
            
#     except Exception as e:
#         # print(f"Error processing location reference: {e}")
#         error_message = "There was an error processing your location. Please try again."
#         handle_conversation(sender_id, "botsito", error_message)
#         await send_text_message(sender_id, error_message)
        
#         return False

