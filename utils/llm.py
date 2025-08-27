import os 
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
            "location_method_selected": None,  # Track which location method user chose
            "waiting_for_text_location": False  # Flag to know if we're waiting for text location
        }
        ongoing_conversations.insert_one(new_conversation)

def user_has_location(sender_id):
    # Check if user has already provided location
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    if conversation and conversation.get("location"):
        location = conversation["location"]
        return location.get("lat") is not None and location.get("lon") is not None
    return False

def user_has_selected_location_method(sender_id):
    # Check if user has selected a location method
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    if conversation:
        return conversation.get("location_method_selected") is not None
    return False

def set_location_method(sender_id, method):
    # Set the selected location method for the user
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"location_method_selected": method}}
    )

def set_waiting_for_text_location(sender_id, waiting=True):
    # Set flag to indicate we're waiting for text location reference
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"waiting_for_text_location": waiting}}
    )

def is_waiting_for_text_location(sender_id):
    # Check if we're waiting for text location reference
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    if conversation:
        return conversation.get("waiting_for_text_location", False)
    return False

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