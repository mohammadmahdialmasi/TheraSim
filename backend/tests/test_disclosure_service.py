import json

import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import AuditRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.services.cases import CaseService
from app.services.runs import RunService
from app.services.disclosures import (
    DisclosureEvidenceError,
    DisclosureNotFoundError,
    DisclosureOperationConflictError,
    DisclosurePolicyViolationError,
    DisclosureRecord,
    DisclosureRunNotFoundError,
    DisclosureService,
    DisclosureTransitionError,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def system(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "disclosure-service-tests")
    manager.initialize()

    cases = CaseService(manager)

    cases.create_case(
        case_id="case-1",
        case_code="CASE-001",
        display_name="Synthetic Case",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )

    cases.create_case_version(
        case_version_id="version-1",
        case_id="case-1",
        version_number="1.0",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )

    with manager.transaction("restricted") as connection:
        repository = RestrictedCaseRepository(connection)

        repository.create_profile(
            restricted_profile_id="profile-1",
            case_id="case-1",
            case_version_id="version-1",
            clinical_formulation={"synthetic": True},
            created_at=NOW,
        )

        facts = [
            (
                "FACT-INITIAL",
                "established_fact",
                "initial_disclosure",
            ),
            (
                "FACT-CONTEXT",
                "established_fact",
                "contextually_disclosable",
            ),
            (
                "FACT-HYPOTHESIS",
                "case_hypothesis",
                "contextually_disclosable",
            ),
            (
                "FACT-RESTRICTED",
                "established_fact",
                "restricted",
            ),
            (
                "FACT-NA",
                "established_fact",
                "not_applicable",
            ),
        ]

        for fact_id, information_class, policy in facts:
            repository.create_fact(
                case_id="case-1",
                case_version_id="version-1",
                case_fact_id=fact_id,
                fact_category="test_category",
                information_class=information_class,
                content=f"RESTRICTED CONTENT FOR {fact_id}",
                disclosure_policy=policy,
                created_at=NOW,
            )

    runs = RunService(manager)

    runs.create_run(
        run_id="run-1",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )

    runs.start_run("run-1", started_at=NOW)

    with manager.transaction("operational") as connection:
        SessionRepository(connection).create_session(
            session_id="session-1",
            run_id="run-1",
            session_number=1,
            status="active",
            created_at=NOW,
            started_at=NOW,
        )

        messages = MessageRepository(connection)

        messages.create_message(
            message_id="patient-1",
            session_id="session-1",
            sequence_number=1,
            role="patient",
            content="I received feedback after the meeting.",
            created_at=NOW,
        )

        messages.create_message(
            message_id="therapist-1",
            session_id="session-1",
            sequence_number=2,
            role="therapist",
            content="Can you tell me more?",
            created_at=NOW,
        )

    return {
        "manager": manager,
        "service": DisclosureService(manager),
    }


def initialized(system):
    return system["service"].initialize_run_disclosures(
        "run-1",
        created_at=NOW,
    )


def mark_candidate(
    system,
    fact_id="FACT-CONTEXT",
    operation_id="candidate-1",
):
    return system["service"].mark_candidate_disclosed(
        "run-1",
        fact_id,
        operation_id=operation_id,
        occurred_at="2026-11-16T12:01:00Z",
        source_message_id="patient-1",
        evidence_start_offset=0,
        evidence_end_offset=2,
        evidence_description="Patient transcript evidence.",
    )


def test_initialize_creates_one_disclosure_per_case_fact(system):
    records = initialized(system)

    assert len(records) == 5
    assert all(isinstance(item, DisclosureRecord) for item in records)
    assert all(item.disclosure_status == "not_disclosed" for item in records)

    assert {
        item.case_fact_id for item in records
    } == {
        "FACT-INITIAL",
        "FACT-CONTEXT",
        "FACT-HYPOTHESIS",
        "FACT-RESTRICTED",
        "FACT-NA",
    }


def test_initialization_is_idempotent(system):
    first = initialized(system)
    second = initialized(system)

    assert len(first) == 5
    assert len(second) == 5

    assert {
        item.disclosure_id for item in first
    } == {
        item.disclosure_id for item in second
    }

    with system["manager"].connection("operational") as connection:
        disclosure_count = connection.execute(
            "SELECT COUNT(*) FROM case_fact_disclosures"
        ).fetchone()[0]

        history_count = connection.execute(
            "SELECT COUNT(*) FROM case_fact_disclosure_history"
        ).fetchone()[0]

        audit_count = connection.execute(
            """
            SELECT COUNT(*) FROM audit_events
            WHERE operation_type = 'run_disclosures_initialized'
            """
        ).fetchone()[0]

    assert disclosure_count == 5
    assert history_count == 5
    assert audit_count == 1


def test_candidate_disclosure_uses_patient_evidence(system):
    initialized(system)

    result = mark_candidate(system)

    assert result.disclosure_status == "candidate_disclosed"
    assert result.source_message_id == "patient-1"
    assert result.evidence_start_offset == 0
    assert result.evidence_end_offset == 2
    assert result.validation_method == "patient_annotation"
    assert result.disclosure_policy == "contextually_disclosable"


def test_restricted_fact_cannot_be_candidate_disclosed(system):
    initialized(system)

    with pytest.raises(DisclosurePolicyViolationError):
        mark_candidate(
            system,
            fact_id="FACT-RESTRICTED",
        )


def test_not_applicable_fact_cannot_be_candidate_disclosed(system):
    initialized(system)

    with pytest.raises(DisclosurePolicyViolationError):
        mark_candidate(
            system,
            fact_id="FACT-NA",
        )


def test_confirmation_requires_candidate_or_review_status(system):
    initialized(system)

    with pytest.raises(DisclosureTransitionError):
        system["service"].confirm_disclosure(
            "run-1",
            "FACT-INITIAL",
            operation_id="confirm-too-early",
            confirmed_at=NOW,
            source_message_id="patient-1",
            evidence_start_offset=0,
            evidence_end_offset=2,
        )


def test_established_fact_can_be_confirmed_after_manual_review(system):
    initialized(system)
    mark_candidate(
        system,
        fact_id="FACT-INITIAL",
        operation_id="candidate-initial",
    )

    confirmed = system["service"].confirm_disclosure(
        "run-1",
        "FACT-INITIAL",
        operation_id="manual-confirm-1",
        confirmed_at="2026-11-16T12:02:00Z",
        source_message_id="patient-1",
        evidence_start_offset=0,
        evidence_end_offset=2,
        evidence_description="Reviewed patient statement.",
    )

    assert confirmed.disclosure_status == "confirmed_disclosed"
    assert confirmed.validation_method == "manual_review"
    assert confirmed.information_class == "established_fact"


def test_case_hypothesis_cannot_become_confirmed_fact(system):
    initialized(system)

    mark_candidate(
        system,
        fact_id="FACT-HYPOTHESIS",
        operation_id="candidate-hypothesis",
    )

    with pytest.raises(DisclosurePolicyViolationError):
        system["service"].confirm_disclosure(
            "run-1",
            "FACT-HYPOTHESIS",
            operation_id="confirm-hypothesis",
            confirmed_at=NOW,
            source_message_id="patient-1",
            evidence_start_offset=0,
            evidence_end_offset=2,
        )


def test_restricted_fact_can_be_flagged_for_review(system):
    initialized(system)

    result = system["service"].flag_for_review(
        "run-1",
        "FACT-RESTRICTED",
        operation_id="review-restricted",
        occurred_at=NOW,
        source_message_id="patient-1",
        evidence_start_offset=0,
        evidence_end_offset=2,
        review_reason="Potential restricted disclosure.",
    )

    assert result.disclosure_status == "requires_review"
    assert result.validation_method == "review_required"
    assert result.validation_notes == "Potential restricted disclosure."


def test_evidence_span_must_be_non_empty(system):
    initialized(system)

    with pytest.raises(DisclosureEvidenceError):
        system["service"].mark_candidate_disclosed(
            "run-1",
            "FACT-CONTEXT",
            operation_id="empty-span",
            occurred_at=NOW,
            source_message_id="patient-1",
            evidence_start_offset=5,
            evidence_end_offset=5,
        )


def test_evidence_must_reference_patient_message(system):
    initialized(system)

    with pytest.raises(DisclosureEvidenceError):
        system["service"].mark_candidate_disclosed(
            "run-1",
            "FACT-CONTEXT",
            operation_id="therapist-source",
            occurred_at=NOW,
            source_message_id="therapist-1",
            evidence_start_offset=0,
            evidence_end_offset=5,
        )


def test_evidence_offsets_cannot_exceed_message_length(system):
    initialized(system)

    with pytest.raises(DisclosureEvidenceError):
        system["service"].mark_candidate_disclosed(
            "run-1",
            "FACT-CONTEXT",
            operation_id="invalid-offsets",
            occurred_at=NOW,
            source_message_id="patient-1",
            evidence_start_offset=0,
            evidence_end_offset=10000,
        )


def test_operation_identifier_cannot_be_reused_for_different_change(system):
    initialized(system)

    mark_candidate(
        system,
        operation_id="shared-operation",
    )

    with pytest.raises(DisclosureOperationConflictError):
        system["service"].flag_for_review(
            "run-1",
            "FACT-CONTEXT",
            operation_id="shared-operation",
            occurred_at=NOW,
            source_message_id="patient-1",
            evidence_start_offset=0,
            evidence_end_offset=2,
            review_reason="Conflicting operation.",
        )


def test_get_and_list_disclosures_do_not_expose_fact_content(system):
    initialized(system)

    one = system["service"].get_disclosure(
        "run-1",
        "FACT-INITIAL",
    )

    all_records = system["service"].list_disclosures("run-1")

    assert one is not None
    assert len(all_records) == 5

    assert not hasattr(one, "content")
    assert not hasattr(one, "relevance_metadata")

    assert "RESTRICTED CONTENT" not in repr(one)


def test_missing_disclosure_returns_none(system):
    initialized(system)

    assert system["service"].get_disclosure(
        "run-1",
        "DOES-NOT-EXIST",
    ) is None


def test_unknown_run_is_rejected(system):
    with pytest.raises(DisclosureRunNotFoundError):
        system["service"].initialize_run_disclosures(
            "missing-run",
            created_at=NOW,
        )


def test_disclosure_change_creates_audit_record(system):
    initialized(system)
    mark_candidate(system)

    with system["manager"].connection("operational") as connection:
        events = AuditRepository(connection).list_for_entity(
            "case_fact_disclosure",
            system["service"].get_disclosure(
                "run-1",
                "FACT-CONTEXT",
            ).disclosure_id,
        )

    assert len(events) == 1
    assert events[0]["operation_type"] == "disclosure_candidate_disclosed"

    metadata = json.loads(events[0]["metadata"])

    assert metadata["case_fact_id"] == "FACT-CONTEXT"
    assert metadata["new_status"] == "candidate_disclosed"
    assert "content" not in metadata
