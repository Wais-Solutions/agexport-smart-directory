import os 
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse

from utils.chat import handle_message
from utils.db_tools import db, log_to_db

router = APIRouter() 
WHATSAPP_HOOK_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")

VERIFICATION_BUTTON_TITLE = "Verificar"

@router.get("/")
def home(): 
    return "Messages router is live"

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode      = params.get("hub.mode")
    token     = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        log_to_db("INFO", "Webhook verification attempt", {
            "mode": mode,
            "token_provided": token,
            "expected_token": WHATSAPP_HOOK_TOKEN
        })
        if mode == "subscribe" and token == WHATSAPP_HOOK_TOKEN:
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        raise HTTPException(status_code=400, detail="Missing parameters")

@router.post("/webhook")
async def callback(request: Request): 
    data = await request.json()
    log_to_db("DEBUG", "Webhook data received", {"data": data})

    try:
        entry    = data["entry"][0]
        changes  = entry["changes"][0]
        value    = changes["value"]
        messages = value.get("messages")

        if messages:
            message      = messages[0]
            sender_id    = message["from"]
            message_type = message.get("type")

            log_to_db("INFO", "Processing message", {
                "sender_id":    sender_id,
                "message_type": message_type,
                "message":      message,
            })

            # ── Captura del botón de verificación ──────────────────────────────
            # Los botones de plantilla llegan como type=interactive / button_reply
            if message_type == "interactive":
                interactive = message.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    button_title = interactive.get("button_reply", {}).get("title", "")
                    if button_title == VERIFICATION_BUTTON_TITLE:
                        unix_ts   = int(message.get("timestamp") or time.time())
                        timestamp = datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

                        # Buscar el partner que tiene este número registrado
                        partner_doc = db["partners"].find_one(
                            {"partner_whatsapp": {"$elemMatch": {"$regex": sender_id[-8:]}}},
                            {"partner_name": 1, "partner_category": 1}
                        )
                        partner_name     = partner_doc.get("partner_name", "")     if partner_doc else ""
                        partner_category = partner_doc.get("partner_category", "") if partner_doc else ""

                        db["partner_verifications"].update_one(
                            {"verified_phone": sender_id},
                            {"$set": {
                                "verified_phone":    sender_id,
                                "verified_at":       timestamp,
                                "verified":          True,
                                "partner_name":      partner_name,
                                "partner_category":  partner_category,
                            }},
                            upsert=True,
                        )
                        log_to_db("INFO", f"Partner verified via button: {sender_id}", {
                            "phone":            sender_id,
                            "timestamp":        timestamp,
                            "partner_name":     partner_name,
                            "partner_category": partner_category,
                        })
                        return {"status": "received"}
                    # Si es otro button_reply (p.ej. de otro flujo), cae al handle_message
            # ───────────────────────────────────────────────────────────────────

            await handle_message(message)
        else:
            log_to_db("DEBUG", "No messages in webhook data", {"value": value})

    except Exception as e:
        log_to_db("ERROR", "Error processing webhook", {
            "error": str(e),
            "data":  data,
        })
        try:
            if 'message' in locals() and message:
                from utils.whatsapp import send_text_message
                await send_text_message(message["from"],
                    "Disculpa, hubo un error procesando tu mensaje. Por favor intenta de nuevo.")
        except Exception as send_error:
            log_to_db("ERROR", "Failed to send error message", {"error": str(send_error)})

    return {"status": "received"}