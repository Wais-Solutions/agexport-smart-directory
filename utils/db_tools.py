from pymongo import MongoClient
import os 
import datetime 

mongo_user = os.getenv('GENEZ_MONGO_DB_USER')
mongo_psw = os.getenv('GENEZ_MONGO_DB_PSW')
mongo_host = os.getenv('GENEZ_MONGO_DB_HOST')
mongo_db = os.getenv('GENEZ_MONGO_DB_NAME')

client = MongoClient(f"mongodb+srv://{mongo_user}:{mongo_psw}@{mongo_host}/?retryWrites=true&w=majority")
db = client[mongo_db]

ongoing_conversations = db["ongoing_conversations"]
debugging_logs = db["debugging-logs"]


def log_to_db(level, message, extra_data=None):
    # Save log messages to MongoDB debugging-logs collection
    # level: "INFO", "ERROR", "WARNING", "DEBUG"
    # message: string with the log message
    # extra_data: optional dict with additional data
    try:
        log_entry = {
            "timestamp": datetime.utcnow(),
            "level": level,
            "message": message,
            "extra_data": extra_data if extra_data else {}
        }
        debugging_logs.insert_one(log_entry)
    except Exception as e:
        # Fallback to print if database logging fails
        print(f"Failed to log to database: {e}")
        print(f"Original log - {level}: {message}")
        if extra_data:
            print(f"Extra data: {extra_data}")

def get_conversation(sender_id): 
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    return conversation
    
def new_conversation(sender_id): 
    # If the sender doesn't exist, create a new document
    new_conversation = {
        "sender_id": sender_id,
        "symptoms": [],
        "location": {"lat": None, "lon": None, "text_description": None},
        "language": None,
        "messages": [],
        "recommendation": None,
        "waiting_for_location_reference": False,  # Flag to know if we're waiting for location reference
        "pending_location_confirmation": None,  # Stores location data waiting for confirmation
        "location_confirmation_attempts": 0  # Track failed confirmation attempts
    }
    
    ongoing_conversations.insert_one(new_conversation)

    return new_conversation

def set_pending_location_confirmation(sender_id, location_data):
    # Store location data that needs user confirmation
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"pending_location_confirmation": location_data}}
    )

def get_pending_location_confirmation(sender_id):
    # Get location data pending confirmation
    conversation = ongoing_conversations.find_one({"sender_id": sender_id})
    if conversation:
        return conversation.get("pending_location_confirmation")
    return None

def clear_pending_location_confirmation(sender_id):
    # Clear pending location confirmation
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$unset": {"pending_location_confirmation": ""}}
    )

def increment_location_confirmation_attempts(sender_id):
    # Increment the number of failed location confirmation attempts
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$inc": {"location_confirmation_attempts": 1}}
    )

def reset_location_confirmation_attempts(sender_id):
    # Reset location confirmation attempts counter
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"location_confirmation_attempts": 0}}
    )