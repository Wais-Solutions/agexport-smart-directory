import os 
import httpx
from pymongo import MongoClient
from groq import AsyncGroq

# Connect to MongoDB

mongo_user = os.getenv('GENEZ_MONGO_DB_USER')
mongo_psw = os.getenv('GENEZ_MONGO_DB_PSW')
mongo_host = os.getenv('GENEZ_MONGO_DB_HOST')
mongo_db = os.getenv('GENEZ_MONGO_DB_NAME')

client = MongoClient(f"mongodb+srv://{mongo_user}:{mongo_psw}@{mongo_host}/?retryWrites=true&w=majority")
db = client[mongo_db]

ongoing_conversations = db["ongoing_conversations"]

def handle_conversation(convo_id, sender_id, text, location_data=None):
    # Look for the sender in the ongoing_conversations collection
    conversation = ongoing_conversations.find_one({"sender_id": convo_id})
    
    if conversation:
        # If the sender exists, add the text to the messages array
        message_data = {"sender": sender_id, "text": text}

        # If theres location data, update the location in the document
        if location_data:
            ongoing_conversations.update_one(
                {"sender_id": convo_id},
                {
                    "$push": {"messages": message_data},
                    "$set": {"location": location_data}
                }
            )
        else:
            ongoing_conversations.update_one(
                {"sender_id": convo_id},
                {"$push": {"messages": message_data}}
            )
    else:
        # If the sender doesn't exist, create a new document
        new_conversation = {
            "sender_id": convo_id,
            "symptoms": [],
            "location": location_data if location_data else {"lat": None, "lon": None, "text_description": None},
            "language": None,
            "messages": [{"sender": sender_id, "text": text}],
            "recommendation": None,
            "waiting_for_location_reference": False  # Flag to know if we're waiting for location reference
        }
        ongoing_conversations.insert_one(new_conversation)

def user_has_location(sender_id):
    # Check if user has already provided location
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    if conversation:
        location = conversation.get("location")
        # Check if location object exists and has any valid data
        if location:
            lat = location.get("lat")
            lon = location.get("lon")
            # User has location if lat AND lon are not None
            return lat is not None and lon is not None
        return False
    return False

def set_waiting_for_location_reference(sender_id, waiting=True):
    # Set flag to indicate we're waiting for location reference
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"waiting_for_location_reference": waiting}}
    )

def is_waiting_for_location_reference(sender_id):
    # Check if we're waiting for location reference
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    if conversation:
        return conversation.get("waiting_for_location_reference", False)
    return False

async def geocode_location(location_text):
    # Use Google Maps Geocoding API to get coordinates from location text
    # Returns tuple (lat, lon, formatted_address) or (None, None, None) if not found in Guatemala
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    
    if not api_key:
        print("Google Maps API key not found")
        return None, None, None
    
    # Add "Guatemala" to the search to bias results towards Guatemala
    search_query = f"{location_text}, Guatemala"
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        'address': search_query,
        'key': api_key,
        'region': 'gt',  # Bias towards Guatemala
        'components': 'country:GT'  # Restrict to Guatemala only
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]
                
                # Check if the result is actually in Guatemala
                country_found = False
                for component in result['address_components']:
                    if 'country' in component['types'] and component['short_name'] == 'GT':
                        country_found = True
                        break
                
                if country_found:
                    location = result['geometry']['location']
                    lat = location['lat']
                    lon = location['lng']
                    formatted_address = result['formatted_address']
                    
                    print(f"Geocoded location: {formatted_address} -> {lat}, {lon}")
                    return lat, lon, formatted_address
                else:
                    print(f"Location not found in Guatemala: {location_text}")
                    return None, None, None
            else:
                print(f"Geocoding failed: {data.get('status', 'Unknown error')}")
                return None, None, None
                
    except Exception as e:
        print(f"Error in geocoding: {e}")
        return None, None, None

groq_api = os.getenv('GROQ_API_KEY')
client = AsyncGroq(api_key = groq_api)

async def get_completition(prompt): 
    response = await client.chat.completions.create(
        model = "llama-3.3-70b-versatile"
        , messages = [
            {"role" : "system", "content": "You are a recommendation engine of good medical professionals. Be concise and respectful."}
            , {"role" : "user", "content": prompt}
        ]
        , temperature = 0.8 
        , max_completion_tokens = 120
        , top_p= 1 
    )

    return response.choices[0].message.content