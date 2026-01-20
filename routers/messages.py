import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime
from pymongo import MongoClient
import traceback
import sys

from utils.chat import handle_message
from utils.translation import send_translated_message
from utils.db_tools import log_to_db


router = APIRouter() 
WHATSAPP_HOOK_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")

#### API PING
@router.get("/")
def home(): 
    return "Messages router is live"

#### META VERIFICATION ENDPOINT 
@router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
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

#### MAIN     
@router.post("/webhook")
async def callback(request: Request): 
    data = await request.json()
    
    log_to_db("INFO", "Webhook callback received", {
        "data_preview": str(data)[:200]
    })

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            message = messages[0]
            
            log_to_db("INFO", "Message extracted from webhook", {
                "sender_id": message.get("from"),
                "message_type": message.get("type"),
                "message_preview": str(message)[:200]
            })
            
            await handle_message(message)
            
            log_to_db("INFO", "Message handled successfully", {
                "sender_id": message.get("from")
            })

    except Exception as e:
        # Get full traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        full_traceback = ''.join(tb_lines)
        
        # DETAILED error logging
        error_details = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "full_traceback": full_traceback,
            "line_number": exc_traceback.tb_lineno if exc_traceback else None,
            "function_name": exc_traceback.tb_frame.f_code.co_name if exc_traceback else None,
            "has_message_var": 'message' in locals(),
            "has_data_var": 'data' in locals(),
        }
        
        if 'message' in locals() and message:
            error_details["sender_id"] = message.get("from")
            error_details["message_type"] = message.get("type")
        
        log_to_db("ERROR", "CRITICAL ERROR in webhook callback", error_details)
        
        # Also print to console for immediate debugging
        print("=" * 80)
        print("CRITICAL ERROR IN WEBHOOK CALLBACK")
        print("=" * 80)
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"Full Traceback:")
        print(full_traceback)
        print("=" * 80)
        
        # Send error message to user if possible
        try:
            if 'message' in locals() and message:
                sender_id = message["from"]
                error_message = "Sorry, there was an error processing your message. Please try again."
                await send_translated_message(sender_id, error_message)
                
                log_to_db("INFO", "Error message sent to user", {
                    "sender_id": sender_id
                })
        except Exception as send_error:
            log_to_db("ERROR", "Failed to send error message to user", {
                "error": str(send_error),
                "traceback": traceback.format_exc()
            })
            print(f"Failed to send error message: {send_error}")

    return {"status": "received"}