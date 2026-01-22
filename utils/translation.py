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
                    "content": f"""You are a professional medical translator. Your task is to translate the COMPLETE message to {target_language}. 

EXAMPLE OF CORRECT TRANSLATION:
Input: "I found this location: Antigua Guatemala. Is this correct? Please reply with 'yes' or 'no'."
Output (if target is Spanish): "Encontré esta ubicación: Antigua Guatemala. ¿Es correcto? Por favor responde con 'sí' o 'no'."

CRITICAL RULES:
- Translate the ENTIRE message - never shorten, summarize, or respond to it
- Place names, addresses, and proper nouns should REMAIN in their original form
  Examples: "Antigua Guatemala" stays as "Antigua Guatemala", "Paris" stays as "Paris"
- Do NOT confuse place names in the message with the target language
- When the message asks for 'yes' or 'no', translate the WHOLE question - do NOT just reply 'yes' or 'no'
- Maintain the exact meaning and tone of the entire message
- Keep medical terminology accurate
- Preserve ALL formatting (line breaks, punctuation, etc.)
- Return ONLY the FULL translated text, no additional commentary or responses
- Be culturally appropriate for the target language
- NEVER respond with just a single word unless the original is a single word
- If the message is already completely in {target_language}, return it COMPLETELY unchanged"""
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
        
        # Validation: if translation is suspiciously short compared to original, log warning
        if len(translated_text) < len(message_text) * 0.3:  # Less than 30% of original
            log_to_db("WARNING", "Translation seems too short, possible error", {
                "sender_id": sender_id,
                "original_message": message_text,
                "translated_message": translated_text,
                "original_length": len(message_text),
                "translated_length": len(translated_text),
                "target_language": target_language
            })
            # Still use it, but log the warning
        
        log_to_db("INFO", "Message translated successfully", {
            "sender_id": sender_id,
            "original_language": "English",
            "target_language": target_language,
            "original_message": message_text[:100],  # Log first 100 chars
            "translated_message": translated_text[:100],
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
    
    # Log original message before translation
    log_to_db("DEBUG", "Preparing to send translated message", {
        "sender_id": sender_id,
        "original_message": message_text,
        "message_length": len(message_text),
        "force_language": force_language
    })
    
    # Determine target language
    target_language = force_language or await get_user_language(sender_id)
    
    # Translate message if needed
    if target_language and target_language.lower() not in ['english', 'en']:
        translated_message = await translate_message(message_text, target_language, sender_id)
    else:
        translated_message = message_text
    
    # Final validation before sending
    if len(translated_message) < 3:
        log_to_db("ERROR", "Message too short, using original instead", {
            "sender_id": sender_id,
            "original_message": message_text,
            "translated_message": translated_message,
            "target_language": target_language
        })
        translated_message = message_text
    
    # Log what will actually be sent
    log_to_db("DEBUG", "Sending final message", {
        "sender_id": sender_id,
        "final_message": translated_message,
        "message_length": len(translated_message)
    })
    
    # Send the translated message
    return await send_text_message(sender_id, translated_message)