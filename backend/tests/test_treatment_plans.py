import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.routes.runs import get_run_service
from app.api.routes.treatment_plans import get_treatment_plan_service
from app.main import app
from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.events import EventRepository
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.services.runs import RunService, SimulationRunRecord
from app.services.treatment_plans import (
    PlanEvidenceReference,
    PlanGoal,
    PlanIntervention,
    PlanObjective,
    TreatmentPlanConflictError,
    TreatmentPlanDefinition,
    TreatmentPlanEvidenceError,
    TreatmentPlanService,
)


NOW = "2026-11-17T08:00:00Z"


def plan_definition(description="Improve flexible responding"):
    return TreatmentPlanDefinition(
        initial_formulation="A preliminary, revisable educational formulation.",
        goals=[
            PlanGoal(
                goal_id="goal-flexibility",
                description=description,
                relevant_processes=["acceptance", "values"],
            )
        ],
        objectives=[
            PlanObjective(
                objective_id="objective-1",
                goal_id="goal-flexibility",
                description="Notice avoidance in a recent situation.",
                progress_indicator="Client-described example and response.",
            )
        ],
        interventions=[
            PlanIntervention(
                intervention_id="intervention-1",
                description="Explore the function of an avoidance response.",
                objective_ids=["objective-1"],
            )
        ],
        outcome_measures=[],
        review_after_session=2,
    )


@pytest.fixture
def plan_system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "treatment-plans")
    manager.initialize()
    with manager.transaction("operational") as connection:
        CaseRepository(connection).create_case(
            case_id="case-1",
            case_code="CASE-001",
            display_name="Ava",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
        CaseRepository(connection).create_case_version(
            case_version_id="version-1",
            case_id="case-1",
            version_number="1.0",
            modality="ACT",
            language="en",
            schema_version="0.2",
            created_at=NOW,
        )
        SimulationRunRepository(connection).create_run(
            run_id="run-1",
            case_id="case-1",
            case_version_id="version-1",
            modality="ACT",
            language="en",
            configuration_version="0.1",
            created_at=NOW,
            status="active",
        )
        EventRepository(connection).create_event(
            event_id="event-accepted",
            run_id="run-1",
            session_id=None,
            sequence_number=1,
            event_type="value_consistent_action",
            actor="patient",
            payload={"summary": "Client took a value-consistent action."},
            extraction_method="manual",
            event_status="accepted",
            idempotency_key="event-key-1",
            created_at=NOW,
        )
        EventRepository(connection).create_event(
            event_id="event-pending",
            run_id="run-1",
            session_id=None,
            sequence_number=2,
            event_type="setback",
            actor="patient",
            payload={"summary": "Pending event."},
            extraction_method="model_assisted",
            event_status="requires_review",
            idempotency_key="event-key-2",
            created_at=NOW,
        )
    run = SimulationRunRecord(
        run_id="run-1",
        case_id="case-1",
        case_version_id="version-1",
        modality="ACT",
        language="en",
        status="active",
        configuration_version="0.1",
        started_at=NOW,
        completed_at=None,
        created_at=NOW,
    )
    return {
        "manager": manager,
        "run": run,
        "service": TreatmentPlanService(manager),
        "run_service": RunService(manager),
    }


def create_initial(system):
    return system["service"].create_initial_plan(
        system["run"],
        definition=plan_definition(),
        created_at=NOW,
    )


def propose_revision(system, expected_revision_number=1, **kwargs):
    return system["service"].propose_revision(
        "run-1",
        expected_revision_number=expected_revision_number,
        definition=kwargs.get("definition", plan_definition()),
        evidence=kwargs.get(
            "evidence",
            (PlanEvidenceReference(kind="event", source_id="event-accepted"),),
        ),
        rationale=kwargs.get("rationale", "Reviewed longitudinal evidence."),
        created_at=NOW,
    )


def test_plan_revision_requires_review_and_preserves_history(plan_system):
    system = plan_system
    initial = create_initial(system)
    proposal = propose_revision(
        system,
        definition=plan_definition("Respond more flexibly to setbacks"),
    )

    assert initial.revision_number == 1
    assert initial.status == "active"
    assert proposal.revision_number == 2
    assert proposal.status == "requires_review"
    assert system["service"].get_current("run-1").revision_number == 1

    accepted, review = system["service"].review_revision(
        "run-1",
        proposal.revision_id,
        decision="accepted",
        reviewer_id="unverified_local_caller",
        rationale="The accepted event supports the revised goal.",
        reviewed_at=NOW,
    )

    revisions = system["service"].list_revisions("run-1")
    assert accepted.status == "active"
    assert review.decision == "accepted"
    assert [item.status for item in revisions] == ["superseded", "active"]
    assert revisions[0].definition.goals[0].description == (
        "Improve flexible responding"
    )
    assert revisions[1].evidence == (
        PlanEvidenceReference(kind="event", source_id="event-accepted"),
    )
    assert revisions[1].review is not None
    assert revisions[1].review.rationale == (
        "The accepted event supports the revised goal."
    )

    with system["manager"].transaction("operational") as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="treatment_plan_revision_immutable",
        ):
            connection.execute(
                "UPDATE treatment_plan_revisions SET plan_json = '{}' "
                "WHERE revision_id = ?",
                (proposal.revision_id,),
            )


def test_adaptation_guidance_uses_newly_accepted_evidence_only(plan_system):
    system = plan_system
    create_initial(system)

    unchanged = system["service"].get_adaptation_guidance("run-1")
    assert unchanged.status == "no_new_evidence"
    assert unchanged.evidence == ()

    with system["manager"].transaction("operational") as connection:
        EventRepository(connection).create_event(
            event_id="event-setback-new",
            run_id="run-1",
            session_id=None,
            sequence_number=3,
            event_type="setback",
            actor="patient",
            payload={"summary": "Client described renewed avoidance."},
            extraction_method="manual",
            event_status="accepted",
            idempotency_key="event-key-setback-new",
            created_at="2026-11-18T08:00:00Z",
        )
        EventRepository(connection).create_event(
            event_id="event-unreviewed-new",
            run_id="run-1",
            session_id=None,
            sequence_number=4,
            event_type="value_consistent_action",
            actor="patient",
            payload={"summary": "Pending progress event."},
            extraction_method="model_assisted",
            event_status="requires_review",
            idempotency_key="event-key-unreviewed-new",
            created_at="2026-11-18T08:01:00Z",
        )

    guidance = system["service"].get_adaptation_guidance("run-1")
    assert guidance.status == "actionable"
    assert guidance.recommendation == "review_objectives_and_interventions"
    assert [item.event_id for item in guidance.evidence] == [
        "event-setback-new"
    ]
    assert guidance.evidence[0].summary == "Client described renewed avoidance."


def test_adaptation_guidance_does_not_infer_when_sessions_lack_events(
    plan_system,
):
    from app.persistence.repositories.sessions import SessionRepository

    create_initial(plan_system)
    with plan_system["manager"].transaction("operational") as connection:
        sessions = SessionRepository(connection)
        sessions.create_session(
            session_id="session-after-plan",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at="2026-11-18T08:00:00Z",
            started_at="2026-11-18T08:00:00Z",
        )
        sessions.update_status(
            "session-after-plan",
            "completed",
            ended_at="2026-11-18T09:00:00Z",
        )

    guidance = plan_system["service"].get_adaptation_guidance("run-1")
    assert guidance.status == "insufficient_evidence"
    assert guidance.recommendation == "human_review"
    assert guidance.evidence == ()


def test_rejected_plan_proposal_does_not_change_active_plan(plan_system):
    system = plan_system
    initial = create_initial(system)
    proposal = propose_revision(system)

    rejected, review = system["service"].review_revision(
        "run-1",
        proposal.revision_id,
        decision="rejected",
        reviewer_id="unverified_local_caller",
        rationale="The proposed revision is not supported.",
        reviewed_at=NOW,
    )

    assert rejected.status == "rejected"
    assert review.decision == "rejected"
    assert system["service"].get_current("run-1").revision_id == (
        initial.revision_id
    )


def test_new_revision_can_follow_rejection_without_losing_history(plan_system):
    system = plan_system
    initial = create_initial(system)
    rejected = propose_revision(system)
    system["service"].review_revision(
        "run-1",
        rejected.revision_id,
        decision="rejected",
        reviewer_id="unverified_local_caller",
        rationale="Reject this proposal.",
        reviewed_at=NOW,
    )

    next_proposal = propose_revision(
        system,
        expected_revision_number=initial.revision_number,
        definition=plan_definition("A different revision after review"),
    )
    assert next_proposal.revision_number == 3
    assert next_proposal.based_on_revision_number == 1
    system["service"].review_revision(
        "run-1",
        next_proposal.revision_id,
        decision="accepted",
        reviewer_id="unverified_local_caller",
        rationale="Accept the subsequent proposal.",
        reviewed_at=NOW,
    )

    revisions = system["service"].list_revisions("run-1")
    assert [item.status for item in revisions] == [
        "superseded",
        "rejected",
        "active",
    ]


def test_plan_proposal_rejects_unreviewed_or_cross_run_evidence(plan_system):
    system = plan_system
    create_initial(system)

    with pytest.raises(TreatmentPlanEvidenceError, match="Only accepted events"):
        propose_revision(
            system,
            evidence=(
                PlanEvidenceReference(kind="event", source_id="event-pending"),
            ),
        )

    with pytest.raises(TreatmentPlanEvidenceError, match="same Run"):
        propose_revision(
            system,
            evidence=(
                PlanEvidenceReference(kind="event", source_id="missing-event"),
            ),
        )


def test_stale_plan_proposal_and_second_pending_proposal_are_rejected(
    plan_system,
):
    system = plan_system
    create_initial(system)
    first = propose_revision(system)

    with pytest.raises(TreatmentPlanConflictError, match="stale plan"):
        propose_revision(system, expected_revision_number=9)
    with pytest.raises(TreatmentPlanConflictError, match="already awaiting"):
        propose_revision(system)

    system["service"].review_revision(
        "run-1",
        first.revision_id,
        decision="accepted",
        reviewer_id="unverified_local_caller",
        rationale="Approve the first pending revision.",
        reviewed_at=NOW,
    )
    with pytest.raises(TreatmentPlanConflictError, match="stale plan"):
        propose_revision(system)


def test_treatment_plan_api_supports_reviewed_version_progression(plan_system):
    system = plan_system
    app.dependency_overrides[get_treatment_plan_service] = (
        lambda: system["service"]
    )
    app.dependency_overrides[get_run_service] = (
        lambda: system["run_service"]
    )
    client = TestClient(app)
    try:
        initial = client.post(
            "/api/v1/simulation-runs/run-1/treatment-plan",
            json={
                "definition": plan_definition().model_dump(mode="json"),
                "rationale": "Initial formulation for this educational run.",
            },
        )
        assert initial.status_code == 201
        proposal = client.post(
            "/api/v1/simulation-runs/run-1/treatment-plan/revisions",
            json={
                "expected_revision_number": 1,
                "definition": plan_definition(
                    "Respond flexibly to setbacks"
                ).model_dump(mode="json"),
                "evidence": [
                    {"kind": "event", "source_id": "event-accepted"}
                ],
                "rationale": "The reviewed event supports a revision.",
            },
        )
        assert proposal.status_code == 201
        revision_id = proposal.json()["data"]["revision_id"]
        reviewed = client.post(
            f"/api/v1/simulation-runs/run-1/treatment-plan/revisions/{revision_id}/review",
            json={
                "decision": "accepted",
                "rationale": "Approve the evidence-linked revision.",
            },
        )
        assert reviewed.status_code == 200
        current = client.get(
            "/api/v1/simulation-runs/run-1/treatment-plan"
        )
    finally:
        client.close()
        app.dependency_overrides.pop(get_treatment_plan_service, None)
        app.dependency_overrides.pop(get_run_service, None)

    assert current.status_code == 200
    assert current.json()["current"]["revision_number"] == 2
    assert [
        item["status"] for item in current.json()["revisions"]
    ] == ["superseded", "active"]


def test_treatment_plan_api_exposes_review_gated_adaptation_guidance(
    plan_system,
):
    system = plan_system
    create_initial(system)
    with system["manager"].transaction("operational") as connection:
        EventRepository(connection).create_event(
            event_id="event-contradiction-new",
            run_id="run-1",
            session_id=None,
            sequence_number=3,
            event_type="contradiction",
            actor="patient",
            payload={"summary": "Client gave a conflicting account."},
            extraction_method="manual",
            event_status="accepted",
            idempotency_key="event-key-contradiction-new",
            created_at="2026-11-18T08:00:00Z",
        )

    app.dependency_overrides[get_treatment_plan_service] = (
        lambda: system["service"]
    )
    app.dependency_overrides[get_run_service] = (
        lambda: system["run_service"]
    )
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/simulation-runs/run-1/treatment-plan/adaptation-guidance"
        )
    finally:
        client.close()
        app.dependency_overrides.pop(get_treatment_plan_service, None)
        app.dependency_overrides.pop(get_run_service, None)

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "actionable"
    assert (
        response.json()["data"]["recommendation"] == "review_formulation"
    )
    assert response.json()["data"]["evidence"][0]["event_id"] == (
        "event-contradiction-new"
    )
