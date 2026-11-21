"""Optional, manual release metadata lookup."""

from pathlib import Path

from fastapi import APIRouter

from app.core.config import settings
from app.services.update_metadata import (
    get_latest_release_metadata,
    get_source_checkout_status,
)


router = APIRouter(prefix="/api/v1/updates", tags=["Updates"])


@router.get("/check")
def check_for_updates() -> dict[str, object]:
    """Fetch stable release metadata on demand; never install or modify files."""

    repository_root = Path(__file__).resolve().parents[4]
    return {
        "current_version": settings.app_version,
        "source_checkout": get_source_checkout_status(repository_root),
        "release": get_latest_release_metadata(settings.app_version),
        "automatic_installation": False,
    }
