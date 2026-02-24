from utils.db_tools import log_to_db, save_patient_data

async def process_language_message(sender_id, conversation, message_data):
    # Process language from extracted message data
    if not has_language(conversation) and message_data.get('language'): 
        await update_conversation_language(sender_id, message_data['language'])
        await update_patient_language(sender_id, conversation, message_data['language'])

async def update_conversation_language(sender_id, language):
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"language": language}}
    )

async def update_patient_language(sender_id, conversation, language):
    try:
        current_symptoms = conversation.get("symptoms", [])
        current_location = conversation.get("location")
        
        save_patient_data(
            phone_number=sender_id,
            symptoms=current_symptoms,
            location=current_location,
            language=language,
            urgency=None
        )
        
    except Exception as e:
        log_to_db("ERROR", "Error updating patient language", {
            "sender_id": sender_id,
            "error": str(e)
        })

def has_language(conversation): 
    language = conversation.get("language")
    return language is not None and language != ""