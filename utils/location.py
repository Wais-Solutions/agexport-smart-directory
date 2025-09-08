from utils.db_tools import log_to_db, get_conversation
from utils.llm import geocode_location
from utils.whatsapp import send_text_message, send_initial_location_request

async def process_location_message(sender_id, conversation, message_data, location_data):
    # Process location from message data or GPS coordinates
    if not has_location(conversation):
        if location_data:
            # Direct GPS location received
            await update_conversation_location(sender_id, location_data)
            log_to_db("INFO", "Location updated from GPS", {
                "sender_id": sender_id,
                "location": location_data
            })
        elif message_data.get('location'):
            # Text reference to location - need to geocode
            await process_location_reference(sender_id, message_data['location'])

async def process_location_reference(sender_id, location_text):
    # Process location reference using geocoding API
    log_to_db("INFO", "Processing location reference", {
        "sender_id": sender_id,
        "location_text": location_text
    })
    
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
            
            # Update conversation with location
            await update_conversation_location(sender_id, location_data)
            
            # Send confirmation
            confirmation_message = f"Perfect! I've found your location: {formatted_address}. I can now help you with medical referrals in your area."
            await send_text_message(sender_id, confirmation_message)
            
            log_to_db("INFO", "Location successfully geocoded and saved", {
                "sender_id": sender_id,
                "formatted_address": formatted_address,
                "coordinates": {"lat": lat, "lon": lon}
            })
                
        else:
            # Location not found in Guatemala
            error_message = "I couldn't find that location in Guatemala. Please try the name of your city or municipality (e.g., 'Guatemala City,' 'Antigua Guatemala,' 'Quetzaltenango.')."
            await send_text_message(sender_id, error_message)
            
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
        
        error_message = "There was an error processing your location. Please try again."
        await send_text_message(sender_id, error_message)

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

def has_location(conversation): 
    location = conversation.get("location")
    if location:
        lat = location.get("lat")
        lon = location.get("lon")
        return lat is not None and lon is not None
    return False