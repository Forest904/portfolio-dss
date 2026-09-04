"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.router import router
from app.core.config import API_DESCRIPTION, API_TITLE, API_VERSION


def create_app() -> FastAPI:
    """Create and configure the HTTP application."""
    application = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
    )
    application.include_router(router)
    return application


app = create_app()
