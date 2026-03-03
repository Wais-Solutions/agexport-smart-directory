import json
import math
import re
from datetime import datetime

import numpy as np
from sentence_transformers import SentenceTransformer

from utils.db_tools import log_to_db
from utils.translation import send_translated_message

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
GROQ_MODEL = "openai/gpt-oss-120b"

# Distance limits used for the hard-radius filter (fallback path)
MAX_DISTANCE_GPS = 30    # km — GPS locations
MAX_DISTANCE_TEXT = 60   # km — text-based locations

# Gaussian scoring parameters
DISTANCE_SIGMA_KM = 50.0   # controls how fast distance score decays (matches notebook)
SIMILARITY_SIGMA = 0.3     # controls how fast similarity score decays

# Emergency boost multiplier applied to matching emergency services
EMERGENCY_SERVICE_BOOST_FACTOR = 3.0

# Keywords that identify "emergency" services/symptoms
EMERGENCY_KEYWORDS = (
    "emergencias dentales en niños",
    "emergencias dentales a niños",
    "emergencias dentales",
    "emergencias",
)

# How many top partners to return
TOP_K = 2

# ---------------------------------------------------------------------------
# Model (lazy-loaded)
# ---------------------------------------------------------------------------

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load the sentence-transformer model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Service-embedding cache (loaded once from MongoDB at first use)
# ---------------------------------------------------------------------------

_service_embedding_map: dict[str, np.ndarray] | None = None


def get_service_embedding_map() -> dict[str, np.ndarray]:
    """
    Build a dict {og_service_name -> embedding} from the `services` collection.
    Cached after the first call.
    """
    global _service_embedding_map
    if _service_embedding_map is not None:
        return _service_embedding_map

    from utils.db_tools import db

    _service_embedding_map = {}
    for item in db["services"].find({}, {"og_service_name": 1, "embedding": 1}):
        name = str(item.get("og_service_name", "")).strip().lower()
        emb = item.get("embedding")
        if name and isinstance(emb, list) and emb:
            _service_embedding_map[name] = np.asarray(emb, dtype=np.float32)

    log_to_db("INFO", "Service embedding map loaded", {
        "sender_id": None,
        "total_services": len(_service_embedding_map),
    })
    return _service_embedding_map


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom != 0 else 0.0


def _gaussian_similarity(similarity: float, sigma: float = SIMILARITY_SIGMA) -> float:
    """Map raw cosine similarity to [0, 1] with a Gaussian centred at 1."""
    return float(math.exp(-0.5 * ((similarity - 1.0) / sigma) ** 2))


def _gaussian_distance_km(distance_km: float, sigma_km: float = DISTANCE_SIGMA_KM) -> float:
    """Map distance (km) to a score in (0, 1] — score decays as distance grows."""
    return float(math.exp(-0.5 * (distance_km / sigma_km) ** 2))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two (lat, lon) points in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _has_emergency_signal(items: list[str]) -> bool:
    return any(k in items for k in EMERGENCY_KEYWORDS)


def _safe_json_parse(content: str):
    content = (content or "").strip()
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

async def extract_symptoms_services(text: str) -> dict:
    """
    Use Groq LLM to extract symptoms, possible services, and emergency flag.
    Returns: {"symptoms": [...], "possible_services": [...], "is_emergency": bool}
    """
    from groq import AsyncGroq

    if not text or not str(text).strip():
        return {"symptoms": [], "possible_services": [], "is_emergency": False}

    client = AsyncGroq()

    try:
        completion = await client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0,
            top_p=1,
            stream=False,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract medical intent from user text: "
                        "{\"symptoms\": string[], \"possible_services\": string[]}. "
                        "Rules: "
                        "- symptoms: medical symptoms/conditions/injuries mentioned or implied. "
                        "- possible_services: likely healthcare services related to the case. all fractures are just emergencies. "
                        "- is_emergency: true if urgency/emergency is indicated. all fractures are just emergencies. if bleeding is involved is an emergency. "
                        "- Keep outputs concise and in Spanish if user text is Spanish."
                    ),
                },
                {"role": "user", "content": str(text)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "specialty_mapping",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "symptoms": {"type": "array", "items": {"type": "string"}},
                            "possible_services": {"type": "array", "items": {"type": "string"}},
                            "is_emergency": {"type": "boolean"},
                        },
                        "required": ["symptoms", "possible_services", "is_emergency"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        raw = completion.choices[0].message.content if completion.choices else ""
        data = _safe_json_parse(raw) or {}

        symptoms = [str(x).strip() for x in (data.get("symptoms") or []) if str(x).strip()]
        services = [str(x).strip() for x in (data.get("possible_services") or []) if str(x).strip()]
        is_emergency = bool(data.get("is_emergency", False))

        return {"symptoms": symptoms, "possible_services": services, "is_emergency": is_emergency}

    except Exception as e:
        log_to_db("ERROR", "Error extracting symptoms/services via Groq", {
            "sender_id": None,
            "error": str(e),
            "text": text,
        })
        return {"symptoms": [], "possible_services": [], "is_emergency": False}


# ---------------------------------------------------------------------------
# Core ranking logic
# ---------------------------------------------------------------------------

async def find_matching_partners(
    symptoms: list[str],
    location: dict,
    max_distance_km: float | None = MAX_DISTANCE_GPS,
) -> list[dict]:
    """
    Rank all partners by a combined service-similarity × distance score,
    exactly as implemented in partner_emb_ranking.ipynb.

    Flow:
      1. Extract symptoms/services/emergency flag via Groq LLM.
      2. Build a single query embedding (mean of original text + extracted signals).
      3. For each partner, score every service against the query embedding with a
         Gaussian similarity. Apply 3× boost for emergency services when relevant.
         Take the top-1 service score as the partner's service_score.
      4. For each partner geo-location compute distance_score (Gaussian, σ=50 km).
         combined_score = service_score × distance_score. Keep the best location.
      5. Sort all partners by final_score descending.
      6. If max_distance_km is given (normal path): return top-K partners whose
         closest location is within the radius.
         If none qualify, return [] so the caller can trigger the fallback.
      7. If max_distance_km is None (fallback path): return global top-K with no
         distance filter, so the caller always gets the best available match.
    """
    from utils.db_tools import db

    try:
        service_embedding_map = get_service_embedding_map()
        model = get_embedding_model()

        patient_lat = location.get("lat")
        patient_lon = location.get("lon")

        symptoms_query = ", ".join(symptoms)
        extracted = await extract_symptoms_services(symptoms_query)

        # Build query embedding: mean of [original text, symptoms, possible_services]
        query_chunks = (
            [symptoms_query]
            + extracted["symptoms"]
            + extracted["possible_services"]
        )
        query_chunks = [q for q in query_chunks if q and str(q).strip()]
        query_vectors = model.encode(query_chunks, convert_to_numpy=True).astype(np.float32)
        query_emb: np.ndarray = (
            query_vectors if query_vectors.ndim == 1
            else np.mean(query_vectors, axis=0).astype(np.float32)
        )

        all_partners = list(db["partners"].find({}))
        ranked: list[dict] = []

        for partner in all_partners:
            partner_services = [
                str(s).strip().lower()
                for s in partner.get("partner_services", [])
            ]

            # --- Service similarity score (top-1 as in notebook) --------
            service_scores: list[float] = []
            for svc_name in partner_services:
                emb = service_embedding_map.get(svc_name)
                if emb is None:
                    continue

                raw_sim = _cosine_similarity(query_emb, emb)
                sim_score = _gaussian_similarity(raw_sim, sigma=SIMILARITY_SIGMA)

                if _has_emergency_signal([svc_name]) and extracted["is_emergency"]:
                    sim_score = sim_score * EMERGENCY_SERVICE_BOOST_FACTOR

                service_scores.append(sim_score)

            # top-1 average (identical to max, matches notebook exactly)
            if service_scores:
                top_scores = sorted(service_scores, reverse=True)[:1]
                service_score = float(sum(top_scores) / len(top_scores))
            else:
                service_score = 0.0

            # --- Best location (highest combined score) ------------------
            best_location: dict | None = None
            best_combined: float = -1.0

            for idx, geo in enumerate(partner.get("partner_geo_locations", [])):
                if not isinstance(geo, dict):
                    continue
                glat, glon = geo.get("lat"), geo.get("lon")
                if glat is None or glon is None:
                    continue

                try:
                    distance_km = _haversine_km(
                        float(patient_lat), float(patient_lon),
                        float(glat), float(glon),
                    ) if patient_lat and patient_lon else None
                except (TypeError, ValueError):
                    distance_km = None

                distance_score = (
                    _gaussian_distance_km(distance_km, sigma_km=DISTANCE_SIGMA_KM)
                    if distance_km is not None else 0.0
                )
                combined = service_score * distance_score

                location_result = {
                    "location_index": idx,
                    "query": geo.get("query"),
                    "name": geo.get("name"),
                    "direccion": geo.get("address"),
                    "lat": float(glat),
                    "lon": float(glon),
                    "maps_url": geo.get("maps_url"),
                    "place_id": geo.get("place_id"),
                    "distance_km": distance_km,
                    "distance_score": distance_score,
                    "combined_score": combined,
                }

                if combined > best_combined:
                    best_combined = combined
                    best_location = location_result

            # Partner has no geo-locations
            if best_location is None:
                best_location = {
                    "location_index": None, "query": None, "name": None,
                    "direccion": None, "lat": None, "lon": None,
                    "maps_url": None, "place_id": None,
                    "distance_km": None, "distance_score": 0.0,
                    "combined_score": service_score,
                }
                best_combined = service_score

            ranked.append({
                **{k: v for k, v in partner.items() if k != "_id"},
                "_id": partner.get("_id"),
                "service_score": service_score,
                "overall_similarity": service_score,
                "final_score": best_combined,
                "closest_location": best_location,
                "distance_km": best_location["distance_km"],
                "extracted_signals": extracted,
            })

        # Sort by final_score descending — same as notebook
        ranked.sort(key=lambda x: x["final_score"], reverse=True)

        if max_distance_km is not None:
            # Normal path: only return partners within the hard radius
            within_radius = [
                p for p in ranked
                if p["distance_km"] is not None and p["distance_km"] <= max_distance_km
            ]
            return within_radius[:TOP_K]

        # Fallback path (max_distance_km=None): no radius filter, return global top-K
        return ranked[:TOP_K]

    except Exception as e:
        log_to_db("ERROR", "Error searching for partners", {
            "sender_id": None,
            "error": str(e),
            "error_type": type(e).__name__,
            "symptoms": symptoms,
            "location": location,
        })
        return []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def provide_medical_referral(sender_id: str, conversation: dict):
    """Generate and send a medical referral based on symptoms and location."""
    symptoms: list[str] = conversation.get("symptoms", [])
    location: dict = conversation.get("location", {})

    location_type = location.get("location_type", "gps")
    max_distance_km = MAX_DISTANCE_GPS if location_type == "gps" else MAX_DISTANCE_TEXT

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
                        "distance_km": round(p.get("distance_km") or 0, 2),
                        "service_score": round(p.get("service_score", 0), 4),
                        "final_score": round(p.get("final_score", 0), 4),
                    }
                    for p in matching_partners
                ],
            })
        else:
            # Fallback: best global match ignoring radius
            best_match = await find_matching_partners(symptoms, location, max_distance_km=None)

            if best_match:
                fallback_message = await format_fallback_referral(best_match[0], max_distance_km)
                await send_translated_message(sender_id, fallback_message)
                await save_referrals(sender_id, [best_match[0]], symptoms, location, is_fallback=True)

                log_to_db("INFO", "Partner match found (outside radius fallback)", {
                    "sender_id": sender_id,
                    "symptoms": symptoms,
                    "partner": best_match[0].get("partner_name"),
                    "distance_km": round(best_match[0].get("distance_km") or 0, 2),
                    "search_radius_km": max_distance_km,
                })
            else:
                apology_message = (
                    "I apologize, but I couldn't find any medical partners that specialize "
                    "in your symptoms. Please consider contacting your local hospital or "
                    "health center for assistance."
                )
                await send_translated_message(sender_id, apology_message)

                log_to_db("INFO", "No matching partners found", {
                    "sender_id": sender_id,
                    "symptoms": symptoms,
                })

        await update_conversation_recommendation(
            sender_id,
            matching_partners if matching_partners else "No partners found",
        )

        from utils.db_tools import (
            get_conversation,
            increment_referral_count,
            set_waiting_for_another_referral,
        )

        increment_referral_count(sender_id)
        conversation = get_conversation(sender_id)
        referral_count = conversation.get("referral_count", 0)

        if referral_count < 4:
            await send_translated_message(
                sender_id,
                "\n\nDo you need another medical referral for different symptoms? Reply 'yes' or 'no'.",
            )
            set_waiting_for_another_referral(sender_id, True)
        else:
            await send_translated_message(
                sender_id,
                "\n\nYou have reached the maximum number of referrals (4) for this session. "
                "If you need more assistance, please start a new conversation with /reset.",
            )

    except Exception as e:
        log_to_db("ERROR", "Error generating medical referral", {
            "sender_id": sender_id,
            "error": str(e),
        })
        await send_translated_message(
            sender_id,
            "Sorry, there was an error processing your medical referral request. Please try again.",
        )


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _build_location_fields(partner: dict) -> tuple[str, str]:
    """Return (direccion, maps_url) from closest_location or partner_geo_locations."""
    closest = partner.get("closest_location")
    if closest:
        direccion = closest.get("direccion") or closest.get("address") or "Address not available"
        lat, lon = closest.get("lat"), closest.get("lon")
        maps_url = (
            f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            if lat and lon
            else closest.get("maps_url", "")
        )
        return direccion, maps_url

    geos = partner.get("partner_geo_locations", [])
    if geos:
        geo = geos[0]
        direccion = geo.get("address") or "Address not available"
        lat, lon = geo.get("lat"), geo.get("lon")
        maps_url = (
            f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            if lat and lon
            else geo.get("maps_url", "")
        )
        return direccion, maps_url

    return "Address not available", ""


async def format_partner_referrals(partners: list[dict]) -> str:
    """Format partner list into a WhatsApp-friendly message."""
    if not partners:
        return "No medical partners found for your needs."

    parts = ["🏥 *I found the following medical partners for you:*\n"]

    for i, partner in enumerate(partners, 1):
        name = partner.get("partner_name", "Unknown")
        direccion, maps_url = _build_location_fields(partner)

        distance = partner.get("distance_km")
        distance_text = f" ({round(distance, 1)} km away)" if distance else ""

        phone_numbers = partner.get("partner_phone_number") or partner.get("phone_number", [])
        phone_text = ", ".join(phone_numbers) if phone_numbers else "Not available"

        emergency_numbers = partner.get("emergency_number", [])
        emergency_text = (
            ", ".join([n for n in emergency_numbers if n]) if emergency_numbers else "Not available"
        )

        website = (partner.get("website") or "").strip().replace('"', "").replace("'", "")
        website_text = website if website else "Not available"

        block = f"""
━━━━━━━━━━━━━━━
*{i}. {name}*{distance_text}

📍 *Address:*
{direccion}"""

        if maps_url and maps_url.strip():
            block += f"\n🗺️ *Google Maps:* {maps_url.strip()}"

        block += f"""

📞 *Phone:* {phone_text}
🚨 *Emergency:* {emergency_text}
🌐 *Website:* {website_text}
"""
        parts.append(block)

    parts.append(
        "\n━━━━━━━━━━━━━━━\n\n💡 Please contact them directly to schedule an appointment."
    )
    return "\n".join(parts)


async def format_fallback_referral(partner: dict, max_distance_searched: float | None) -> str:
    """Format a fallback referral message for a partner outside the search radius."""
    if not partner:
        return "No medical partners found for your needs."

    intro = (
        f"⚠️ *I couldn't find any medical partners within {max_distance_searched} km of your location.*\n\n"
        "However, this partner might be helpful for your symptoms:\n"
    )

    name = partner.get("partner_name", "Unknown")
    direccion, maps_url = _build_location_fields(partner)

    distance = partner.get("distance_km")
    distance_text = f" ({round(distance, 1)} km away)" if distance else ""

    phone_numbers = partner.get("partner_phone_number") or partner.get("phone_number", [])
    phone_text = ", ".join(phone_numbers) if phone_numbers else "Not available"

    emergency_numbers = partner.get("emergency_number", [])
    emergency_text = (
        ", ".join([n for n in emergency_numbers if n]) if emergency_numbers else "Not available"
    )

    website = (partner.get("website") or "").strip().replace('"', "").replace("'", "")
    website_text = website if website else "Not available"

    block = f"""
━━━━━━━━━━━━━━━
*{name}*{distance_text}

📍 *Address:*
{direccion}"""

    if maps_url and maps_url.strip():
        block += f"\n🗺️ *Google Maps:* {maps_url.strip()}"

    block += f"""

📞 *Phone:* {phone_text}
🚨 *Emergency:* {emergency_text}
🌐 *Website:* {website_text}
"""

    footer = (
        "\n━━━━━━━━━━━━━━━\n\n"
        "⚠️ *Note:* This partner is outside your search radius but may be able to help "
        "with your symptoms.\n\n"
        "💡 Please contact them to verify they can assist you, or consider contacting "
        "your local hospital."
    )

    return intro + block + footer


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def update_conversation_recommendation(sender_id: str, recommendation) -> None:
    """Persist the recommendation summary in the ongoing_conversations collection."""
    from utils.db_tools import ongoing_conversations

    if isinstance(recommendation, list):
        text = (
            f"Found {len(recommendation)} partners: "
            + ", ".join(p.get("partner_name", "Unknown") for p in recommendation)
            if recommendation
            else "No partners found"
        )
    else:
        text = str(recommendation)

    ongoing_conversations.update_one(
        {"sender_id": sender_id},
        {"$set": {"recommendation": text}},
    )


async def save_referrals(
    sender_id: str,
    partners: list[dict],
    symptoms: list[str],
    location: dict,
    is_fallback: bool = False,
) -> bool:
    """Persist referral records and notify partners via WhatsApp template."""
    try:
        from utils.db_tools import db, get_conversation
        from utils.whatsapp import send_template_message

        referrals = db["referrals"]
        conversation = get_conversation(sender_id)
        patient_language = (conversation.get("language", "Unknown") if conversation else "Unknown")
        symptoms_text = ", ".join(symptoms) if symptoms else "Not specified"

        records = []
        for partner in partners:
            closest = partner.get("closest_location") or {}
            extracted = partner.get("extracted_signals") or {}

            records.append({
                # --- Patient ---
                "patient_phone_number": sender_id,
                "patient_language": patient_language,
                "patient_location": {
                    "lat": location.get("lat"),
                    "lon": location.get("lon"),
                    "text_description": location.get("text_description"),
                    "location_type": location.get("location_type", "gps"),
                },

                # --- Symptoms & LLM extraction ---
                "symptoms_raw": symptoms,
                "symptoms_extracted": extracted.get("symptoms", []),
                "services_extracted": extracted.get("possible_services", []),
                "is_emergency": extracted.get("is_emergency", False),

                # --- Partner identity ---
                "partner_id": partner.get("_id"),
                "partner_name": partner.get("partner_name"),
                "partner_category": partner.get("partner_category"),
                "partner_phone_number": partner.get("partner_phone_number", []),
                "partner_whatsapp": partner.get("partner_whatsapp", []),
                "partner_services": partner.get("partner_services", []),

                # --- Matched location ---
                "location_matched": {
                    "address": closest.get("direccion") or closest.get("address"),
                    "lat": closest.get("lat"),
                    "lon": closest.get("lon"),
                    "maps_url": closest.get("maps_url"),
                    "place_id": closest.get("place_id"),
                },
                "distance_km": partner.get("distance_km"),

                # --- Ranking scores ---
                "service_score": partner.get("service_score"),
                "distance_score": closest.get("distance_score"),
                "final_score": partner.get("final_score"),
                "overall_similarity": partner.get("service_score"),  # backwards compat

                # --- Referral metadata ---
                "is_fallback": is_fallback,
                "referred_at": datetime.utcnow(),
                "status": "sent",
            })

        if records:
            referrals.insert_many(records)

            for partner in partners:
                partner_whatsapp = "50258792752"  # partner.get("partner_whatsapp", [None])[0]
                if partner_whatsapp:
                    await send_template_message(
                        recipient_number=partner_whatsapp,
                        template_name="bot_referral_notification",
                        parameters=[sender_id, symptoms_text, patient_language],
                        language_code="es",
                    )
                else:
                    log_to_db("ERROR", "Partner has no WhatsApp number, notification not sent", {
                        "sender_id": sender_id,
                        "partner_name": partner.get("partner_name"),
                        "partner_id": str(partner.get("_id")),
                    })

        return True

    except Exception as e:
        log_to_db("ERROR", "Error saving referrals", {
            "patient_phone_number": sender_id,
            "error": str(e),
            "symptoms": symptoms,
            "partners_count": len(partners) if partners else 0,
        })
        return False