from utils.db_tools import log_to_db
from utils.whatsapp import send_text_message

async def process_symptoms_message(sender_id, conversation, message_data):
    # Process symptoms from extracted message data
    if not has_symptoms(conversation) and message_data.get('symptoms'): 
        await update_conversation_symptoms(sender_id, message_data['symptoms'])
        log_to_db("INFO", "Symptoms updated", {
            "sender_id": sender_id,
            "symptoms": message_data['symptoms']
        })

async def request_symptoms(sender_id):
    # Ask user for symptoms
    message = "Hello! In order to help you with a medical referral, I need to know what symptoms you're experiencing. Please describe any discomfort or symptoms you're experiencing."
    await send_text_message(sender_id, message)
    log_to_db("INFO", "Requested symptoms from user", {"sender_id": sender_id})

async def update_conversation_symptoms(sender_id, symptoms):
    # Update conversation with symptoms
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"symptoms": symptoms}}
    )

def has_symptoms(conversation): 
    symptoms = conversation.get("symptoms")
    if symptoms:
        return len(symptoms) > 0
    return False