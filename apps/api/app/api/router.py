"""Top-level API routes."""

from fastapi import APIRouter

from app.api.schemas import HealthResponse
from app.core.config import API_VERSION, SERVICE_NAME

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Report whether the API process is ready to serve requests."""
    return HealthResponse(status="ok", service=SERVICE_NAME, version=API_VERSION)
