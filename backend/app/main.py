from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ingredients import router as ingredients_router
from app.config import settings

app = FastAPI(
    title="MiSt API",
    version="0.2.0",
    description="Sustainability analytics for caterers — backend API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingredients_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version, "environment": settings.environment}
