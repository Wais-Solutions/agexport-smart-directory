from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import messages, database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages.router, prefix="/message", tags=["message"])
app.include_router(database.router, prefix="/db", tags=["database"])

@app.get("/")
async def root():
    return {"message": "App is alive"}