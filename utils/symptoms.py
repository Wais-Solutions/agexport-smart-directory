from utils.db_tools import log_to_db, save_patient_data
from utils.translation import send_translated_message

async def process_symptoms_message(sender_id, conversation, message_data):
    if not has_symptoms(conversation) and message_data.get('symptoms'): 
        await update_conversation_symptoms(sender_id, message_data['symptoms'])
        await update_patient_symptoms(sender_id, conversation, message_data['symptoms'])
        
        log_to_db("INFO", "Symptoms received and saved", {
            "sender_id": sender_id,
            "symptoms": message_data['symptoms']
        })

async def request_symptoms(sender_id):
    message = "Hello! In order to help you with a medical referral, I need to know what symptoms you're experiencing. Please describe any discomfort or symptoms you're experiencing."
    await send_translated_message(sender_id, message)

async def update_conversation_symptoms(sender_id, symptoms):
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"symptoms": symptoms}}
    )

async def update_patient_symptoms(sender_id, conversation, symptoms):
    try:
        current_location = conversation.get("location")
        current_language = conversation.get("language")
        
        save_patient_data(
            phone_number=sender_id,
            symptoms=symptoms,
            location=current_location,
            language=current_language,
            urgency=None
        )
        
    except Exception as e:
        log_to_db("ERROR", "Error updating patient symptoms", {
            "sender_id": sender_id,
            "error": str(e)
        })

def has_symptoms(conversation): 
    symptoms = conversation.get("symptoms")
    if symptoms:
        return len(symptoms) > 0
    return False