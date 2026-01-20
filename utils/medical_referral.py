from utils.db_tools import log_to_db
from utils.llm import get_completition
from utils.translation import send_translated_message
from datetime import datetime

# Maximum distance in kilometers to consider a partner
MAX_DISTANCE_KM = 15

async def provide_medical_referral(sender_id, conversation):
    # Generate and send medical referral based on symptoms and location
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
            "error": str(e)
        })
        
        error_message = "Sorry, there was an error processing your medical referral request. Please try again."
        await send_translated_message(sender_id, error_message)

# Calculate distance between two geographic points using Haversine formula
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

# Find partners that match the patients symptoms and location
async def find_matching_partners(symptoms, location):
    from utils.db_tools import db
    
    try:
        partners = db["partners"]
        patient_lat = location.get('lat')
        patient_lon = location.get('lon')
        
        # Get all partners from the new collection structure
        all_partners = list(partners.find({}))
        
        matching_partners = []
        
        for partner in all_partners:
            match_score = 0
            reasons = []
            closest_distance = float('inf')
            closest_location = None
            
            # Check specialty match using LLM
            if symptoms and partner.get('available_services'):
                specialty_match = await check_specialty_match(symptoms, partner['available_services'])
                if specialty_match:
                    match_score += specialty_match  # LLM returns confidence score (0-10)
                    reasons.append("specialty_match")
            
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
                        "distance_km": round(closest_distance, 2),
                        "max_allowed": MAX_DISTANCE_KM
                    })
                    continue  # Skip this partner
                
                # Add distance score (closer = higher score)
                # Within 5km: +10 points, 5-10km: +8 points, 10-15km: +5 points
                if closest_distance < 5:
                    match_score += 10
                    reasons.append("very_close")
                elif closest_distance < 10:
                    match_score += 8
                    reasons.append("close")
                elif closest_distance <= MAX_DISTANCE_KM:
                    match_score += 5
                    reasons.append("nearby")
            
            # If we have a reasonable match, include the partner
            if match_score >= 3:  # Minimum threshold (at least some specialty match or nearby location)
                partner['match_score'] = match_score
                partner['match_reasons'] = reasons
                partner['distance_km'] = closest_distance if closest_distance != float('inf') else None
                partner['closest_location'] = closest_location
                matching_partners.append(partner)
        
        # Sort by match score (highest first), then by distance (closest first)
        matching_partners.sort(key=lambda x: (x['match_score'], -x.get('distance_km', float('inf')) if x.get('distance_km') else 0), reverse=True)
        
        log_to_db("INFO", "Partner search completed", {
            "patient_location": {"lat": patient_lat, "lon": patient_lon},
            "symptoms": symptoms,
            "total_partners_checked": len(all_partners),
            "matches_found": len(matching_partners),
            "max_distance_km": MAX_DISTANCE_KM,
            "top_matches": [
                {
                    "name": p.get("partner_name"),
                    "score": p.get("match_score"),
                    "distance_km": round(p.get("distance_km"), 2) if p.get("distance_km") else None
                } 
                for p in matching_partners[:3]
            ]
        })
        
        return matching_partners[:3]  # Return top 3 matches
        
    except Exception as e:
        log_to_db("ERROR", "Error searching for partners", {
            "error": str(e),
            "symptoms": symptoms,
            "location": location
        })
        return []

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

# Format the partner information into a WhatsApp-friendly message
async def format_partner_referrals(partners):
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
        else:
            # Fallback to first location if closest not available
            locations = partner.get('location', [])
            direccion = locations[0].get('direccion', 'Address not available.') if locations else 'Address not available'
        
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
━━━━━━━━━━━━━━━━━
*{i}. {name}*{distance_text}

📍 *Address:*
{direccion}

📞 *Phone:* {phone_text}
🚨 *Emergency:* {emergency_text}
🌐 *Website:* {website_text}
"""
        message_parts.append(partner_info)
    
    # Footer message
    footer = "\n━━━━━━━━━━━━━━━━━\n\n💡 Please contact them directly to schedule an appointment."
    message_parts.append(footer)
    
    return "\n".join(message_parts)

async def update_conversation_recommendation(sender_id, recommendation):
    # Update conversation with medical recommendation
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

# Save referrals to the referrals collection
async def save_referrals(sender_id, partners, symptoms, location):
    try:
        from utils.db_tools import db
        
        referrals = db["referrals"]
        
        # Create a referral record for each partner
        referral_records = []
        
        for partner in partners:
            # Get distance and closest location info
            distance_km = partner.get('distance_km')
            closest_location = partner.get('closest_location')
            
            referral_record = {
                "patient_phone_number": sender_id,
                "partner_id": partner.get('_id'),
                "partner_name": partner.get('partner_name'),
                "symptoms_matched": symptoms,
                "distance_km": distance_km,
                "location_matched": closest_location.get('direccion') if closest_location else None,
                "match_score": partner.get('match_score'),
                "match_reasons": partner.get('match_reasons', []),
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