from fastapi import APIRouter

from app.core.config import settings


router = APIRouter()


@router.get("/health", tags=["System"])
def health_check() -> dict[str, str]:
    """Check the availability of the TheraSim backend."""

    return {
        "status": "ok",
        "service": "therasim",
        "component": "backend",
        "version": settings.app_version,
    }