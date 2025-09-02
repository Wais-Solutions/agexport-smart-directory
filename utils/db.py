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
        "waiting_for_location_reference": False  # Flag to know if we're waiting for location reference
    }
    
    ongoing_conversations.insert_one(new_conversation)

    return new_conversation