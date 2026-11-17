import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.routes.auth import get_current_user, router as auth_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.health import router as health_router
from app.api.routes.runs import router as runs_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.cases import router as cases_router
from app.api.routes.llm import router as llm_router
from app.api.routes.interactions import router as interactions_router
from app.api.routes.memories import router as memories_router
from app.api.routes.events import router as events_router
from app.api.routes.treatment_plans import router as treatment_plans_router
from app.core.config import settings
from app.llm.client import OpenAICompatibleClient
from app.llm.evaluator_agent import EvaluatorAgent
from app.llm.memory_extraction_agent import MemoryExtractionAgent
from app.llm.patient_agent import PatientAgent
from app.persistence.database import DatabaseManager
from app.services.cases import CaseService
from app.services.evaluations import EvaluationService
from app.services.interactions import InteractionService
from app.services.memory import MemoryService
from app.services.event_reviews import EventReviewService
from app.services.treatment_plans import TreatmentPlanService
from app.services.memory_extraction import (
    MemoryExtractionStatusService,
    MemoryExtractionWorker,
)
from app.services.interaction_status import InteractionRequestStatusService
from app.services.runs import RunService
from app.services.sessions import SessionService
from app.services.local_auth import LocalAuthService
from app.services.run_analytics import RunAnalyticsService


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize local databases before the API starts serving requests."""

    database_manager = DatabaseManager()
    applied_migrations = database_manager.initialize()

    application.state.database_manager = database_manager
    application.state.database_migrations = applied_migrations
    application.state.local_auth_service = LocalAuthService(database_manager)
    application.state.case_service = CaseService(database_manager)
    application.state.run_service = RunService(database_manager)
    application.state.session_service = SessionService(database_manager)
    application.state.interaction_request_status_service = (
        InteractionRequestStatusService(database_manager)
    )
    application.state.memory_service = MemoryService(database_manager)
    application.state.event_review_service = EventReviewService(database_manager)
    application.state.treatment_plan_service = TreatmentPlanService(
        database_manager
    )
    application.state.memory_extraction_status_service = (
        MemoryExtractionStatusService(database_manager)
    )
    application.state.memory_extraction_worker = None
    application.state.patient_agent = None
    application.state.interaction_service = None
    evaluator_agent = None
    memory_worker_task: asyncio.Task | None = None

    # Do not require a configured model merely to start the API.
    # No provider request is made during application startup.
    provider_config = settings.active_provider

    if provider_config.model:
        provider_client = OpenAICompatibleClient(
            config=provider_config,
            timeout=settings.request_timeout_seconds,
        )
        patient_agent = PatientAgent(provider_client)
        evaluator_agent = EvaluatorAgent(
            provider_client,
            model=provider_config.model,
        )

        application.state.patient_agent = patient_agent
        application.state.interaction_service = InteractionService(
            database_manager,
            patient_agent,
            request_timeout_seconds=settings.request_timeout_seconds,
        )
        memory_worker = MemoryExtractionWorker(
            database_manager,
            application.state.memory_service,
            MemoryExtractionAgent(provider_client),
            request_timeout_seconds=settings.request_timeout_seconds,
        )
        application.state.memory_extraction_worker = memory_worker
        memory_worker_task = asyncio.create_task(
            memory_worker.run_forever(),
            name="therasim-memory-extraction",
        )

    application.state.evaluation_service = EvaluationService(
        database_manager,
        evaluator_agent,
    )
    application.state.run_analytics_service = RunAnalyticsService(
        database_manager,
        application.state.evaluation_service,
    )

    try:
        yield
    finally:
        if memory_worker_task is not None:
            application.state.memory_extraction_worker.request_stop()
            await memory_worker_task
        application.state.memory_extraction_worker = None
        application.state.memory_extraction_status_service = None
        application.state.interaction_request_status_service = None
        application.state.interaction_service = None
        application.state.memory_service = None
        application.state.event_review_service = None
        application.state.treatment_plan_service = None
        application.state.case_service = None
        application.state.run_service = None
        application.state.session_service = None
        application.state.evaluation_service = None
        application.state.run_analytics_service = None
        application.state.patient_agent = None
        application.state.database_manager = None
        application.state.database_migrations = None
        application.state.local_auth_service = None


app = FastAPI(
    title=settings.app_name,
    description=(
        "Local-first backend for the TheraSim psychotherapy "
        "skills simulation and evaluation framework."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
protected = [Depends(get_current_user)]
app.include_router(cases_router, dependencies=protected)
app.include_router(runs_router, dependencies=protected)
app.include_router(sessions_router, dependencies=protected)
from app.api.routes.evaluations import router as evaluations_router
app.include_router(evaluations_router, dependencies=protected)
app.include_router(llm_router, dependencies=protected)
app.include_router(interactions_router, dependencies=protected)
from app.api.routes.interaction_requests import router as interaction_requests_router
app.include_router(interaction_requests_router, dependencies=protected)
app.include_router(memories_router, dependencies=protected)
app.include_router(events_router, dependencies=protected)
app.include_router(treatment_plans_router, dependencies=protected)
app.include_router(analytics_router, dependencies=protected)
