from fastapi import FastAPI
from routers import messages, database 

app = FastAPI()

# Include the user router with prefix
app.include_router(messages.router, prefix="/message", tags=["message"])
app.include_router(database.router, prefix="/db", tags=["database"]) 

@app.get("/")
async def root():
    return {"message": "App is alive"}
