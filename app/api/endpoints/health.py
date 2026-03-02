"""Health check endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.responses import StandardResponse

router = APIRouter(prefix="/health", tags=["health"])
settings = get_settings()


@router.get("", response_model=StandardResponse[dict])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Standard response with service health status
    """
    return StandardResponse(
        success=True,
        message="Service is healthy",
        data={
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "ok",
        },
    )


@router.get("/ready", response_model=StandardResponse[dict])
async def readiness_check():
    """
    Readiness check endpoint.

    Returns:
        Standard response with service readiness status
    """
    return StandardResponse(
        success=True,
        message="Service is ready",
        data={
            "service": settings.APP_NAME,
            "status": "ready",
        },
    )


@router.get("/live", response_model=StandardResponse[dict])
async def liveness_check():
    """
    Liveness check endpoint.

    Returns:
        Standard response with service liveness status
    """
    return StandardResponse(
        success=True,
        message="Service is alive",
        data={
            "service": settings.APP_NAME,
            "status": "alive",
        },
    )
