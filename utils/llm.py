import os 
import httpx

from groq import AsyncGroq
from datetime import datetime

from groq import AsyncGroq
import json 
import asyncio 

from utils.db_tools import log_to_db, ongoing_conversations


groq_client = AsyncGroq()
async def extract_data(message): 
    completion = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile"
        , messages=[
        {
            "role": "system",
            "content": "You are an information extraction assistant. Given a text message, extract the following fields and return them strictly in JSON format:\n\n{\n  \"location\": string | None,\n  \"symptoms\": array of strings | None,\n  \"language\": string | None\n}\n\nRules:\n- \"location\" must be a clear geographical entity: city, state, country, neighborhood, or publicly known place (e.g., \"Times Square\", \"Central Park\", \"Fifth Avenue\").\n- Do NOT use vague places (e.g., \"my hotel\", \"a pool\", \"a park\", \"the mall\"). Only accept a park if it is a specifically named, publicly recognized one.\n- Patients might use popular landmarks or well-known places as location references—these should be included.\n- correct mispellings\n- separate distinct symptoms into an array\n- \"language\" must be extracted as the full language name in English (e.g.,\"English\",  \"Spanish\", \"French\", \"Mandarin Chinese\"), not abbreviations or codes.\n- If any field is not present in the text, set it to None.\n- translate all results to english.\n- Return only the JSON, with no extra commentary.\n"
        },
        {
            "role": "user",
            "content": message
        }
        ],
        temperature=0,
        max_completion_tokens=8192,
        top_p=1,
        stream=True,
        stop=None
    )

    response = ""
    
    async for chunk in completion:
        response += chunk.choices[0].delta.content or ""

    try:
        data = json.loads(response)
    except Exception:
        data = {"location": None, "symptoms": [], "language": None}

    return data




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
        log_to_db("ERROR", "Google Maps API key not found")
        return None, None, None
    
    log_to_db("INFO", f"Trying to geocode location", {"location_text": location_text})
    
    # Try multiple search variations
    search_queries = [
        f"{location_text}, Guatemala",
        location_text,
        f"{location_text}, GT"
    ]
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    for search_query in search_queries:
        log_to_db("DEBUG", f"Searching for location", {"search_query": search_query})
        
        params = {
            'address': search_query,
            'key': api_key,
            'region': 'gt',  # Bias towards Guatemala
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params)
                data = response.json()
                
                api_status = data.get('status')
                results_count = len(data.get('results', []))
                
                log_to_db("DEBUG", "Geocoding API response", {
                    "search_query": search_query,
                    "api_status": api_status,
                    "results_count": results_count
                })
                
                if data['status'] == 'OK' and data['results']:
                    result = data['results'][0]
                    
                    # Check if the result is actually in Guatemala
                    country_found = False
                    country_short = ""
                    for component in result['address_components']:
                        if 'country' in component['types']:
                            country_short = component['short_name']
                            if component['short_name'] == 'GT':
                                country_found = True
                            break
                    
                    log_to_db("DEBUG", "Country check in geocoding result", {
                        "search_query": search_query,
                        "country_found": country_found,
                        "country_short": country_short
                    })
                    
                    if country_found:
                        location = result['geometry']['location']
                        lat = location['lat']
                        lon = location['lng']
                        formatted_address = result['formatted_address']
                        
                        log_to_db("INFO", "Successfully geocoded location", {
                            "location_text": location_text,
                            "formatted_address": formatted_address,
                            "lat": lat,
                            "lon": lon
                        })
                        
                        return lat, lon, formatted_address
                    else:
                        log_to_db("DEBUG", "Result not in Guatemala, trying next variation", {
                            "search_query": search_query,
                            "country_short": country_short
                        })
                        continue
                else:
                    error_detail = data.get('error_message', 'No error message')
                    log_to_db("WARNING", "Geocoding failed for search query", {
                        "search_query": search_query,
                        "api_status": api_status,
                        "error_detail": error_detail
                    })
                    continue
                    
        except Exception as e:
            log_to_db("ERROR", "Exception in geocoding", {
                "search_query": search_query,
                "error": str(e)
            })
            continue
    
    log_to_db("WARNING", "Could not find location in Guatemala after trying all variations", {
        "location_text": location_text,
        "search_queries_tried": search_queries
    })
    
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