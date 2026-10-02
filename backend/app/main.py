from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import chat, items

app = FastAPI(
    title="Online Orthodox Church API",
    version="1.0.0",
    description="Backend API for church shop, prayer requests, and pastoral services.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(items.router)
app.include_router(chat.router)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for container readiness."""
    return {"status": "ok", "service": "online-church-backend"}
