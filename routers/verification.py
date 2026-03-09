import asyncio
from fastapi import APIRouter
from utils.db_tools import db, log_to_db
from utils.whatsapp import send_template_message

router = APIRouter()

COUNTRY_CODE  = "502"
TEMPLATE_NAME = "partners_number_verification"
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
    """Devuelve todos los partners con sus números de WhatsApp."""
    docs = list(db["partners"].find(
        {},
        {"partner_name": 1, "partner_category": 1, "partner_whatsapp": 1}
    ))
    result = []
    for doc in docs:
        raw_numbers = doc.get("partner_whatsapp") or []
        formatted = [format_phone(n) for n in raw_numbers if n]
        result.append({
            "_id":              str(doc["_id"]),
            "partner_name":     doc.get("partner_name", ""),
            "partner_category": doc.get("partner_category", ""),
            "partner_whatsapp": raw_numbers,
            "whatsapp_e164":    formatted,
        })
    return {"partners": result, "total": len(result)}


# ── POST /verification/send ────────────────────────────────────────────────
@router.post("/send")
async def send_verification_blast():
    """
    Envía la template 'partners_number_verification' a todos los números
    de WhatsApp de todos los partners.
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
        raw_numbers  = doc.get("partner_whatsapp") or [] #TEST: ["58792752"]

        for raw in raw_numbers:
            if not raw:
                continue
            phone = format_phone(raw)
            try:
                resp    = await send_template_message(phone, TEMPLATE_NAME, [], TEMPLATE_LANG)
                success = resp is not None and resp.status_code in (200, 201)

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
                        "status_code":  resp.status_code if resp else None,
                        "response":     resp.text[:300] if resp else "No response",
                    },
                )
                results.append({
                    "partner":     partner_name,
                    "phone":       phone,
                    "success":     success,
                    "status_code": resp.status_code if resp else None,
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