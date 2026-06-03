import asyncio
import httpx
from fastapi import APIRouter
from utils.db_tools import db, log_to_db
from utils.whatsapp import headers, WHATSAPP_API_URL

router = APIRouter()

COUNTRY_CODE  = "502"
TEMPLATE_NAME = "partners_whatsapp_verification"
TEMPLATE_LANG = "es"


def format_phone(raw: str) -> str:
    """'23857777' → '50223857777' (agrega 502 si no lo tiene)"""
    digits = "".join(filter(str.isdigit, raw))
    if digits.startswith("502"):
        return digits
    return COUNTRY_CODE + digits


# ── GET /verification/partners ─────────────────────────────────────────────
@router.get("/partners")
def get_partners_for_verification():
    """
    Devuelve todos los partners con sus números de WhatsApp e info de verificación.
    verified_phones: lista de números e164 que ya presionaron el botón.
    verified_at: timestamp unix del primer número que confirmó (para mostrar en UI).
    """
    docs = list(db["partners"].find(
        {},
        {"partner_name": 1, "partner_category": 1, "partner_whatsapp": 1}
    ))

    # Cargar todas las verificaciones de una vez para evitar N queries
    verifications: dict[str, dict] = {
        v["verified_phone"]: v
        for v in db["partner_verifications"].find({}, {"_id": 0})
        if v.get("verified_phone")
    }

    result = []
    for doc in docs:
        raw_numbers = doc.get("partner_whatsapp") or []
        formatted   = [format_phone(n) for n in raw_numbers if n]

        confirmed_phones = [p for p in formatted if p in verifications]

        result.append({
            "_id":              str(doc["_id"]),
            "partner_name":     doc.get("partner_name", ""),
            "partner_category": doc.get("partner_category", ""),
            "partner_whatsapp": raw_numbers,
            "whatsapp_e164":    formatted,
            "verified_phones":  confirmed_phones,
            "verified_at":      verifications[confirmed_phones[0]]["verified_at"]
                                if confirmed_phones else None,
        })

    return {"partners": result, "total": len(result)}


# ── POST /verification/send ────────────────────────────────────────────────
@router.post("/send")
async def send_verification_blast():
    """
    Envía la template a todos los números de WhatsApp de todos los partners.
    Pasa el nombre del partner como parámetro {{partner_name}} del body.
    """
    docs = list(db["partners"].find(
        {},
        {"partner_name": 1, "partner_whatsapp": 1}
    ))

    results      = []
    sent_count   = 0
    failed_count = 0

    for doc in docs:
        partner_name = doc.get("partner_name", str(doc["_id"]))
        raw_numbers  = ["58792752"]  # TEST — reemplazar por: doc.get("partner_whatsapp") or []

        for raw in raw_numbers:
            if not raw:
                continue
            phone = format_phone(raw)
            try:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "template",
                    "template": {
                        "name": TEMPLATE_NAME,
                        "language": {"code": TEMPLATE_LANG},
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": partner_name}
                                ]
                            }
                        ]
                    }
                }

                async with httpx.AsyncClient() as client:
                    resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)

                print("META RESPONSE:", resp.status_code, resp.text)
                success = resp.status_code in (200, 201)

                if success:
                    sent_count += 1
                else:
                    failed_count += 1

                log_to_db(
                    "INFO" if success else "ERROR",
                    f"Verification blast → {partner_name} ({phone})",
                    {
                        "partner_name": partner_name,
                        "phone":        phone,
                        "raw_phone":    raw,
                        "status_code":  resp.status_code,
                        "response":     resp.text[:300],
                    },
                )
                results.append({
                    "partner":     partner_name,
                    "phone":       phone,
                    "success":     success,
                    "status_code": resp.status_code,
                })

            except Exception as e:
                failed_count += 1
                log_to_db("ERROR", f"Verification blast FAILED → {partner_name} ({phone})", {
                    "partner_name": partner_name,
                    "phone":        phone,
                    "error":        str(e),
                })
                results.append({
                    "partner": partner_name,
                    "phone":   phone,
                    "success": False,
                    "error":   str(e),
                })

            await asyncio.sleep(0.2)

    return {
        "sent":    sent_count,
        "failed":  failed_count,
        "total":   sent_count + failed_count,
        "results": results,
    }