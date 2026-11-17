"""User-confirmed, language-aware and data-minimized support diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import platform
import re
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from app.core.config import PROVIDER_NAMES, settings


router = APIRouter(prefix="/api/v1/support", tags=["Support"])

_SAFE_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_CONNECTION_STATUSES = frozenset(
    {
        "connected",
        "model_available",
        "model_required",
        "model_unavailable",
        "authentication_failed",
        "timeout",
        "unavailable",
        "provider_error",
        "remote_blocked",
    }
)
_EXPORT_READMES = {
    "en": """TheraSim support diagnostics

This archive contains only the allow-listed metadata in diagnostics.json.
It does not contain databases, user records, transcripts, case content,
application logs, credentials, API keys, cookies, or names.

Review the file before sharing it. TheraSim does not send or upload this
archive. To contact support, attach it yourself to a message you choose to send.
""",
    "fa": """اطلاعات عیب‌یابی پشتیبانی TheraSim

این بسته فقط فرادادهٔ مجاز در diagnostics.json را در بر دارد.
پایگاه داده، رکوردهای کاربر، رونوشت، محتوای پرونده، گزارش‌های برنامه،
اطلاعات ورود، کلیدهای API، کوکی یا نام افراد در آن نیست.

پیش از اشتراک‌گذاری، فایل را بررسی کنید. TheraSim این بسته را ارسال یا بارگذاری
نمی‌کند. برای تماس با پشتیبانی، خودتان آن را به پیام دلخواه پیوست کنید.
""",
}


class SupportExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool = False
    language: Literal["en", "fa"] = "en"


def _safe_connection_results(request: Request) -> dict[str, object]:
    raw_results = getattr(request.app.state, "provider_test_results", {})
    if not isinstance(raw_results, dict):
        return {}
    safe_results: dict[str, object] = {}
    for provider in PROVIDER_NAMES:
        result = raw_results.get(provider)
        if not isinstance(result, dict):
            continue
        status = result.get("status")
        tested_at = result.get("tested_at")
        success = result.get("success")
        model_available = result.get("model_available")
        if (
            status not in _CONNECTION_STATUSES
            or not isinstance(tested_at, str)
            or not isinstance(success, bool)
            or (
                model_available is not None
                and not isinstance(model_available, bool)
            )
        ):
            continue
        safe_results[provider] = {
            "tested_at": tested_at[:40],
            "success": success,
            "status": status,
            "model_available": model_available,
        }
    return safe_results


def build_support_report(request: Request, language: Literal["en", "fa"]) -> dict[str, object]:
    active_provider = settings.llm_provider
    # Provider metadata is included only as a provider type. Model identifiers
    # and provider endpoints are intentionally omitted from support exports:
    # they are not required for diagnostics and may identify private models or
    # infrastructure. Keep this export compatible with settings-like objects
    # used by alternate deployments and tests.
    safe_model = None
    migrations = getattr(request.app.state, "database_migrations", {})
    schema_versions: dict[str, str | None] = {}
    if isinstance(migrations, dict):
        for name in ("operational", "restricted"):
            applied = migrations.get(name)
            schema_versions[name] = (
                applied[-1].split("_", 1)[0]
                if isinstance(applied, list) and applied
                and isinstance(applied[-1], str)
                else None
            )

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "language": language,
        "application": {
            "name": settings.app_name,
            "version": settings.app_version,
            "backend_version": settings.app_version,
            "frontend_version": settings.app_version,
        },
        "runtime": {
            "operating_system": platform.system(),
            "operating_system_release": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
        },
        "service": {
            "api": "FastAPI",
            "health": "ok",
            "database_schema_versions": schema_versions,
        },
        "model_provider": {
            "active_provider_type": active_provider,
            "model_identifier": safe_model,
            "connection_test_results": _safe_connection_results(request),
        },
        "privacy": {
            "user_records_included": False,
            "transcripts_included": False,
            "case_content_included": False,
            "logs_included": False,
            "credentials_included": False,
            "personal_information_included": False,
            "provider_endpoints_included": False,
        },
    }


def build_support_archive(
    request: Request,
    language: Literal["en", "fa"],
) -> bytes:
    """Create an in-memory archive from a narrow, non-user-data allowlist."""

    report = build_support_report(request, language)
    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "diagnostics.json",
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
        archive.writestr(
            "README.txt",
            _EXPORT_READMES[language],
        )
    return output.getvalue()


@router.get("/preview")
def preview_support_diagnostics(
    request: Request,
    language: Literal["en", "fa"] = Query(default="en"),
) -> dict[str, object]:
    """Return the same sanitized fields that an export would contain."""

    return build_support_report(request, language)


@router.post("/export")
def export_support_diagnostics(
    request: Request,
    payload: SupportExportRequest,
) -> Response:
    if not payload.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Explicit confirmation is required before creating an export.",
        )

    filename = (
        "TheraSim-support-diagnostics-fa.zip"
        if payload.language == "fa"
        else "TheraSim-support-diagnostics.zip"
    )
    return Response(
        content=build_support_archive(request, payload.language),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
