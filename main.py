from fastapi import FastAPI
from routers import messages

app = FastAPI()

# Include the user router with prefix
app.include_router(messages.router, prefix="/message", tags=["message"])

@app.get("/")
async def root():
    return {"message": "App is alive"}
