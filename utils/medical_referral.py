from utils.db_tools import log_to_db
from utils.translation import send_translated_message
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json

# Maximum distance in kilometers based on location type
MAX_DISTANCE_GPS = 30  # For GPS locations (precise)
MAX_DISTANCE_TEXT = 60  # For text-based locations (less precise, wider search)

# Weights for combining symptom and specialty similarity
SYMPTOM_WEIGHT = 0.7
SPECIALTY_WEIGHT = 0.3

# Minimum similarity threshold
SIMILARITY_THRESHOLD = 0.4

# Initialize the sentence transformer model (lazy loading)
_model = None

def get_embedding_model():
    """Lazy load the sentence transformer model"""
    global _model
    if _model is None:
        _model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    return _model

def generate_embeddings(query: str):
    """Generate embeddings for a given text query"""
    model = get_embedding_model()
    return model.encode(query)

async def extract_symptoms_specialties(message: str) -> tuple:
    """
    Extract symptoms and potential medical specialties from the message using Groq LLM
    Returns: (result_dict, success_flag)
    """
    from groq import AsyncGroq
    
    groq_client = AsyncGroq()
    
    try:
        response = await groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "Analiza el siguiente mensaje y extrae una lista de síntomas, enfermedades o condiciones que puedan inferirse directamente de su contenido. No agregues, supongas ni completes información que no esté explícita o implícitamente presente en el texto. A continuación, genera una segunda lista con las especialidades médicas o tipos de atención en salud que podrían abordar dichas condiciones. Si no puedes encontrar nada relevante, retorna el mensaje íntegro y el campo contains_info como False. Mantén todas tus respuestas en español."
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "specialty_mapping",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string"},
                            "contains_info": {"type": "boolean"},
                            "symptoms": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "specialties": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["message", "contains_info", "symptoms", "specialties"],
                        "additionalProperties": False
                    }
                }
            }
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        return result, True
        
    except Exception as e:
        log_to_db("ERROR", "Error extracting symptoms and specialties", {
            "sender_id": None,
            "error": str(e),
            "message": message
        })
        result = {
            'message': message,
            'contains_info': False,
            'symptoms': [],
            'specialties': []
        }
        return result, False

def calculate_similarity_scores(query_embedding, partner_embeddings_list):
    """
    Calculate cosine similarity between query embedding and multiple partner embeddings
    """
    try:
        query_embedding = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        partner_embeddings_matrix = np.array(partner_embeddings_list, dtype=np.float32)
        similarity_scores = cosine_similarity(query_embedding, partner_embeddings_matrix)[0]
        return similarity_scores.tolist()
        
    except Exception as e:
        log_to_db("ERROR", "Error calculating similarity scores", {"sender_id": None, "error": str(e)})
        return [0.0] * len(partner_embeddings_list)

async def provide_medical_referral(sender_id, conversation):
    """Generate and send medical referral based on symptoms and location"""
    symptoms = conversation.get('symptoms', [])
    location = conversation.get('location', {})
    
    symptoms_text = ", ".join(symptoms)
    location_text = location.get('text_description', 'ubicación no especificada')
    
    location_type = location.get('location_type', 'gps')
    max_distance_km = MAX_DISTANCE_GPS if location_type == 'gps' else MAX_DISTANCE_TEXT
    
    try:
        matching_partners = await find_matching_partners(symptoms, location, max_distance_km)
        
        if matching_partners:
            referral_message = await format_partner_referrals(matching_partners)
            await send_translated_message(sender_id, referral_message)
            await save_referrals(sender_id, matching_partners, symptoms, location)
            
            log_to_db("INFO", "Partner match found", {
                "sender_id": sender_id,
                "symptoms": symptoms,
                "partners": [
                    {
                        "name": p.get("partner_name"),
                        "distance_km": round(p.get("distance_km", 0), 2),
                        "similarity": round(p.get("overall_similarity", 0), 4)
                    }
                    for p in matching_partners
                ]
            })
        else:
            best_match = await find_matching_partners(symptoms, location, max_distance_km=None)
            
            if best_match:
                fallback_message = await format_fallback_referral(best_match[0], max_distance_km)
                await send_translated_message(sender_id, fallback_message)
                await save_referrals(sender_id, [best_match[0]], symptoms, location, is_fallback=True)
                
                log_to_db("INFO", "Partner match found (outside radius fallback)", {
                    "sender_id": sender_id,
                    "symptoms": symptoms,
                    "partner": best_match[0].get("partner_name"),
                    "distance_km": round(best_match[0].get("distance_km", 0), 2),
                    "search_radius_km": max_distance_km
                })
            else:
                apology_message = f"I apologize, but I couldn't find any medical partners that specialize in your symptoms. Please consider contacting your local hospital or health center for assistance."
                await send_translated_message(sender_id, apology_message)
                
                log_to_db("INFO", "No matching partners found", {
                    "sender_id": sender_id,
                    "symptoms": symptoms,
                    "location": location_text
                })
        
        await update_conversation_recommendation(sender_id, matching_partners if matching_partners else "No partners found")
        
        from utils.db_tools import increment_referral_count, set_waiting_for_another_referral, get_conversation
        
        increment_referral_count(sender_id)
        conversation = get_conversation(sender_id)
        referral_count = conversation.get('referral_count', 0)
        
        if referral_count < 4:
            another_referral_message = "\n\nDo you need another medical referral for different symptoms? Reply 'yes' or 'no'."
            await send_translated_message(sender_id, another_referral_message)
            set_waiting_for_another_referral(sender_id, True)
        else:
            limit_message = "\n\nYou have reached the maximum number of referrals (4) for this session. If you need more assistance, please start a new conversation with /reset."
            await send_translated_message(sender_id, limit_message)
        
    except Exception as e:
        log_to_db("ERROR", "Error generating medical referral", {
            "sender_id": sender_id,
            "error": str(e)
        })
        
        error_message = "Sorry, there was an error processing your medical referral request. Please try again."
        await send_translated_message(sender_id, error_message)

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points using Haversine formula
    Returns distance in kilometers
    """
    from math import radians, cos, sin, asin, sqrt
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371
    
    return c * r

async def find_matching_partners(symptoms, location, max_distance_km=MAX_DISTANCE_GPS):
    """
    Find partners that match the patient's symptoms and location
    Uses embedding-based similarity scoring with separate symptom and specialty embeddings
    """
    from utils.db_tools import db
    
    try:
        partners = db["partners"]
        patient_lat = location.get('lat')
        patient_lon = location.get('lon')
        
        symptoms_query = ", ".join(symptoms)
        
        extraction_result, extraction_success = await extract_symptoms_specialties(symptoms_query)
        
        if not extraction_success or not extraction_result.get('contains_info'):
            query_text = symptoms_query
        else:
            query_text = str(extraction_result)
        
        query_embedding = generate_embeddings(query_text)
        all_partners = list(partners.find({}))
        
        # Calculate similarity scores for all partners
        partners_with_scores = []
        
        for partner in all_partners:
            symptom_embeddings = partner.get('symptom_embeddings')
            service_embeddings = partner.get('service_embeddings')
            
            if not symptom_embeddings or not service_embeddings:
                continue
            
            symptom_similarity = calculate_similarity_scores(query_embedding, [symptom_embeddings])[0]
            service_similarity = calculate_similarity_scores(query_embedding, [service_embeddings])[0]
            
            overall_similarity = (
                SYMPTOM_WEIGHT * symptom_similarity +
                SPECIALTY_WEIGHT * service_similarity
            )
            
            partner['symptom_similarity'] = symptom_similarity
            partner['service_similarity'] = service_similarity
            partner['overall_similarity'] = overall_similarity
            
            partners_with_scores.append(partner)
        
        # Filter by similarity threshold
        if max_distance_km is None:
            partners_above_threshold = partners_with_scores
        else:
            partners_above_threshold = [
                p for p in partners_with_scores
                if p['overall_similarity'] > SIMILARITY_THRESHOLD
            ]
            
            if not partners_above_threshold:
                log_to_db("INFO", "No partners above similarity threshold", {
                    "sender_id": None,
                    "symptoms": symptoms,
                    "threshold": SIMILARITY_THRESHOLD,
                    "highest_similarity": max([p['overall_similarity'] for p in partners_with_scores]) if partners_with_scores else 0
                })
                return []
        
        partners_above_threshold.sort(key=lambda x: x['overall_similarity'], reverse=True)
        
        # Filter by distance
        matching_partners = []
        
        for partner in partners_above_threshold:
            closest_distance = float('inf')
            closest_location = None
            
            if patient_lat and patient_lon and partner.get('location'):
                for partner_location in partner['location']:
                    loc_lat = partner_location.get('lat')
                    loc_lon = partner_location.get('lon')
                    
                    if loc_lat and loc_lon:
                        distance = calculate_distance(patient_lat, patient_lon, loc_lat, loc_lon)
                        
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_location = partner_location
                
                partner['distance_km'] = closest_distance
                partner['closest_location'] = closest_location
                partner['similarity_score'] = partner['overall_similarity']
                
                if max_distance_km is None:
                    matching_partners.append(partner)
                elif closest_distance <= max_distance_km:
                    matching_partners.append(partner)
        
        matching_partners.sort(key=lambda x: x['overall_similarity'], reverse=True)
        top_matches = matching_partners[:2]
        
        return top_matches
        
    except Exception as e:
        log_to_db("ERROR", "Error searching for partners", {
            "sender_id": None,
            "error": str(e),
            "error_type": type(e).__name__,
            "symptoms": symptoms,
            "location": location
        })
        return []

async def format_partner_referrals(partners):
    """Format the partner information into a WhatsApp-friendly message"""
    if not partners:
        return "No medical partners found for your needs."
    
    intro_text = "🏥 *I found the following medical partners for you:*\n"
    message_parts = [intro_text]
    
    for i, partner in enumerate(partners, 1):
        name = partner.get('partner_name', 'Unknown')
        
        closest_location = partner.get('closest_location')
        if closest_location:
            direccion = closest_location.get('direccion', 'Address not available')
            lat = closest_location.get('lat')
            lon = closest_location.get('lon')
            if lat and lon:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            else:
                maps_url = closest_location.get('maps_url', '')
        else:
            locations = partner.get('location', [])
            if locations:
                direccion = locations[0].get('direccion', 'Address not available')
                lat = locations[0].get('lat')
                lon = locations[0].get('lon')
                if lat and lon:
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
                else:
                    maps_url = locations[0].get('maps_url', '')
            else:
                direccion = 'Address not available'
                maps_url = ''
        
        distance = partner.get('distance_km')
        distance_text = f" ({round(distance, 1)} km away)" if distance else ""
        
        phone_numbers = partner.get('phone_number', [])
        phone_text = ", ".join(phone_numbers) if phone_numbers else "Not available"
        
        emergency_numbers = partner.get('emergency_number', [])
        emergency_text = ", ".join([num for num in emergency_numbers if num]) if emergency_numbers else "Not available"
        
        website = partner.get('website', '').strip()
        website = website.replace('"', '').replace("'", "")
        website_text = website if website and website != "" else "Not available"
        
        partner_info = f"""
━━━━━━━━━━━━━━━
*{i}. {name}*

📍 *Address:*
{direccion}"""
        
        if maps_url and maps_url.strip():
            partner_info += f"\n🗺️ *Google Maps:* {maps_url.strip()}"
        
        partner_info += f"""

📞 *Phone:* {phone_text}
🚨 *Emergency:* {emergency_text}
🌐 *Website:* {website_text}
"""
        message_parts.append(partner_info)
    
    footer = "\n━━━━━━━━━━━━━━━\n\n💡 Please contact them directly to schedule an appointment."
    message_parts.append(footer)
    
    return "\n".join(message_parts)

async def format_fallback_referral(partner, max_distance_searched):
    """Format a fallback referral message when no partners are within radius"""
    if not partner:
        return "No medical partners found for your needs."
    
    intro_text = f"⚠️ *I couldn't find any medical partners within {max_distance_searched} km of your location.*\n\n"
    intro_text += "However, this partner might be helpful for your symptoms:\n"
    
    message_parts = [intro_text]
    
    name = partner.get('partner_name', 'Unknown')
    
    closest_location = partner.get('closest_location')
    if closest_location:
        direccion = closest_location.get('direccion', 'Address not available')
        lat = closest_location.get('lat')
        lon = closest_location.get('lon')
        if lat and lon:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            maps_url = closest_location.get('maps_url', '')
    else:
        locations = partner.get('location', [])
        if locations:
            direccion = locations[0].get('direccion', 'Address not available')
            lat = locations[0].get('lat')
            lon = locations[0].get('lon')
            if lat and lon:
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            else:
                maps_url = locations[0].get('maps_url', '')
        else:
            direccion = 'Address not available'
            maps_url = ''
    
    distance = partner.get('distance_km')
    distance_text = f" ({round(distance, 1)} km away)" if distance else ""
    
    phone_numbers = partner.get('phone_number', [])
    phone_text = ", ".join(phone_numbers) if phone_numbers else "Not available"
    
    emergency_numbers = partner.get('emergency_number', [])
    emergency_text = ", ".join([num for num in emergency_numbers if num]) if emergency_numbers else "Not available"
    
    website = partner.get('website', '').strip()
    website = website.replace('"', '').replace("'", "")
    website_text = website if website and website != "" else "Not available"
    
    partner_info = f"""
━━━━━━━━━━━━━━━
*{name}*{distance_text}

📍 *Address:*
{direccion}"""
    
    if maps_url and maps_url.strip():
        partner_info += f"\n🗺️ *Google Maps:* {maps_url.strip()}"
    
    partner_info += f"""

📞 *Phone:* {phone_text}
🚨 *Emergency:* {emergency_text}
🌐 *Website:* {website_text}
"""
    message_parts.append(partner_info)
    
    footer = "\n━━━━━━━━━━━━━━━\n\n"
    footer += "⚠️ *Note:* This partner is outside your search radius but may be able to help with your symptoms.\n\n"
    footer += "💡 Please contact them to verify they can assist you, or consider contacting your local hospital."
    message_parts.append(footer)
    
    return "\n".join(message_parts)

async def update_conversation_recommendation(sender_id, recommendation):
    """Update conversation with medical recommendation"""
    from utils.db_tools import ongoing_conversations
    
    if isinstance(recommendation, list):
        if recommendation:
            recommendation_text = f"Found {len(recommendation)} partners: " + ", ".join([p.get('partner_name', 'Unknown') for p in recommendation])
        else:
            recommendation_text = "No partners found"
    else:
        recommendation_text = str(recommendation)
    
    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"recommendation": recommendation_text}}
    )

async def save_referrals(sender_id, partners, symptoms, location, is_fallback=False):
    """Save referrals to the referrals collection and notify partners"""
    try:
        from utils.db_tools import db, get_conversation
        from utils.whatsapp import send_template_message
        
        referrals = db["referrals"]
        
        conversation = get_conversation(sender_id)
        patient_language = conversation.get('language', 'Unknown') if conversation else 'Unknown'
        
        symptoms_text = ", ".join(symptoms) if symptoms else "Not specified"
        
        referral_records = []
        
        for partner in partners:
            distance_km = partner.get('distance_km')
            closest_location = partner.get('closest_location')
            overall_similarity = partner.get('overall_similarity')
            symptom_similarity = partner.get('symptom_similarity')
            service_similarity = partner.get('service_similarity')
            
            referral_record = {
                "patient_phone_number": sender_id,
                "partner_id": partner.get('_id'),
                "partner_name": partner.get('partner_name'),
                "symptoms_matched": symptoms,
                "distance_km": distance_km,
                "location_matched": closest_location.get('direccion') if closest_location else None,
                "overall_similarity": overall_similarity,
                "symptom_similarity": symptom_similarity,
                "service_similarity": service_similarity,
                "similarity_score": overall_similarity,
                "is_fallback": is_fallback,
                "referred_at": datetime.utcnow(),
                "status": "sent"
            }
            
            referral_records.append(referral_record)
        
        if referral_records:
            result = referrals.insert_many(referral_records)
            
            for partner in partners:
                partner_whatsapp = "50258792752"  # partner.get('whatsapp_number')
                
                if partner_whatsapp:
                    template_params = [
                        sender_id,
                        symptoms_text,
                        patient_language
                    ]
                    
                    await send_template_message(
                        recipient_number=partner_whatsapp,
                        template_name="bot_referral_notification",
                        parameters=template_params,
                        language_code="es"
                    )
                else:
                    log_to_db("ERROR", "Partner has no WhatsApp number, notification not sent", {
                        "sender_id": sender_id,
                        "partner_name": partner.get('partner_name'),
                        "partner_id": str(partner.get('_id'))
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