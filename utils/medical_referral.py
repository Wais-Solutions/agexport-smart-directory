from utils.db_tools import log_to_db
from utils.llm import get_completition
from utils.translation import send_translated_message
from datetime import datetime

async def provide_medical_referral(sender_id, conversation):
    # Generate and send medical referral based on symptoms and location
    symptoms = conversation.get('symptoms', [])
    location = conversation.get('location', {})
    
    # Create prompt for medical referral
    symptoms_text = ", ".join(symptoms)
    location_text = location.get('text_description', 'ubicación no especificada')
    
    try:
        # Search for partners that match the patient's needs
        matching_partners = await find_matching_partners(symptoms, location)
        
        if matching_partners:
            # Found matching partners - send their information
            referral_message = await format_partner_referrals(matching_partners)
            await send_translated_message(sender_id, referral_message)
            
            # Save referrals to the referrals table
            await save_referrals(sender_id, matching_partners, symptoms, location)
            
            log_to_db("INFO", "Medical referral provided with partners", {
                "sender_id": sender_id,
                "symptoms": symptoms,
                "location": location_text,
                "partners_found": len(matching_partners),
                "partner_names": [p["nombre_comercial"] for p in matching_partners]
            })
        else:
            # No matching partners found - send apology
            apology_message = "I apologize, but I couldn't find medical partners in your area that specialize in your specific symptoms at this time. Please consider contacting your local hospital or health center for assistance."
            await send_translated_message(sender_id, apology_message)
            
            log_to_db("INFO", "No matching partners found", {
                "sender_id": sender_id,
                "symptoms": symptoms,
                "location": location_text
            })
        
        # Update conversation with recommendation
        await update_conversation_recommendation(sender_id, matching_partners if matching_partners else "No partners found")
        
    except Exception as e:
        log_to_db("ERROR", "Error generating medical referral", {
            "sender_id": sender_id,
            "error": str(e)
        })
        
        error_message = "Sorry, there was an error processing your medical referral request. Please try again."
        await send_translated_message(sender_id, error_message)

# Find partners that match the patients symptoms and location
async def find_matching_partners(symptoms, location):
    from utils.db_tools import db
    
    try:
        partners = db["partners"]
        patient_department = None
        
        # Extract department from location
        if location and location.get('text_description'):
            patient_department = await extract_department_from_location(location['text_description'])
        
        # Get all partners (well filter programmatically for better control)
        all_partners = list(partners.find({}))
        
        matching_partners = []
        
        for partner in all_partners:
            match_score = 0
            reasons = []
            
            # Check location match (department level)
            if patient_department and partner.get('ubicaciones'):
                for ubicacion in partner['ubicaciones']:
                    if ubicacion.get('departamento', '').upper() == patient_department.upper():
                        match_score += 10
                        reasons.append("same_department")
                        break
            
            # Check specialty match using LLM
            if symptoms and partner.get('especialidades'):
                specialty_match = await check_specialty_match(symptoms, partner['especialidades'])
                if specialty_match:
                    match_score += specialty_match  # LLM returns confidence score
                    reasons.append("specialty_match")
            
            # If we have a reasonable match, include the partner
            if match_score >= 5:  # Minimum threshold
                partner['match_score'] = match_score
                partner['match_reasons'] = reasons
                matching_partners.append(partner)
        
        # Sort by match score (highest first) and return top 3
        matching_partners.sort(key=lambda x: x['match_score'], reverse=True)
        
        log_to_db("INFO", "Partner search completed", {
            "patient_department": patient_department,
            "symptoms": symptoms,
            "total_partners_checked": len(all_partners),
            "matches_found": len(matching_partners),
            "top_matches": [p["nombre_comercial"] for p in matching_partners[:3]]
        })
        
        return matching_partners[:3]  # Return top 3 matches
        
    except Exception as e:
        log_to_db("ERROR", "Error searching for partners", {
            "error": str(e),
            "symptoms": symptoms,
            "location": location
        })
        return []

# Extract department from location text using LL
async def extract_department_from_location(location_text):
    try:
        from utils.llm import groq_client
        
        completion = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """You are a location analyzer for Guatemala. Extract the department (departamento) from the given location text.

                    Guatemala departments include: Guatemala, Sacatepéquez, Chimaltenango, Escuintla, Santa Rosa, Sololá, Totonicapán, Quetzaltenango, Suchitepéquez, Retalhuleu, San Marcos, Huehuetenango, Quiché, Baja Verapaz, Alta Verapaz, Petén, Izabal, Zacapa, Chiquimula, Jalapa, Jutiapa.

                    Return only the department name, nothing else. If unclear, return the most likely department."""
                },
                {
                    "role": "user",
                    "content": location_text
                }
            ],
            temperature=0,
            # max_completion_tokens=50,
            stream=False
        )
        
        department = completion.choices[0].message.content.strip()
        return department
        
    except Exception as e:
        log_to_db("ERROR", "Error extracting department", {
            "location_text": location_text,
            "error": str(e)
        })
        return None

# Check if partners specialties match patients symptoms using LLM
# Returns confidence score (0-10)
async def check_specialty_match(symptoms, specialties):
    try:
        from utils.llm import groq_client
        
        symptoms_text = ", ".join(symptoms)
        specialties_text = ", ".join(specialties)
        
        completion = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """You are a medical specialty matcher. Given patient symptoms and medical specialties, determine how well they match.

                    Return a JSON with:
                    {
                        "confidence_score": number (0-10, where 10 is perfect match),
                        "reasoning": "brief explanation"
                    }

                    Consider:
                    - Direct specialty matches (e.g., dental symptoms → dental specialties)
                    - General medicine can handle many common symptoms
                    - Emergency/hospital services for urgent symptoms
                    - Specialist referrals for specific conditions

                    Return only the JSON, no extra text."""
                },
                {
                    "role": "user",
                    "content": f"Patient symptoms: {symptoms_text}\nAvailable specialties: {specialties_text}"
                }
            ],
            temperature=0,
            # max_completion_tokens=150,
            stream=False
        )
        
        import json
        response = completion.choices[0].message.content.strip()
        result = json.loads(response)
        
        confidence_score = result.get('confidence_score', 0)
        
        log_to_db("DEBUG", "Specialty match check", {
            "symptoms": symptoms_text,
            "specialties": specialties_text,
            "confidence_score": confidence_score,
            "reasoning": result.get('reasoning', '')
        })
        
        return confidence_score
        
    except Exception as e:
        log_to_db("ERROR", "Error checking specialty match", {
            "symptoms": symptoms,
            "specialties": specialties,
            "error": str(e)
        })
        return 0

# Format the partner information into a user friendly message
async def format_partner_referrals(partners):
    if not partners:
        return "No medical partners found for your needs."
    
    message_parts = ["I found the following medical partners for you:\n"]
    
    for i, partner in enumerate(partners, 1):
        # Partner name and location
        name = partner.get('nombre_comercial', 'Unknown')
        ubicaciones = partner.get('ubicaciones', [])
        direccion = ubicaciones[0].get('direccion', 'Address not available') if ubicaciones else 'Address not available'
        
        # Schedule
        horario = partner.get('horario_atencion', {})
        schedule_info = format_schedule(horario)
        
        # Languages
        idiomas = partner.get('idiomas_atencion', [])
        languages = ", ".join(idiomas) if idiomas else "Information not available"
        
        # Price scale
        escala_precios = partner.get('escala_precios', 'Information not available')
        
        # Contact for patients
        contacto = partner.get('contacto_pacientes', {})
        phone = contacto.get('telefono', 'Not available')
        whatsapp = contacto.get('whatsapp', 'Not available')
        
        partner_info = f"""
        {i}. {name}
        - Location: {direccion}
        - Schedule: {schedule_info}
        - Price range: {escala_precios}
        - Languages: {languages}
        - Phone: {phone}
        - WhatsApp: {whatsapp}
        """
        message_parts.append(partner_info)
    
    message_parts.append("\nPlease contact them directly to schedule an appointment.")
    
    return "\n".join(message_parts)

# Format schedule information into readable text
def format_schedule(horario_atencion):
    if not horario_atencion:
        return "Information not available"
    
    schedule_parts = []
    
    if horario_atencion.get('lunes_viernes'):
        schedule_parts.append(f"Mon-Fri: {horario_atencion['lunes_viernes']}")
    
    if horario_atencion.get('sabado'):
        schedule_parts.append(f"Sat: {horario_atencion['sabado']}")
    
    if horario_atencion.get('domingo'):
        schedule_parts.append(f"Sun: {horario_atencion['domingo']}")
    
    if horario_atencion.get('emergencias'):
        schedule_parts.append(f"Emergency: {horario_atencion['emergencias']}")
    
    return " | ".join(schedule_parts) if schedule_parts else "Information not available"

async def update_conversation_recommendation(sender_id, recommendation):
    # Update conversation with medical recommendation
    from utils.db_tools import ongoing_conversations
    
    # Convert recommendation to string if it's a list of partners
    if isinstance(recommendation, list):
        if recommendation:
            recommendation_text = f"Found {len(recommendation)} partners: " + ", ".join([p.get('nombre_comercial', 'Unknown') for p in recommendation])
        else:
            recommendation_text = "No partners found"
    else:
        recommendation_text = str(recommendation)
    
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"recommendation": recommendation_text}}
    )

# Save referrals to the referrals collection
async def save_referrals(sender_id, partners, symptoms, location):
    try:
        from utils.db_tools import db
        
        referrals = db["referrals"]
        
        # Extract department from location for department match tracking
        patient_department = None
        if location and location.get('text_description'):
            patient_department = await extract_department_from_location(location['text_description'])
        
        # Create a referral record for each partner
        referral_records = []
        
        for partner in partners:
            # Check if partner is in same department
            department_match = False
            if patient_department and partner.get('ubicaciones'):
                for ubicacion in partner['ubicaciones']:
                    if ubicacion.get('departamento', '').upper() == patient_department.upper():
                        department_match = True
                        break
            
            referral_record = {
                "patient_phone_number": sender_id,
                "partner_id": partner.get('_id'),
                "partner_name": partner.get('nombre_comercial'),
                "symptoms_matched": symptoms,
                "department_match": patient_department if department_match else None,
                "referred_at": datetime.utcnow(),
                "status": "sent"
            }
            
            referral_records.append(referral_record)
        
        # Insert all referral records
        if referral_records:
            result = referrals.insert_many(referral_records)
            
            log_to_db("INFO", "Referrals saved to database", {
                "patient_phone_number": sender_id,
                "referrals_count": len(referral_records),
                "partner_names": [r["partner_name"] for r in referral_records],
                "inserted_ids": [str(id) for id in result.inserted_ids]
            })
            
        return True
        
    except Exception as e:
        log_to_db("ERROR", "Error saving referrals", {
            "patient_phone_number": sender_id,
            "error": str(e),
            "symptoms": symptoms,
            "partners_count": len(partners) if partners else 0
        })
        return False