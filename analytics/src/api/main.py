from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from analytics.src.api.routes.metrics import router as metrics_router

app = FastAPI(
    title="Online Church Analytics Service",
    version="1.0.0",
    description="DWH serving layer providing financial and parishioner activity metrics."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)


@app.get("/health", tags=["System"])
async def health_check():
    """Analytics service health check."""
    return {"status": "ok", "service": "church-analytics-api"}
