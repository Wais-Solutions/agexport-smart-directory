import os
from groq import AsyncGroq
from utils.db_tools import log_to_db, get_conversation

groq_client = AsyncGroq()

async def translate_message(message_text, target_language, sender_id=None):
    if not target_language or target_language.lower() in ['english', 'en']:
        return message_text
    
    try:
        completion = await groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
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
            top_p=1,
            stream=False
        )
        
        translated_text = completion.choices[0].message.content.strip()
        
        if len(translated_text) < len(message_text) * 0.3:
            log_to_db("ERROR", "Translation result suspiciously short", {
                "sender_id": sender_id,
                "original_message": message_text,
                "translated_message": translated_text,
                "target_language": target_language
            })
        
        return translated_text
        
    except Exception as e:
        log_to_db("ERROR", "Translation failed", {
            "sender_id": sender_id,
            "target_language": target_language,
            "error": str(e)
        })
        return message_text

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

async def send_translated_message(sender_id, message_text, force_language=None):
    from utils.whatsapp import send_text_message
    
    target_language = force_language or await get_user_language(sender_id)
    
    if target_language and target_language.lower() not in ['english', 'en']:
        translated_message = await translate_message(message_text, target_language, sender_id)
    else:
        translated_message = message_text
    
    if len(translated_message) < 3:
        log_to_db("ERROR", "Translated message too short, using original", {
            "sender_id": sender_id,
            "original_message": message_text,
            "translated_message": translated_message,
            "target_language": target_language
        })
        translated_message = message_text
    
    return await send_text_message(sender_id, translated_message)