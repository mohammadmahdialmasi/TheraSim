"""Persisted Run analytics and research-oriented JSON export."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.api.routes.runs import RunService, get_run_service
from app.services.run_analytics import (
    RunAnalyticsIntegrityError,
    RunAnalyticsNotFoundError,
    RunAnalyticsService,
    RunAnalyticsSnapshot,
)


router = APIRouter(
    prefix="/api/v1/simulation-runs/{run_id}/analytics",
    tags=["Run Analytics"],
)


class RunAnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_scope: str
    run_id: str
    generated_at: str
    time_range_start: str | None
    time_range_end: str | None
    sessions: list[dict[str, object]]
    events: list[dict[str, object]]
    event_counts: dict[str, int]
    memories: list[dict[str, object]]
    memory_counts: dict[str, int]
    state_transitions: list[dict[str, object]]
    transition_counts: dict[str, int]
    plan_revisions: list[dict[str, object]]
    current_plan: dict[str, object] | None
    evaluations: list[dict[str, object]]
    competency_trajectories: list[dict[str, object]]
    limitations: list[str]


def get_run_analytics_service(request: Request) -> RunAnalyticsService:
    service = getattr(request.app.state, "run_analytics_service", None)
    if service is None:
        raise HTTPException(
            status_code=503,
            detail="run_analytics_service_unavailable",
        )
    return service


def _response(snapshot: RunAnalyticsSnapshot) -> RunAnalyticsResponse:
    return RunAnalyticsResponse(
        data_scope=snapshot.data_scope,
        run_id=snapshot.run_id,
        generated_at=snapshot.generated_at,
        time_range_start=snapshot.time_range_start,
        time_range_end=snapshot.time_range_end,
        sessions=list(snapshot.sessions),
        events=list(snapshot.events),
        event_counts=snapshot.event_counts,
        memories=list(snapshot.memories),
        memory_counts=snapshot.memory_counts,
        state_transitions=list(snapshot.state_transitions),
        transition_counts=snapshot.transition_counts,
        plan_revisions=list(snapshot.plan_revisions),
        current_plan=snapshot.current_plan,
        evaluations=list(snapshot.evaluations),
        competency_trajectories=list(snapshot.competency_trajectories),
        limitations=list(snapshot.limitations),
    )


@router.get("", response_model=RunAnalyticsResponse)
def get_run_analytics(
    run_id: str,
    service: RunAnalyticsService = Depends(get_run_analytics_service),
    run_service: RunService = Depends(get_run_service),
):
    """Return real persisted records and count summaries for one Run."""

    if run_service.get_run(run_id) is None:
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        )
    try:
        return _response(service.get_snapshot(run_id))
    except RunAnalyticsNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="simulation_run_not_found",
        ) from None
    except RunAnalyticsIntegrityError:
        raise HTTPException(
            status_code=500,
            detail="run_analytics_data_invalid",
        ) from None
