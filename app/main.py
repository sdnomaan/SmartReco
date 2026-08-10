from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.events import router as events_router
from app.api.admin import router as admin_router
from app.config import get_settings
from app.api.auth import router as auth_router
from app.api.products import router as products_router
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
    application.mount("/static", StaticFiles(directory="static"), name="static")
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_value,
        same_site="lax",
        https_only=settings.environment.lower() not in {"development", "testing"},
    )
    application.include_router(auth_router)
    application.include_router(products_router)
    application.include_router(admin_router)
    application.include_router(events_router)

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