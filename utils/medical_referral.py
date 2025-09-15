from utils.db_tools import log_to_db
from utils.llm import get_completition
from utils.translation import send_translated_message

async def provide_medical_referral(sender_id, conversation):
    # Generate and send medical referral based on symptoms and location
    symptoms = conversation.get('symptoms', [])
    location = conversation.get('location', {})
    
    # Create prompt for medical referral
    symptoms_text = ", ".join(symptoms)
    location_text = location.get('text_description', 'ubicación no especificada')
    
    prompt = f"A patient at {location_text} presents with the following symptoms: {symptoms_text}. Provide an appropriate medical referral and suggest which type of specialist they should see."
    
    try:
        # Get medical recommendation
        recommendation = await get_completition(prompt)
        
        # Send recommendation to user (will be translated automatically)
        await send_translated_message(sender_id, recommendation)
        
        # Update conversation with recommendation
        await update_conversation_recommendation(sender_id, recommendation)
        
        log_to_db("INFO", "Medical referral provided", {
            "sender_id": sender_id,
            "symptoms": symptoms,
            "location": location_text,
            "recommendation": recommendation
        })
        
    except Exception as e:
        log_to_db("ERROR", "Error generating medical referral", {
            "sender_id": sender_id,
            "error": str(e)
        })
        
        error_message = "Sorry, there was an error generating your medical referral. Please try again."
        await send_translated_message(sender_id, error_message)

async def update_conversation_recommendation(sender_id, recommendation):
    # Update conversation with medical recommendation
    from utils.db_tools import ongoing_conversations
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"recommendation": recommendation}}
    )