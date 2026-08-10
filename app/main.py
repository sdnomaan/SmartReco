from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.database import initialize_database


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize_database()
        yield

    application = FastAPI(
        title=settings.app_name,
        description="Behavioral AI Recommendation Engine",
        version="1.0.0",
        lifespan=lifespan,
    )

    @application.get("/")
    def home() -> dict[str, str]:
        return {
            "app": settings.app_name,
            "status": "running",
            "message": "Behavioral recommendation engine is online.",
        }

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()