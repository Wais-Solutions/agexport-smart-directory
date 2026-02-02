from utils.db_tools import log_to_db
from utils.translation import send_translated_message
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import json

# Maximum distance in kilometers to consider a partner
MAX_DISTANCE_KM = 15

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
        log_to_db("INFO", "Loading sentence transformer model")
        _model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
        log_to_db("INFO", "Sentence transformer model loaded successfully")
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
        
        log_to_db("INFO", "Symptoms and specialties extracted", {
            "symptoms": result.get("symptoms", []),
            "specialties": result.get("specialties", []),
            "contains_info": result.get("contains_info", False)
        })
        
        return result, True
        
    except Exception as e:
        log_to_db("ERROR", "Error extracting symptoms and specialties", {
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
    Args:
        query_embedding: 1D numpy array of query embeddings
        partner_embeddings_list: List of partner embeddings (each is a 1D numpy array)
    Returns:
        List of similarity scores
    """
    try:
        # Convert to numpy arrays and ensure proper shape
        query_embedding = np.array(query_embedding, dtype=np.float32).reshape(1, -1)
        partner_embeddings_matrix = np.array(partner_embeddings_list, dtype=np.float32)
        
        # Calculate cosine similarity for all partners at once
        similarity_scores = cosine_similarity(query_embedding, partner_embeddings_matrix)[0]
        
        return similarity_scores.tolist()
        
    except Exception as e:
        log_to_db("ERROR", "Error calculating similarity scores", {
            "error": str(e)
        })
        return [0.0] * len(partner_embeddings_list)

async def provide_medical_referral(sender_id, conversation):
    """Generate and send medical referral based on symptoms and location"""
    symptoms = conversation.get('symptoms', [])
    location = conversation.get('location', {})
    
    # Create prompt for medical referral
    symptoms_text = ", ".join(symptoms)
    location_text = location.get('text_description', 'ubicación no especificada')
    
    log_to_db("INFO", "Starting medical referral search", {
        "sender_id": sender_id,
        "symptoms": symptoms,
        "location": location_text
    })
    
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
                "partner_names": [p.get("partner_name") for p in matching_partners]
            })
        else:
            # No matching partners found - send apology
            apology_message = f"I apologize, but I couldn't find medical partners within {MAX_DISTANCE_KM} km of your location that specialize in your symptoms. Please consider contacting your local hospital or health center for assistance."
            await send_translated_message(sender_id, apology_message)
            
            log_to_db("INFO", "No matching partners found", {
                "sender_id": sender_id,
                "symptoms": symptoms,
                "location": location_text,
                "max_distance_km": MAX_DISTANCE_KM
            })
        
        # Update conversation with recommendation
        await update_conversation_recommendation(sender_id, matching_partners if matching_partners else "No partners found")
        
    except Exception as e:
        log_to_db("ERROR", "Error generating medical referral", {
            "sender_id": sender_id,
            "error": str(e),
            "traceback": str(e.__traceback__)
        })
        
        error_message = "Sorry, there was an error processing your medical referral request. Please try again."
        await send_translated_message(sender_id, error_message)

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    Returns distance in kilometers
    Uses Haversine formula
    """
    from math import radians, cos, sin, asin, sqrt
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    
    return c * r

async def find_matching_partners(symptoms, location):
    """
    Find partners that match the patient's symptoms and location
    Uses embedding-based similarity scoring with separate symptom and specialty embeddings
    Follows the approach from partner_analysis.ipynb
    """
    from utils.db_tools import db
    
    try:
        partners = db["partners"]
        patient_lat = location.get('lat')
        patient_lon = location.get('lon')
        
        # Create query from symptoms
        symptoms_query = ", ".join(symptoms)
        
        # Extract symptoms and specialties from the query
        extraction_result, extraction_success = await extract_symptoms_specialties(symptoms_query)
        
        if not extraction_success or not extraction_result.get('contains_info'):
            log_to_db("WARNING", "Could not extract meaningful symptoms/specialties", {
                "symptoms_query": symptoms_query,
                "extraction_result": extraction_result
            })
            # Fallback: use original symptoms query
            query_text = symptoms_query
        else:
            # Use the extracted result as query
            query_text = str(extraction_result)
        
        log_to_db("INFO", "Generating embeddings for query", {
            "query_text": query_text[:100]  # Log first 100 chars
        })
        
        # Generate embeddings for the query
        query_embedding = generate_embeddings(query_text)
        
        # Get all partners from the database
        all_partners = list(partners.find({}))
        
        log_to_db("INFO", "Starting partner matching with dual embeddings", {
            "total_partners": len(all_partners),
            "symptom_weight": SYMPTOM_WEIGHT,
            "specialty_weight": SPECIALTY_WEIGHT,
            "similarity_threshold": SIMILARITY_THRESHOLD
        })
        
        # Step 1: Calculate similarity scores using both symptom and service embeddings
        partners_with_scores = []
        
        for partner in all_partners:
            symptom_embeddings = partner.get('symptom_embeddings')
            service_embeddings = partner.get('service_embeddings')
            
            # Skip partners that don't have embeddings
            if not symptom_embeddings or not service_embeddings:
                log_to_db("DEBUG", "Partner missing embeddings, skipping", {
                    "partner_name": partner.get('partner_name'),
                    "has_symptom_embeddings": symptom_embeddings is not None,
                    "has_service_embeddings": service_embeddings is not None
                })
                continue
            
            # Calculate similarity with symptom embeddings
            symptom_similarity = calculate_similarity_scores(
                query_embedding,
                [symptom_embeddings]
            )[0]
            
            # Calculate similarity with service embeddings  
            service_similarity = calculate_similarity_scores(
                query_embedding,
                [service_embeddings]
            )[0]
            
            # Calculate weighted overall similarity
            overall_similarity = (
                SYMPTOM_WEIGHT * symptom_similarity +
                SPECIALTY_WEIGHT * service_similarity
            )
            
            # Store all scores
            partner['symptom_similarity'] = symptom_similarity
            partner['service_similarity'] = service_similarity
            partner['overall_similarity'] = overall_similarity
            
            partners_with_scores.append(partner)
            
            log_to_db("DEBUG", "Similarities calculated", {
                "partner_name": partner.get('partner_name'),
                "symptom_sim": round(symptom_similarity, 4),
                "service_sim": round(service_similarity, 4),
                "overall_sim": round(overall_similarity, 4)
            })
        
        # Step 2: Filter by similarity threshold
        partners_above_threshold = [
            p for p in partners_with_scores
            if p['overall_similarity'] > SIMILARITY_THRESHOLD
        ]
        
        log_to_db("INFO", "Partners filtered by similarity threshold", {
            "total_partners": len(partners_with_scores),
            "above_threshold": len(partners_above_threshold),
            "threshold": SIMILARITY_THRESHOLD
        })
        
        if not partners_above_threshold:
            log_to_db("WARNING", "No partners above similarity threshold", {
                "threshold": SIMILARITY_THRESHOLD,
                "highest_similarity": max([p['overall_similarity'] for p in partners_with_scores]) if partners_with_scores else 0
            })
            return []
        
        # Step 3: Sort by overall similarity (highest first)
        partners_above_threshold.sort(key=lambda x: x['overall_similarity'], reverse=True)
        
        log_to_db("INFO", "Partners sorted by overall similarity", {
            "top_3_similarities": [
                {
                    "name": p.get('partner_name'),
                    "overall_sim": round(p['overall_similarity'], 4),
                    "symptom_sim": round(p['symptom_similarity'], 4),
                    "service_sim": round(p['service_similarity'], 4)
                }
                for p in partners_above_threshold[:3]
            ]
        })
        
        # Step 4: Filter by distance (max 15km)
        matching_partners = []
        
        for partner in partners_above_threshold:
            closest_distance = float('inf')
            closest_location = None
            
            # Calculate distance to each location of the partner
            if patient_lat and patient_lon and partner.get('location'):
                for partner_location in partner['location']:
                    loc_lat = partner_location.get('lat')
                    loc_lon = partner_location.get('lon')
                    
                    if loc_lat and loc_lon:
                        distance = calculate_distance(patient_lat, patient_lon, loc_lat, loc_lon)
                        
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_location = partner_location
                
                # Only include partners within MAX_DISTANCE_KM
                if closest_distance > MAX_DISTANCE_KM:
                    log_to_db("DEBUG", "Partner excluded - too far", {
                        "partner_name": partner.get('partner_name'),
                        "overall_similarity": round(partner['overall_similarity'], 4),
                        "distance_km": round(closest_distance, 2),
                        "max_allowed": MAX_DISTANCE_KM
                    })
                    continue  # Skip this partner
                
                # Partner is within range - add to matching list
                partner['distance_km'] = closest_distance
                partner['closest_location'] = closest_location
                # Keep overall_similarity as the main similarity_score for compatibility
                partner['similarity_score'] = partner['overall_similarity']
                matching_partners.append(partner)
                
                log_to_db("DEBUG", "Partner within range", {
                    "partner_name": partner.get('partner_name'),
                    "overall_similarity": round(partner['overall_similarity'], 4),
                    "symptom_similarity": round(partner['symptom_similarity'], 4),
                    "service_similarity": round(partner['service_similarity'], 4),
                    "distance_km": round(closest_distance, 2)
                })
            else:
                log_to_db("DEBUG", "Partner has no location data", {
                    "partner_name": partner.get('partner_name')
                })
        
        # Step 5: Sort by overall similarity (already sorted, but re-sort after distance filtering)
        matching_partners.sort(key=lambda x: x['overall_similarity'], reverse=True)
        
        # Return only top 2 matches
        top_matches = matching_partners[:2]
        
        log_to_db("INFO", "Partner search completed", {
            "patient_location": {"lat": patient_lat, "lon": patient_lon},
            "symptoms": symptoms,
            "total_partners_checked": len(all_partners),
            "partners_with_embeddings": len(partners_with_scores),
            "partners_above_threshold": len(partners_above_threshold),
            "partners_within_range": len(matching_partners),
            "top_matches_returned": len(top_matches),
            "max_distance_km": MAX_DISTANCE_KM,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "top_matches": [
                {
                    "name": p.get("partner_name"),
                    "overall_similarity": round(p['overall_similarity'], 4),
                    "symptom_similarity": round(p['symptom_similarity'], 4),
                    "service_similarity": round(p['service_similarity'], 4),
                    "distance_km": round(p['distance_km'], 2)
                }
                for p in top_matches
            ]
        })
        
        return top_matches
        
    except Exception as e:
        log_to_db("ERROR", "Error searching for partners", {
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
        # Partner name
        name = partner.get('partner_name', 'Unknown')
        
        # Get closest location details
        closest_location = partner.get('closest_location')
        if closest_location:
            direccion = closest_location.get('direccion', 'Address not available')
            maps_url = closest_location.get('maps_url', '')
        else:
            # Fallback to first location if closest not available
            locations = partner.get('location', [])
            if locations:
                direccion = locations[0].get('direccion', 'Address not available')
                maps_url = locations[0].get('maps_url', '')
            else:
                direccion = 'Address not available'
                maps_url = ''
        
        # Distance
        distance = partner.get('distance_km')
        distance_text = f" ({round(distance, 1)} km away)" if distance else ""
        
        # Phone numbers
        phone_numbers = partner.get('phone_number', [])
        phone_text = ", ".join(phone_numbers) if phone_numbers else "Not available"
        
        # Emergency numbers
        emergency_numbers = partner.get('emergency_number', [])
        emergency_text = ", ".join([num for num in emergency_numbers if num]) if emergency_numbers else "Not available"
        
        # Website
        website = partner.get('website', '').strip()
        # Clean up website (remove quotes if present)
        website = website.replace('"', '').replace("'", "")
        website_text = website if website and website != "" else "Not available"
        
        # Build partner info section
        partner_info = f"""
━━━━━━━━━━━━━━━
*{i}. {name}*{distance_text}

📍 *Address:*
{direccion}"""
        
        # Add Google Maps link if available
        if maps_url and maps_url.strip():
            partner_info += f"\n🗺️ *Google Maps:* {maps_url.strip()}"
        
        partner_info += f"""

📞 *Phone:* {phone_text}
🚨 *Emergency:* {emergency_text}
🌐 *Website:* {website_text}
"""
        message_parts.append(partner_info)
    
    # Footer message
    footer = "\n━━━━━━━━━━━━━━━\n\n💡 Please contact them directly to schedule an appointment."
    message_parts.append(footer)
    
    return "\n".join(message_parts)

async def update_conversation_recommendation(sender_id, recommendation):
    """Update conversation with medical recommendation"""
    from utils.db_tools import ongoing_conversations
    
    # Convert recommendation to string if it's a list of partners
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

async def save_referrals(sender_id, partners, symptoms, location):
    """Save referrals to the referrals collection and notify partners"""
    try:
        from utils.db_tools import db, get_conversation
        from utils.whatsapp import send_template_message
        
        referrals = db["referrals"]
        
        # Get patient's language from conversation
        conversation = get_conversation(sender_id)
        patient_language = conversation.get('language', 'Unknown') if conversation else 'Unknown'
        
        # Format symptoms as comma-separated string
        symptoms_text = ", ".join(symptoms) if symptoms else "Not specified"
        
        # Create a referral record for each partner
        referral_records = []
        
        for partner in partners:
            # Get distance and closest location info
            distance_km = partner.get('distance_km')
            closest_location = partner.get('closest_location')
            
            # Get all similarity scores
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
                "similarity_score": overall_similarity,  # For backwards compatibility
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
                "distances": [r.get("distance_km") for r in referral_records],
                "overall_similarities": [r.get("overall_similarity") for r in referral_records],
                "inserted_ids": [str(id) for id in result.inserted_ids]
            })
            
            # Send notification to each partner
            for partner in partners:
                partner_whatsapp = "50258792752"  # partner.get('whatsapp_number')
                
                if partner_whatsapp:
                    # Prepare template parameters
                    # {{1}}: Patient contact
                    # {{2}}: Symptoms
                    # {{3}}: Language
                    template_params = [
                        sender_id,           # Patient phone number
                        symptoms_text,       # Symptoms as comma-separated string
                        patient_language     # Patient's language
                    ]
                    
                    # Send template notification to partner
                    await send_template_message(
                        recipient_number=partner_whatsapp,
                        template_name="bot_referral_notification",
                        parameters=template_params,
                        language_code="es"  # Template is in Spanish
                    )
                    
                    log_to_db("INFO", "Partner notification sent", {
                        "partner_name": partner.get('partner_name'),
                        "partner_whatsapp": partner_whatsapp,
                        "patient_phone": sender_id,
                        "symptoms": symptoms_text,
                        "language": patient_language
                    })
                else:
                    log_to_db("WARNING", "Partner has no WhatsApp number, notification not sent", {
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