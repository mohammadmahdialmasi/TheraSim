"""Therapist-visible synthetic case catalog endpoints."""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from app.services.cases import CaseService


router = APIRouter(
    prefix="/api/v1/cases",
    tags=["Cases"],
)


class CaseListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_code: str
    display_name: str
    modality: str
    available_languages: list[str]
    status: str


class PaginationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int
    offset: int
    total: int


class CaseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[CaseListItem]
    pagination: PaginationResponse


class PublicPresentation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age: int | None
    occupation: str | None
    presenting_concerns: list[str]
    initial_disclosure: str | None


class CaseVersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_version_id: str
    version_number: str
    modality: str
    language: str
    presentation: PublicPresentation


class CaseDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    case_code: str
    display_name: str
    status: str
    versions: list[CaseVersionResponse]


class CaseDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: CaseDetail


def get_case_service(request: Request) -> CaseService:
    service = getattr(request.app.state, "case_service", None)

    if service is None:
        raise HTTPException(
            status_code=503,
            detail="case_service_unavailable",
        )

    return service


def _iter_active_cases(service: CaseService) -> Iterator:
    """Read the complete active catalog in bounded pages."""

    page_size = 50
    offset = 0

    while True:
        page = service.list_cases(
            status="active",
            limit=page_size,
            offset=offset,
        )

        if not page:
            break

        yield from page

        if len(page) < page_size:
            break

        offset += len(page)


def _visible_versions(service: CaseService, case_id: str):
    """Return only versions with an explicit public profile."""

    for version in service.list_case_versions(case_id):
        profile = service.get_public_profile(
            version.case_version_id
        )

        if profile is not None:
            yield version, profile


@router.get(
    "",
    response_model=CaseListResponse,
)
def list_cases(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    modality: str | None = Query(default=None, min_length=1, max_length=50),
    language: str | None = Query(default=None, min_length=2, max_length=20),
    service: CaseService = Depends(get_case_service),
):
    """List therapist-visible versions of active synthetic cases."""

    grouped: dict[tuple[str, str], dict] = {}

    for case in _iter_active_cases(service):
        for version, _profile in _visible_versions(
            service,
            case.case_id,
        ):
            if modality and version.modality.casefold() != modality.casefold():
                continue

            key = (case.case_id, version.modality)

            if key not in grouped:
                grouped[key] = {
                    "case_id": case.case_id,
                    "case_code": case.case_code,
                    "display_name": case.display_name,
                    "modality": version.modality,
                    "available_languages": set(),
                    "status": case.status,
                }

            grouped[key]["available_languages"].add(
                version.language
            )

    entries = []

    for item in grouped.values():
        languages = sorted(item["available_languages"])

        if language and not any(
            value.casefold() == language.casefold()
            for value in languages
        ):
            continue

        entries.append(
            CaseListItem(
                case_id=item["case_id"],
                case_code=item["case_code"],
                display_name=item["display_name"],
                modality=item["modality"],
                available_languages=languages,
                status=item["status"],
            )
        )

    entries.sort(
        key=lambda item: (
            item.display_name.casefold(),
            item.modality.casefold(),
            item.case_id,
        )
    )

    total = len(entries)

    return CaseListResponse(
        data=entries[offset:offset + limit],
        pagination=PaginationResponse(
            limit=limit,
            offset=offset,
            total=total,
        ),
    )


@router.get(
    "/{case_id}",
    response_model=CaseDetailResponse,
)
def get_case(
    case_id: str,
    service: CaseService = Depends(get_case_service),
):
    """Retrieve explicitly therapist-visible case presentation data."""

    case = service.get_case(case_id)

    if case is None or case.status != "active":
        raise HTTPException(
            status_code=404,
            detail="case_not_found",
        )

    versions = []

    for version, profile in _visible_versions(
        service,
        case_id,
    ):
        versions.append(
            CaseVersionResponse(
                case_version_id=version.case_version_id,
                version_number=version.version_number,
                modality=version.modality,
                language=version.language,
                presentation=PublicPresentation(
                    age=profile.age,
                    occupation=profile.occupation,
                    presenting_concerns=list(
                        profile.presenting_concerns
                    ),
                    initial_disclosure=profile.initial_disclosure,
                ),
            )
        )

    if not versions:
        raise HTTPException(
            status_code=404,
            detail="case_not_available",
        )

    return CaseDetailResponse(
        data=CaseDetail(
            case_id=case.case_id,
            case_code=case.case_code,
            display_name=case.display_name,
            status=case.status,
            versions=versions,
        )
    )
