from pymongo import MongoClient
import os 
from datetime import datetime

mongo_user = os.getenv('GENEZ_MONGO_DB_USER')
mongo_psw = os.getenv('GENEZ_MONGO_DB_PSW')
mongo_host = os.getenv('GENEZ_MONGO_DB_HOST')
mongo_db = os.getenv('GENEZ_MONGO_DB_NAME')

client = MongoClient(f"mongodb+srv://{mongo_user}:{mongo_psw}@{mongo_host}/?retryWrites=true&w=majority")
db = client[mongo_db]

ongoing_conversations = db["ongoing_conversations"]
debugging_logs = db["debugging-logs"]
patients = db["patients"]
partners = db["partners"]

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

# [TEMP] Extract country code from phone number (simplified)
def get_country_from_phone(phone_number):
    try:
        # Add + if you don't have it
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number
        
        # Basic mapping of common country codes (you can expand this)
        country_codes = {
            '+502': {'country_code': 502, 'country_name': 'Guatemala'},
            '+1': {'country_code': 1, 'country_name': 'United States'},
            '+52': {'country_code': 52, 'country_name': 'Mexico'},
            '+503': {'country_code': 503, 'country_name': 'El Salvador'},
            '+504': {'country_code': 504, 'country_name': 'Honduras'},
            '+505': {'country_code': 505, 'country_name': 'Nicaragua'},
            '+506': {'country_code': 506, 'country_name': 'Costa Rica'},
            '+507': {'country_code': 507, 'country_name': 'Panama'}
        }
        
        # Search for country code matches
        for code, info in country_codes.items():
            if phone_number.startswith(code):
                return info
        
        # If Guatemala code not found, try to extract first digits
        if phone_number.startswith('+502'):
            return {'country_code': 502, 'country_name': 'Guatemala'}
        
        # Generic fallback
        return {'country_code': None, 'country_name': 'Unknown'}
        
    except Exception as e:
        log_to_db("ERROR", "Error extracting country from phone", {
            "phone_number": phone_number,
            "error": str(e)
        })
        return {'country_code': None, 'country_name': 'Unknown'}

# Save or update patient information in the patients collection
def save_patient_data(phone_number, symptoms=None, location=None, language=None, urgency=None):    
    try:
        # Get country information
        country_info = get_country_from_phone(phone_number)
        
        # Prepare patient data
        patient_data = {
            "phone_number": phone_number,
            "symptoms": symptoms or [],
            "location": location,
            "language": language,
            "country_code": country_info["country_code"],
            "country_name": country_info["country_name"],
            "urgency": urgency,  # Always None for now
            "updated_at": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        
        # Use upsert to update if exists or create if not exists
        result = patients.update_one(
            {"phone_number": phone_number},
            {
                "$set": {
                    "symptoms": symptoms or [],
                    "location": location,
                    "language": language,
                    "country_code": country_info["country_code"],
                    "country_name": country_info["country_name"],
                    "urgency": urgency,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "phone_number": phone_number,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        log_to_db("INFO", "Patient data saved", {
            "phone_number": phone_number,
            "symptoms": symptoms,
            "location": location,
            "language": language,
            "country": country_info["country_name"],
            "was_insert": result.upserted_id is not None
        })
        
        return True
        
    except Exception as e:
        log_to_db("ERROR", "Error saving patient data", {
            "phone_number": phone_number,
            "error": str(e)
        })
        return False

# Obtain patient information by phone number
def get_patient_data(phone_number):
    try:
        patient = patients.find_one({"phone_number": phone_number})
        return patient
    except Exception as e:
        log_to_db("ERROR", "Error getting patient data", {
            "phone_number": phone_number,
            "error": str(e)
        })
        return None