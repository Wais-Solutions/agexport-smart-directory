import os
from groq import AsyncGroq
from utils.db_tools import log_to_db, get_conversation

# Initialize Groq client
groq_client = AsyncGroq()

# Translate a message to the target language using Groq LLM
async def translate_message(message_text, target_language, sender_id=None):
    # If target language is English or None, return original message
    if not target_language or target_language.lower() in ['english', 'en']:
        return message_text
    
    try:
        completion = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a professional medical translator. Translate the following medical/healthcare message to {target_language}. 

                    Rules:
                    - Maintain the exact meaning and tone
                    - Keep medical terminology accurate
                    - Preserve any formatting (line breaks, etc.)
                    - If the message is already in {target_language}, return it unchanged
                    - Return ONLY the translated text, no additional commentary
                    - Be culturally appropriate for the target language"""
                },
                {
                    "role": "user",
                    "content": message_text
                }
            ],
            temperature=0,
            # max_completion_tokens=1024,
            top_p=1,
            stream=False
        )
        
        translated_text = completion.choices[0].message.content.strip()
        
        log_to_db("INFO", "Message translated successfully", {
            "sender_id": sender_id,
            "original_language": "English",
            "target_language": target_language,
            "original_length": len(message_text),
            "translated_length": len(translated_text)
        })
        
        return translated_text
        
    except Exception as e:
        log_to_db("ERROR", "Translation failed", {
            "sender_id": sender_id,
            "target_language": target_language,
            "error": str(e),
            "original_message_length": len(message_text)
        })
        
        # Return original message if translation fails
        return message_text

# Get the users preferred language from their conversation
async def get_user_language(sender_id):
    try:
        conversation = get_conversation(sender_id)
        if conversation:
            return conversation.get('language')
        return None
    except Exception as e:
        log_to_db("ERROR", "Error getting user language", {
            "sender_id": sender_id,
            "error": str(e)
        })
        return None

# Send a message translated to the users preferred language
async def send_translated_message(sender_id, message_text, force_language=None):
    from utils.whatsapp import send_text_message
    
    # Determine target language
    target_language = force_language or await get_user_language(sender_id)
    
    # Translate message if needed
    if target_language and target_language.lower() not in ['english', 'en']:
        translated_message = await translate_message(message_text, target_language, sender_id)
    else:
        translated_message = message_text
    
    # Send the translated message
    return await send_text_message(sender_id, translated_message)