from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Online Orthodox Church API",
    version="1.0.0",
    description="Backend API for church shop, prayer requests, and pastoral services."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for container readiness."""
    return {"status": "ok", "service": "online-church-backend"}

@app.get("/api/v1/stub", tags=["Stub"])
async def full_screen_stub():
    """Fullscreen placeholder response for unintegrated pages."""
    return {"message": "Under construction. Fullscreen stub placeholder."}
