from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Fact-Check Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "configured": settings.has_required_keys,
        "openrouter_model": settings.openrouter_model,
        "openrouter_vision_model": settings.openrouter_vision_model,
        "tavily_search_depth": settings.tavily_search_depth,
    }
