from utils.db_tools import log_to_db

async def process_language_message(sender_id, conversation, message_data):
    # Process language from extracted message data
    if not has_language(conversation) and message_data.get('language'): 
        await update_conversation_language(sender_id, message_data['language'])
        log_to_db("INFO", "Language updated", {
            "sender_id": sender_id,
            "language": message_data['language']
        })

async def update_conversation_language(sender_id, language):
    # Update conversation with language
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"language": language}}
    )

def has_language(conversation): 
    language = conversation.get("language")
    return language is not None and language != ""