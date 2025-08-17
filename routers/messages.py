import os 
from fastapi import FastAPI, Request, Response, Query, HTTPException, APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime
from pymongo import MongoClient
import httpx
from groq import AsyncGroq

router = APIRouter() 

ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
WHATSAPP_HOOK_TOKEN = os.environ.get("WHATSAPP_HOOK_TOKEN")
WHATSAPP_API_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
# "https://graph.facebook.com/v18.0/739443625915932/messages"

@router.get("/")
def home(): 
    return "Messages router is live"

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        print(f"Comparing {WHATSAPP_HOOK_TOKEN} with {token}")
        if mode == "subscribe" and token == WHATSAPP_HOOK_TOKEN:
            return PlainTextResponse(content=challenge, status_code=200)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        raise HTTPException(status_code=400, detail="Missing parameters")


# Connect to MongoDB

mongo_user = os.getenv('GENEZ_MONGO_DB_USER')
mongo_psw = os.getenv('GENEZ_MONGO_DB_PSW')
mongo_host = os.getenv('GENEZ_MONGO_DB_HOST')
mongo_db = os.getenv('GENEZ_MONGO_DB_NAME')

client = MongoClient(f"mongodb+srv://{mongo_user}:{mongo_psw}@{mongo_host}/?retryWrites=true&w=majority")
db = client[mongo_db]

ongoing_conversations = db["ongoing_conversations"]

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

def handle_conversation(convo_id, sender_id, text):
    # Look for the sender in the ongoing_conversations collection
    conversation = ongoing_conversations.find_one({"sender_id": convo_id})
    
    if conversation:
        # If the sender exists, add the text to the messages array
        ongoing_conversations.update_one(
            {"sender_id": convo_id},
            {"$push": {"messages": {"sender": sender_id, "text": text}}}
        )
    else:
        # If the sender doesn't exist, create a new document
        new_conversation = {
            "sender_id": convo_id,
            "symptoms": [],
            "location": {"lat": None, "lon": None, "text_description": None},
            "language": None,
            "messages": [{"sender": sender_id, "text": text}],
            "recommendation": None
        }
        ongoing_conversations.insert_one(new_conversation)



groq_api = os.getenv('GROQ_API_KEY')
client = AsyncGroq(api_key = groq_api)

async def get_completition(prompt): 
    response = await client.chat.completions.create(
        model = "llama-3.3-70b-versatile"
        , messages = [
            {"role" : "system", "content": "You are a recommendation engine of good medical professionals. Be concise and respectful."}
            , {"role" : "user", "content": prompt}
        ]
        , temperature = 0.8 
        , max_completion_tokens = 120
        , top_p= 1 
    )

    return response.choices[0].message.content 
    
@router.post("/webhook")
async def callback(request: Request): 
    # print("callback is beign called")
    data = await request.json()
    # print("Incoming data:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]
        messages = value.get("messages")

        if messages:
            message = messages[0]
            sender_id = message["from"]

            # Get the message text
            text = message.get("text", {}).get("body", "")

            # Handle conversation (insert message into MongoDB)
            handle_conversation(sender_id, sender_id, text)

            chat_response = await get_completition(text)

            handle_conversation(sender_id, "botsito", chat_response)

            # Prepare response message payload
            payload = {
                "messaging_product": "whatsapp",
                "to": sender_id,
                "type": "text",
                "text": {
                    "body": chat_response
                }
            }

            # Send message back to the user
            async with httpx.AsyncClient() as client:
                resp = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
                # print("Response from WhatsApp:", resp.status_code, resp.text)

    except Exception as e:
        print("Error:", e)

    return {"status": "received"}