from utils.db_tools import log_to_db
from utils.translation import send_translated_message
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer

# Maximum distance in kilometers to consider a partner
MAX_DISTANCE_KM = 15

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

def calculate_similarity(query_embedding, partner_embeddings):
    """
    Calculate cosine similarity between query embedding and partner embeddings
    Returns similarity score (0-1, where 1 is perfect match)
    """
    try:
        # Ensure embeddings are numpy arrays
        query_embedding = np.array(query_embedding, dtype=np.float32).reshape(-1)
        partner_embeddings = np.array(partner_embeddings, dtype=np.float32).reshape(-1)
        
        # Calculate cosine similarity
        similarity = np.dot(query_embedding, partner_embeddings) / (
            np.linalg.norm(query_embedding) * np.linalg.norm(partner_embeddings)
        )
        
        return float(similarity)
        
    except Exception as e:
        log_to_db("ERROR", "Error calculating similarity", {
            "error": str(e)
        })
        return 0.0

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
    Uses embedding-based similarity scoring instead of LLM
    """
    from utils.db_tools import db
    
    try:
        partners = db["partners"]
        patient_lat = location.get('lat')
        patient_lon = location.get('lon')
        
        # Create query from symptoms
        symptoms_query = ", ".join(symptoms)
        
        log_to_db("INFO", "Generating embeddings for symptoms query", {
            "symptoms_query": symptoms_query
        })
        
        # Generate embeddings for the symptoms query
        query_embedding = generate_embeddings(symptoms_query)
        
        # Get all partners from the database
        all_partners = list(partners.find({}))
        
        log_to_db("INFO", "Starting partner matching", {
            "total_partners": len(all_partners),
            "symptoms_query": symptoms_query
        })
        
        # Step 1: Filter by specialty similarity (embedding-based)
        partners_with_similarity = []
        
        for partner in all_partners:
            # Check if partner has embeddings
            embeddings = partner.get('embeddings')
            
            if not embeddings:
                # Generate embeddings if not present
                log_to_db("WARNING", "Partner missing embeddings, generating on the fly", {
                    "partner_name": partner.get('partner_name')
                })
                
                # Create descriptor from partner data
                category = partner.get('category', '')
                partner_name = partner.get('partner_name', '')
                services = partner.get('available_services', [])
                services_text = " - ".join(services) if services else ""
                
                str_descriptor = f"{category} - {partner_name} - {services_text}"
                embeddings = generate_embeddings(str_descriptor)
                
                # Optionally save embeddings back to database
                partners.update_one(
                    {"_id": partner.get('_id')},
                    {"$set": {"embeddings": embeddings.tolist()}}
                )
            
            # Calculate similarity score
            similarity_score = calculate_similarity(query_embedding, embeddings)
            
            partner['similarity_score'] = similarity_score
            partners_with_similarity.append(partner)
            
            log_to_db("DEBUG", "Similarity calculated for partner", {
                "partner_name": partner.get('partner_name'),
                "similarity_score": round(similarity_score, 4)
            })
        
        # Sort by similarity (highest first)
        partners_with_similarity.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        log_to_db("INFO", "Partners sorted by similarity", {
            "top_3_similarities": [
                {
                    "name": p.get('partner_name'),
                    "similarity": round(p.get('similarity_score'), 4)
                }
                for p in partners_with_similarity[:3]
            ]
        })
        
        # Step 2: Filter by distance (max 15km)
        matching_partners = []
        
        for partner in partners_with_similarity:
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
                
                # CRITICAL: Only include partners within MAX_DISTANCE_KM
                if closest_distance > MAX_DISTANCE_KM:
                    log_to_db("DEBUG", "Partner excluded - too far", {
                        "partner_name": partner.get('partner_name'),
                        "similarity_score": round(partner.get('similarity_score'), 4),
                        "distance_km": round(closest_distance, 2),
                        "max_allowed": MAX_DISTANCE_KM
                    })
                    continue  # Skip this partner
                
                # Partner is within range - add to matching list
                partner['distance_km'] = closest_distance
                partner['closest_location'] = closest_location
                matching_partners.append(partner)
                
                log_to_db("DEBUG", "Partner within range", {
                    "partner_name": partner.get('partner_name'),
                    "similarity_score": round(partner.get('similarity_score'), 4),
                    "distance_km": round(closest_distance, 2)
                })
            else:
                log_to_db("DEBUG", "Partner has no location data", {
                    "partner_name": partner.get('partner_name')
                })
        
        # Step 3: Sort by similarity (distance filtering already done)
        # Partners are already sorted by similarity from Step 1
        matching_partners.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        # Return only top 2 matches
        top_matches = matching_partners[:2]
        
        log_to_db("INFO", "Partner search completed", {
            "patient_location": {"lat": patient_lat, "lon": patient_lon},
            "symptoms": symptoms,
            "total_partners_checked": len(all_partners),
            "partners_within_range": len(matching_partners),
            "top_matches_returned": len(top_matches),
            "max_distance_km": MAX_DISTANCE_KM,
            "top_matches": [
                {
                    "name": p.get("partner_name"),
                    "similarity_score": round(p.get("similarity_score"), 4),
                    "distance_km": round(p.get("distance_km"), 2) if p.get("distance_km") else None
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
            similarity_score = partner.get('similarity_score')
            
            referral_record = {
                "patient_phone_number": sender_id,
                "partner_id": partner.get('_id'),
                "partner_name": partner.get('partner_name'),
                "symptoms_matched": symptoms,
                "distance_km": distance_km,
                "location_matched": closest_location.get('direccion') if closest_location else None,
                "similarity_score": similarity_score,  # New field - embedding similarity
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
                "similarity_scores": [r.get("similarity_score") for r in referral_records],
                "inserted_ids": [str(id) for id in result.inserted_ids]
            })
            
            # Send notification to each partner
            for partner in partners:
                partner_whatsapp = "50258792752" #partner.get('whatsapp_number')
                
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
                        template_name="partner_referral_notification",
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