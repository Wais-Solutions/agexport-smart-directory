import os
import asyncio
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from utils.db_tools import db, log_to_db

router = APIRouter()

WHATSAPP_TOKEN   = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
COUNTRY_CODE     = "502"   # Guatemala
TEMPLATE_NAME    = "partners_number_verification"
TEMPLATE_LANG    = "es"


def format_phone(raw: str) -> str:
    """'23857777' → '50223857777'  (agrega 502 si no lo tiene)"""
    digits = "".join(filter(str.isdigit, raw))
    if digits.startswith("502"):
        return digits
    return COUNTRY_CODE + digits


async def send_template(phone: str) -> dict:
    """Envía la template 'partners_number_verification' a un número."""
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": TEMPLATE_LANG},
        },
    }
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    return {"status_code": resp.status_code, "body": resp.json()}


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
        raw_numbers = ["58792752"]  # TEST: reemplazar con doc.get("partner_whatsapp") or []
        formatted = [format_phone(n) for n in raw_numbers if n]
        result.append({
            "_id":              str(doc["_id"]),
            "partner_name":     doc.get("partner_name", ""),
            "partner_category": doc.get("partner_category", ""),
            "partner_whatsapp": raw_numbers,       # originales (para mostrar en UI)
            "whatsapp_e164":    formatted,          # con código de país (para enviar)
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

    results = []
    sent_count   = 0
    failed_count = 0

    for doc in docs:
        partner_name = doc.get("partner_name", str(doc["_id"]))
        raw_numbers  = doc.get("partner_whatsapp") or []

        for raw in raw_numbers:
            if not raw:
                continue
            phone = format_phone(raw)
            try:
                api_resp = await send_template(phone)
                success  = api_resp["status_code"] in (200, 201)
                if success:
                    sent_count += 1
                else:
                    failed_count += 1

                log_to_db(
                    "INFO" if success else "ERROR",
                    f"Verification blast → {partner_name} ({phone})",
                    {
                        "partner_name":  partner_name,
                        "phone":         phone,
                        "raw_phone":     raw,
                        "status_code":   api_resp["status_code"],
                        "response":      str(api_resp["body"])[:300],
                    },
                )
                results.append({
                    "partner": partner_name,
                    "phone":   phone,
                    "success": success,
                    "status_code": api_resp["status_code"],
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

            # Pequeña pausa para no saturar la API de Meta
            await asyncio.sleep(0.2)

    return {
        "sent":    sent_count,
        "failed":  failed_count,
        "total":   sent_count + failed_count,
        "results": results,
    }