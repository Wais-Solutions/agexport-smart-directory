from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import messages, database, verification, services

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages.router,      prefix="/message",      tags=["message"])
app.include_router(database.router,      prefix="/db",           tags=["database"])
app.include_router(verification.router,  prefix="/verification", tags=["verification"])
app.include_router(services.router,      prefix="/services",     tags=["services"])
@app.get("/")
async def root():
    return {"message": "App is alive"}