"""Memory candidate and review endpoints scoped to a simulation Run."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictStr,
    field_validator,
)

from app.api.routes.runs import RunService, get_run_service
from app.api.routes.auth import get_current_user
from app.services.character_model import (
    MemoryEvidenceQuote,
    MemoryProposal,
)
from app.services.memory import (
    MemoryConsolidationError,
    MemoryConsolidationSuggestion,
    MemoryEvidenceRecord,
    MemoryEvidenceValidationError,
    MemoryIdempotencyConflictError,
    MemoryRecord,
    MemoryRequestNotCompletedError,
    MemoryRequestNotFoundError,
    MemoryReviewConflictError,
    MemoryReviewRecord,
    MemoryService,
)
from app.services.memory_extraction import (
    MemoryExtractionStatusService,
)
from app.services.local_auth import AuthenticatedUser


router = APIRouter(
    prefix="/api/v1/simulation-runs/{run_id}/memories",
    tags=["Longitudinal Memory"],
)

class MemoryCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: str = Field(min_length=1, max_length=200)
    interaction_request_id: str = Field(min_length=1, max_length=200)
    proposal_index: int = Field(ge=0)
    memory_scope: Literal["episodic", "semantic", "therapeutic"]
    proposal: "MemoryProposalRequest"
    supersedes_memory_id: str | None = Field(default=None, max_length=200)

    @field_validator(
        "session_id",
        "interaction_request_id",
        "supersedes_memory_id",
    )
    @classmethod
    def validate_optional_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Field must not be blank.")
        return value.strip() if value is not None else None


class MemoryEvidenceQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    message_id: StrictStr = Field(min_length=1, max_length=200)
    exact_quote: StrictStr = Field(min_length=1, max_length=12000)

    @field_validator("message_id", "exact_quote")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be blank.")
        return value


class MemoryProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    proposal_id: StrictStr = Field(min_length=1, max_length=200)
    memory_type: StrictStr = Field(min_length=1, max_length=100)
    information_class: Literal[
        "confirmed_fact",
        "explicit_disclosure",
        "system_generated_summary",
        "reported_outcome",
    ]
    content: StrictStr = Field(min_length=1, max_length=12000)
    evidence: list[MemoryEvidenceQuoteRequest] = Field(min_length=1, max_length=20)
    confidence: StrictFloat = Field(ge=0.0, le=1.0)
    status: Literal["candidate", "requires_review"] = "candidate"

    @field_validator("proposal_id", "memory_type", "content")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be blank.")
        return value

    @field_validator("evidence")
    @classmethod
    def validate_unique_evidence_messages(
        cls,
        value: list[MemoryEvidenceQuoteRequest],
    ) -> list[MemoryEvidenceQuoteRequest]:
        message_ids = [item.message_id for item in value]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError(
                "Each source message may be cited only once."
            )
        return value

    def to_contract(self) -> MemoryProposal:
        return MemoryProposal(
            proposal_id=self.proposal_id,
            memory_type=self.memory_type,
            information_class=self.information_class,
            content=self.content,
            evidence=tuple(
                MemoryEvidenceQuote(
                    message_id=item.message_id,
                    exact_quote=item.exact_quote,
                )
                for item in self.evidence
            ),
            confidence=self.confidence,
            status=self.status,
        )


class MemoryReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decision: Literal["accepted", "rejected"]
    rationale: str = Field(min_length=1, max_length=4000)

    @field_validator("rationale")
    @classmethod
    def validate_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be blank.")
        return value.strip()


class MemoryConsolidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_memory_ids: list[StrictStr] = Field(min_length=2, max_length=5)
    content: StrictStr = Field(min_length=1, max_length=12000)

    @field_validator("source_memory_ids")
    @classmethod
    def validate_source_ids(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("Source memory IDs must be distinct and nonblank.")
        return cleaned

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field must not be blank.")
        return value.strip()


class MemoryEvidenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    relationship_type: str
    start_offset: int | None
    end_offset: int | None
    excerpt: str | None


class MemoryConsolidationSourceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_memory_id: str
    source_memory_version: int
    relationship_type: str
    content: str
    source_session_id: str


class MemoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    run_id: str
    source_session_id: str | None
    memory_type: str
    information_class: str
    content: str
    confidence: float | None
    status: str
    memory_version: int
    memory_scope: str
    supersedes_memory_id: str | None
    evidence: list[MemoryEvidenceData]
    consolidation_sources: list[MemoryConsolidationSourceData] = Field(
        default_factory=list
    )
    created_at: str
    updated_at: str


class MemoryConsolidationSuggestionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_memory_ids: list[str]
    relationship_type: str
    similarity: float
    sources: list[MemoryConsolidationSourceData]


class MemoryReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: str
    memory_id: str
    decision: str
    reviewer_id: str
    rationale: str
    reviewed_at: str


class MemoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[MemoryData]


class MemoryCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: MemoryData


class MemoryReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: MemoryData
    review: MemoryReviewData


class MemoryConsolidationSuggestionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[MemoryConsolidationSuggestionData]


class MemoryConsolidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: MemoryData


class MemoryExtractionStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    interaction_request_id: str
    status: str
    attempt_count: int
    candidate_count: int
    last_error_code: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class MemoryExtractionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: MemoryExtractionStatusData


def get_memory_service(request: Request) -> MemoryService:
    service = getattr(request.app.state, "memory_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="memory_service_unavailable",
        )
    return service


def get_memory_extraction_status_service(
    request: Request,
) -> MemoryExtractionStatusService:
    service = getattr(
        request.app.state,
        "memory_extraction_status_service",
        None,
    )
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="memory_extraction_status_unavailable",
        )
    return service


def _ensure_run_exists(run_id: str, service: RunService) -> None:
    if service.get_run(run_id) is None:
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        )


def _memory_data(
    memory: MemoryRecord,
    evidence: list[MemoryEvidenceRecord],
    consolidation_sources=(),
) -> MemoryData:
    return MemoryData(
        memory_id=memory.memory_id,
        run_id=memory.run_id,
        source_session_id=memory.source_session_id,
        memory_type=memory.memory_type,
        information_class=memory.information_class,
        content=memory.content,
        confidence=memory.confidence,
        status=memory.status,
        memory_version=memory.memory_version,
        memory_scope=memory.memory_scope,
        supersedes_memory_id=memory.supersedes_memory_id,
        evidence=[
            MemoryEvidenceData(
                message_id=item.message_id,
                relationship_type=item.relationship_type,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                excerpt=item.excerpt,
            )
            for item in evidence
        ],
        consolidation_sources=[
            MemoryConsolidationSourceData(
                source_memory_id=item.source_memory_id,
                source_memory_version=item.source_memory_version,
                relationship_type=item.relationship_type,
                content=item.content,
                source_session_id=item.source_session_id,
            )
            for item in consolidation_sources
        ],
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


def _raise_memory_error(exc: Exception) -> None:
    if isinstance(exc, MemoryRequestNotFoundError):
        raise HTTPException(
            status_code=404,
            detail="source_interaction_not_found",
        ) from None
    if isinstance(exc, MemoryRequestNotCompletedError):
        raise HTTPException(
            status_code=409,
            detail="source_interaction_not_completed",
        ) from None
    if isinstance(exc, MemoryEvidenceValidationError):
        raise HTTPException(
            status_code=422,
            detail="memory_evidence_invalid",
        ) from None
    if isinstance(exc, MemoryIdempotencyConflictError):
        raise HTTPException(
            status_code=409,
            detail="memory_proposal_conflict",
        ) from None
    if isinstance(exc, MemoryReviewConflictError):
        raise HTTPException(
            status_code=409,
            detail="memory_review_conflict",
        ) from None
    if isinstance(exc, MemoryConsolidationError):
        raise HTTPException(
            status_code=422,
            detail="memory_consolidation_invalid",
        ) from None
    raise HTTPException(
        status_code=500,
        detail="memory_service_error",
    ) from None


@router.get(
    "",
    response_model=MemoryListResponse,
)
def list_memories(
    run_id: str,
    status: Literal[
        "active",
        "superseded",
        "requires_review",
        "rejected",
    ]
    | None = Query(default=None),
    service: MemoryService = Depends(get_memory_service),
    run_service: RunService = Depends(get_run_service),
):
    """List memory records and their cited evidence for one Run."""

    _ensure_run_exists(run_id, run_service)
    memories = service.list_memories(run_id, status=status)
    return MemoryListResponse(
        data=[
            _memory_data(
                memory,
                service.list_evidence(memory.memory_id),
                service.list_consolidation_sources(memory.memory_id),
            )
            for memory in memories
        ]
    )


@router.get(
    "/consolidation-suggestions",
    response_model=MemoryConsolidationSuggestionsResponse,
)
def list_memory_consolidation_suggestions(
    run_id: str,
    service: MemoryService = Depends(get_memory_service),
    run_service: RunService = Depends(get_run_service),
):
    """Suggest cross-session memory relationships without changing records."""

    _ensure_run_exists(run_id, run_service)
    suggestions: list[MemoryConsolidationSuggestion] = (
        service.list_consolidation_suggestions(run_id)
    )
    return MemoryConsolidationSuggestionsResponse(
        data=[
            MemoryConsolidationSuggestionData(
                source_memory_ids=list(item.source_memory_ids),
                relationship_type=item.relationship_type,
                similarity=item.similarity,
                sources=[
                    MemoryConsolidationSourceData(
                        source_memory_id=source.source_memory_id,
                        source_memory_version=source.source_memory_version,
                        relationship_type=source.relationship_type,
                        content=source.content,
                        source_session_id=source.source_session_id,
                    )
                    for source in item.sources
                ],
            )
            for item in suggestions
        ]
    )


@router.post(
    "/consolidations",
    response_model=MemoryConsolidationResponse,
    status_code=201,
)
def propose_memory_consolidation(
    run_id: str,
    request: MemoryConsolidationRequest,
    service: MemoryService = Depends(get_memory_service),
    run_service: RunService = Depends(get_run_service),
):
    """Create an evidence-linked candidate requiring reviewer approval."""

    _ensure_run_exists(run_id, run_service)
    try:
        memory = service.propose_consolidation(
            run_id,
            source_memory_ids=request.source_memory_ids,
            content=request.content,
        )
    except MemoryConsolidationError as exc:
        _raise_memory_error(exc)
    return MemoryConsolidationResponse(
        data=_memory_data(
            memory,
            service.list_evidence(memory.memory_id),
            service.list_consolidation_sources(memory.memory_id),
        )
    )


@router.get(
    "/processing/{interaction_request_id}",
    response_model=MemoryExtractionStatusResponse,
)
def get_memory_extraction_status(
    run_id: str,
    interaction_request_id: str,
    service: MemoryExtractionStatusService = Depends(
        get_memory_extraction_status_service
    ),
    run_service: RunService = Depends(get_run_service),
):
    """Return sanitized extraction-job status for a completed interaction."""

    _ensure_run_exists(run_id, run_service)
    job = service.get_job(run_id, interaction_request_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="memory_extraction_job_not_found",
        )
    return MemoryExtractionStatusResponse(
        data=MemoryExtractionStatusData(
            job_id=job.job_id,
            interaction_request_id=job.interaction_request_id,
            status=job.status,
            attempt_count=job.attempt_count,
            candidate_count=job.candidate_count,
            last_error_code=job.last_error_code,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )
    )


@router.post(
    "/candidates",
    response_model=MemoryCandidateResponse,
    status_code=201,
)
def create_memory_candidate(
    run_id: str,
    request: MemoryCandidateRequest,
    service: MemoryService = Depends(get_memory_service),
    run_service: RunService = Depends(get_run_service),
):
    """Persist a validated proposal as an inactive review candidate."""

    _ensure_run_exists(run_id, run_service)
    created_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    try:
        memory = service.create_candidate(
            run_id=run_id,
            session_id=request.session_id,
            interaction_request_id=request.interaction_request_id,
            proposal_index=request.proposal_index,
            memory_scope=request.memory_scope,
            proposal=request.proposal.to_contract(),
            created_at=created_at,
            supersedes_memory_id=request.supersedes_memory_id,
        )
    except (
        MemoryRequestNotFoundError,
        MemoryRequestNotCompletedError,
        MemoryEvidenceValidationError,
        MemoryIdempotencyConflictError,
        MemoryReviewConflictError,
    ) as exc:
        _raise_memory_error(exc)
    return MemoryCandidateResponse(
        data=_memory_data(
            memory,
            service.list_evidence(memory.memory_id),
            service.list_consolidation_sources(memory.memory_id),
        )
    )


@router.post(
    "/{memory_id}/review",
    response_model=MemoryReviewResponse,
)
def review_memory_candidate(
    run_id: str,
    memory_id: str,
    request: MemoryReviewRequest,
    service: MemoryService = Depends(get_memory_service),
    run_service: RunService = Depends(get_run_service),
    reviewer: AuthenticatedUser = Depends(get_current_user),
):
    """Accept or reject a candidate, preserving the review rationale."""

    _ensure_run_exists(run_id, run_service)
    candidate = next(
        (
            memory
            for memory in service.list_memories(run_id)
            if memory.memory_id == memory_id
        ),
        None,
    )
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="memory_candidate_not_found",
        )

    reviewed_at = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    try:
        memory, review = service.review_candidate(
            memory_id,
            decision=request.decision,
            reviewer_id=reviewer.user_id,
            rationale=request.rationale,
            reviewed_at=reviewed_at,
        )
    except MemoryReviewConflictError as exc:
        _raise_memory_error(exc)
    return MemoryReviewResponse(
        data=_memory_data(
            memory,
            service.list_evidence(memory.memory_id),
            service.list_consolidation_sources(memory.memory_id),
        ),
        review=MemoryReviewData(
            review_id=review.review_id,
            memory_id=review.memory_id,
            decision=review.decision,
            reviewer_id=review.reviewer_id,
            rationale=review.rationale,
            reviewed_at=review.reviewed_at,
        ),
    )
