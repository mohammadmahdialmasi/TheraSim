"""Tests for honest evaluator availability and rubric identifiers."""

import json
import re
import hashlib
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes.evaluations import (
    _evaluation_response,
    create_run_evaluation,
    create_session_evaluation,
)
from app.core.config import ProviderConfig
from app.llm.evaluator_agent import DEFAULT_RUBRIC_JSON_PATH, EvaluatorAgent
from app.persistence.database import DatabaseManager
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.restricted_cases import RestrictedCaseRepository
from app.services.cases import CaseService
from app.services.evaluations import (
    LONGITUDINAL_COMPETENCIES,
    SESSION_COMPETENCIES,
    EvaluationGenerationError,
    EvaluationRunError,
    EvaluationService,
    EvaluationUnavailableError,
)
from app.services.runs import RunService
from app.services.sessions import SessionService

NOW = "2026-11-16T12:00:00Z"


def make_manager(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "evaluation-service-tests")
    manager.initialize()
    return manager


def seed_case(manager):
    CaseService(manager).create_case(
        case_id="case-1",
        case_code="CASE-1",
        display_name="Synthetic Case 1",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    CaseService(manager).create_case_version(
        case_version_id="version-1",
        case_id="case-1",
        version_number="1.0",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )
    with manager.transaction("restricted") as connection:
        RestrictedCaseRepository(connection).create_profile(
            restricted_profile_id="profile-1",
            case_id="case-1",
            case_version_id="version-1",
            clinical_formulation={"type": "synthetic"},
            created_at=NOW,
        )


def test_session_evaluation_is_unavailable_without_an_evaluator_agent(tmp_path):
    manager = make_manager(tmp_path)
    seed_case(manager)

    run_service = RunService(manager)
    run = run_service.create_run(
        run_id="run-1",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    run_service.start_run("run-1", started_at=NOW)

    session_service = SessionService(manager)
    session_service.create_next_session(
        session_id="session-1",
        run_id="run-1",
        created_at=NOW,
        started_at=NOW,
    )

    with manager.transaction("operational") as connection:
        MessageRepository(connection).create_message(
            message_id="message-session-1",
            session_id="session-1",
            sequence_number=1,
            role="patient",
            content="I feel tense and unsure whether I can trust the process.",
            created_at=NOW,
        )
        SessionRepository(connection).update_status(
            "session-1",
            "completed",
            ended_at=NOW,
        )

    service = EvaluationService(manager)
    with pytest.raises(EvaluationUnavailableError):
        service.generate_session_evaluation(session_id="session-1")

    with manager.connection("operational") as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0

    with pytest.raises(HTTPException) as error:
        create_session_evaluation("session-1", service=service)
    assert error.value.status_code == 503
    assert error.value.detail == "evaluator_unavailable_experimental"


def test_run_evaluation_is_unavailable_without_an_evaluator_agent(tmp_path):
    manager = make_manager(tmp_path)
    seed_case(manager)

    run_service = RunService(manager)
    run_service.create_run(
        run_id="run-2",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    run_service.start_run("run-2", started_at=NOW)

    session_service = SessionService(manager)
    for session_id in ("session-2", "session-3"):
        session_service.create_next_session(
            session_id=session_id,
            run_id="run-2",
            created_at=NOW,
            started_at=NOW,
        )
        with manager.transaction("operational") as connection:
            MessageRepository(connection).create_message(
                message_id=f"message-{session_id}",
                session_id=session_id,
                sequence_number=1,
                role="patient",
                content=f"Session content for {session_id} falls within the completed run scope.",
                created_at=NOW,
            )
            MessageRepository(connection).create_message(
                message_id=f"therapist-{session_id}",
                session_id=session_id,
                sequence_number=2,
                role="therapist",
                content="What did you notice as the session progressed?",
                created_at=NOW,
            )
            SessionRepository(connection).update_status(
                session_id,
                "completed",
                ended_at=NOW,
            )

    service = EvaluationService(manager)
    with pytest.raises(EvaluationUnavailableError):
        service.generate_run_evaluation(run_id="run-2")

    with pytest.raises(HTTPException) as error:
        create_run_evaluation("run-2", service=service)
    assert error.value.status_code == 503
    assert error.value.detail == "evaluator_unavailable_experimental"

    with manager.connection("operational") as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0


def test_run_evaluation_does_not_create_results_for_incomplete_runs(tmp_path):
    manager = make_manager(tmp_path)
    seed_case(manager)

    run_service = RunService(manager)
    run_service.create_run(
        run_id="run-3",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )
    run_service.start_run("run-3", started_at=NOW)

    SessionService(manager).create_next_session(
        session_id="session-4",
        run_id="run-3",
        created_at=NOW,
        started_at=NOW,
    )

    service = EvaluationService(manager)

    with pytest.raises(EvaluationRunError, match="two completed sessions"):
        service.generate_run_evaluation(run_id="run-3")

    with manager.connection("operational") as connection:
        assert connection.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 0


def test_competency_ids_match_the_versioned_act_rubrics():
    repository_root = Path(__file__).resolve().parents[2]
    competency_pattern = re.compile(r"\*\*Competency ID:\*\*\s+([a-z0-9_]+)")
    session_rubric = (
        repository_root / "rubrics" / "act" / "ACT_RUBRIC_V0.md"
    ).read_text(encoding="utf-8")
    longitudinal_rubric = (
        repository_root
        / "rubrics"
        / "act"
        / "ACT_LONGITUDINAL_RUBRIC_V0_2.md"
    ).read_text(encoding="utf-8")

    assert tuple(competency_pattern.findall(session_rubric)) == SESSION_COMPETENCIES
    assert (
        tuple(competency_pattern.findall(longitudinal_rubric))
        == LONGITUDINAL_COMPETENCIES
    )


def test_historical_placeholder_evaluations_are_read_as_experimental():
    response = _evaluation_response(
        {
            "evaluation_id": "legacy-evaluation",
            "run_id": "legacy-run",
            "session_id": "legacy-session",
            "evaluation_scope": "session",
            "rubric_id": "ACT_RUBRIC_V0",
            "rubric_version": "0.2",
            "status": "completed",
            "created_at": NOW,
            "overall_summary": "Placeholder summary",
            "evaluator_model_run_id": None,
        },
        service=None,
    )

    assert response.status == "experimental"
    assert response.items == []
    assert "withheld" in response.overall_summary


class FakeEvaluatorClient:
    config = ProviderConfig(
        name="ollama",
        base_url="http://127.0.0.1:11434/v1",
        model="evaluator-test-model",
        api_key="",
    )

    def __init__(self, *, forged_quote=False):
        self.forged_quote = forged_quote

    def chat(self, *, model, messages, temperature, max_tokens):
        evaluator_input = json.loads(messages[1]["content"])
        rubric = evaluator_input["rubric_definition"]
        transcript = evaluator_input["transcript"]
        is_longitudinal = rubric["scope"] == "longitudinal"
        scored_competency = (
            rubric["competency_ids"][0]
            if is_longitudinal
            else "functional_assessment"
        )
        evidence_messages = []
        seen_sessions = set()
        for message in transcript:
            if message["role"] != "therapist":
                continue
            session_id = message.get("session_id")
            if is_longitudinal:
                if session_id in seen_sessions:
                    continue
                seen_sessions.add(session_id)
            evidence_messages.append(message)
        competencies = []
        for competency_id in rubric["competency_ids"]:
            is_scored = competency_id == scored_competency
            evidence = [
                {
                    "message_id": message["message_id"],
                    "excerpt": (
                        "invented therapist quote"
                        if self.forged_quote
                        else message["content"]
                    ),
                    "evidence_role": "supports",
                    "evidence_note": "The therapist explored the situation.",
                }
                for message in (
                    evidence_messages[:2]
                    if is_longitudinal
                    else evidence_messages[:1]
                )
            ] if is_scored else []
            competencies.append({
                "competency_id": competency_id,
                "rating_code": "2" if is_scored else "NE",
                "explanation": (
                    "The therapist explored the situation."
                    if is_scored
                    else "The transcript does not provide enough evidence."
                ),
                "strengths": ["Asked about the context."] if is_scored else [],
                "limitations": [],
                "missing_evidence": (
                    [] if is_scored else ["No relevant opportunity was observed."]
                ),
                "confidence": "medium" if is_scored else "low",
                "uncertainty_notes": "",
                "alternative_response": None,
                "evidence": evidence,
            })
        return {
            "content": json.dumps({
                "overall_summary": (
                    "Experimental, transcript-grounded formative feedback."
                ),
                "competencies": competencies,
            }),
            "model": model,
            "finish_reason": "stop",
        }


def seed_completed_evaluation_session(
    manager,
    *,
    run_id,
    session_id,
    patient_message_id="patient-eval",
    therapist_message_id="therapist-eval",
):
    if RunService(manager).get_run(run_id) is None:
        seed_case(manager)
        run_service = RunService(manager)
        run_service.create_run(
            run_id=run_id,
            case_id="case-1",
            case_version_id="version-1",
            configuration_version="0.1",
            created_at=NOW,
        )
        run_service.start_run(run_id, started_at=NOW)
    SessionService(manager).create_next_session(
        session_id=session_id,
        run_id=run_id,
        created_at=NOW,
        started_at=NOW,
    )
    with manager.transaction("operational") as connection:
        messages = MessageRepository(connection)
        messages.create_message(
            message_id=patient_message_id,
            session_id=session_id,
            sequence_number=1,
            role="patient",
            content="I avoid speaking during meetings.",
            created_at=NOW,
        )
        messages.create_message(
            message_id=therapist_message_id,
            session_id=session_id,
            sequence_number=2,
            role="therapist",
            content="Could we explore what happens before the meeting?",
            created_at=NOW,
        )
    SessionService(manager).complete_session(
        session_id,
        completed_at=NOW,
    )


def test_session_evaluator_persists_revision_manifest_and_exact_evidence(tmp_path):
    manager = make_manager(tmp_path)
    seed_completed_evaluation_session(
        manager,
        run_id="run-evaluator",
        session_id="session-evaluator",
    )
    agent = EvaluatorAgent(
        FakeEvaluatorClient(),
        model="evaluator-test-model",
    )
    service = EvaluationService(manager, agent)

    record = service.generate_session_evaluation(
        session_id="session-evaluator",
    )

    assert record["status"] == "requires_review"
    assert record["evaluation_revision"] == 1
    assert record["rubric_id"] == "ACT_RUBRIC_V0"
    assert record["rubric_version"] == "0.2"
    assert record["evaluator_model_run_id"].startswith("model-run-evaluator-")

    items = service.list_items(evaluation_id=record["evaluation_id"])
    assert len(items) == len(SESSION_COMPETENCIES)
    scored = next(
        item for item in items
        if item["competency_id"] == "functional_assessment"
    )
    assert scored["rating_code"] == "2"
    evidence = service.list_evidence_for_item(
        evaluation_item_id=scored["evaluation_item_id"],
    )
    assert len(evidence) == 1
    assert evidence[0]["message_id"] == "therapist-eval"
    assert evidence[0]["evidence_excerpt"] == (
        "Could we explore what happens before the meeting?"
    )
    assert evidence[0]["start_offset"] == 0

    manifest = json.loads(record["transcript_manifest"])
    assert [entry["message_id"] for entry in manifest] == [
        "patient-eval",
        "therapist-eval",
    ]
    metadata = json.loads(record["report_metadata"])
    assert metadata["experimental"] is True
    assert metadata["human_review_required"] is True
    assert metadata["evaluator_model"] == "evaluator-test-model"
    rubric_contract = DEFAULT_RUBRIC_JSON_PATH.read_text(encoding="utf-8")
    rubric_document = DEFAULT_RUBRIC_JSON_PATH.with_name(
        "ACT_RUBRIC_V0.md"
    ).read_text(encoding="utf-8")
    expected_rubric_hash = hashlib.sha256(
        (rubric_contract + "\n" + rubric_document).encode("utf-8")
    ).hexdigest()
    assert metadata["rubric_content_sha256"] == expected_rubric_hash

    with manager.connection("operational") as connection:
        model_run = connection.execute(
            "SELECT execution_status, output_validation_status "
            "FROM model_runs WHERE model_run_id = ?",
            (record["evaluator_model_run_id"],),
        ).fetchone()
    assert tuple(model_run) == ("completed", "valid")


def test_session_evaluator_rejects_fabricated_quote_without_saving_report(tmp_path):
    manager = make_manager(tmp_path)
    seed_completed_evaluation_session(
        manager,
        run_id="run-fabricated",
        session_id="session-fabricated",
    )
    service = EvaluationService(
        manager,
        EvaluatorAgent(
            FakeEvaluatorClient(forged_quote=True),
            model="evaluator-test-model",
        ),
    )

    with pytest.raises(EvaluationGenerationError, match="validated report"):
        service.generate_session_evaluation(session_id="session-fabricated")

    with manager.connection("operational") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM evaluations"
        ).fetchone()[0] == 0
        model_run = connection.execute(
            "SELECT execution_status FROM model_runs "
            "WHERE component = 'evaluator_agent'"
        ).fetchone()
    assert model_run["execution_status"] == "failed"


def test_each_new_session_evaluation_is_a_new_revision(tmp_path):
    manager = make_manager(tmp_path)
    seed_completed_evaluation_session(
        manager,
        run_id="run-revisions",
        session_id="session-revisions",
    )
    service = EvaluationService(
        manager,
        EvaluatorAgent(
            FakeEvaluatorClient(),
            model="evaluator-test-model",
        ),
    )

    first = service.generate_session_evaluation(session_id="session-revisions")
    second = service.generate_session_evaluation(session_id="session-revisions")

    assert first["evaluation_revision"] == 1
    assert second["evaluation_revision"] == 2
    assert first["evaluation_id"] != second["evaluation_id"]


def test_session_evaluation_route_returns_reviewable_report(tmp_path):
    manager = make_manager(tmp_path)
    seed_completed_evaluation_session(
        manager,
        run_id="run-api-evaluator",
        session_id="session-api-evaluator",
    )
    service = EvaluationService(
        manager,
        EvaluatorAgent(
            FakeEvaluatorClient(),
            model="evaluator-test-model",
        ),
    )

    response = create_session_evaluation(
        "session-api-evaluator",
        service=service,
    )

    assert response.data.status == "requires_review"
    assert response.data.experimental is True
    assert response.data.human_review_required is True
    assert response.data.evaluator_model == "evaluator-test-model"
    item = next(
        item
        for item in response.data.items
        if item.competency_id == "functional_assessment"
    )
    assert item.confidence == "medium"
    assert item.strengths == ["Asked about the context."]


def test_longitudinal_evaluator_uses_multiple_sessions_and_detects_staleness(
    tmp_path,
):
    manager = make_manager(tmp_path)
    seed_completed_evaluation_session(
        manager,
        run_id="run-longitudinal",
        session_id="session-longitudinal-1",
        patient_message_id="patient-longitudinal-1",
        therapist_message_id="therapist-longitudinal-1",
    )
    seed_completed_evaluation_session(
        manager,
        run_id="run-longitudinal",
        session_id="session-longitudinal-2",
        patient_message_id="patient-longitudinal-2",
        therapist_message_id="therapist-longitudinal-2",
    )
    service = EvaluationService(
        manager,
        EvaluatorAgent(
            FakeEvaluatorClient(),
            model="evaluator-test-model",
        ),
    )

    response = create_run_evaluation(
        "run-longitudinal",
        service=service,
    )

    assert response.data.evaluation_scope == "longitudinal"
    assert response.data.status == "requires_review"
    assert response.data.stale is False
    assert response.data.rubric_id == "ACT_LONGITUDINAL_RUBRIC_V0"
    assert [
        session.session_id for session in response.data.session_scope
    ] == ["session-longitudinal-1", "session-longitudinal-2"]
    assert len(response.data.items) == len(LONGITUDINAL_COMPETENCIES)
    scored = next(
        item
        for item in response.data.items
        if item.competency_id == LONGITUDINAL_COMPETENCIES[0]
    )
    assert scored.rating_code == "2"
    assert {
        evidence.message_id
        for evidence in scored.evidence
    } == {
        "therapist-longitudinal-1",
        "therapist-longitudinal-2",
    }
    assert {
        evidence.session_number for evidence in scored.evidence
    } == {1, 2}
    assert all(
        evidence.source_message_content
        == "Could we explore what happens before the meeting?"
        for evidence in scored.evidence
    )

    with manager.connection("operational") as connection:
        stored = connection.execute(
            "SELECT report_metadata, transcript_manifest FROM evaluations "
            "WHERE evaluation_id = ?",
            (response.data.evaluation_id,),
        ).fetchone()
    metadata = json.loads(stored["report_metadata"])
    assert [
        item["session_id"]
        for item in metadata["longitudinal_session_scope"]
    ] == ["session-longitudinal-1", "session-longitudinal-2"]
    assert len(metadata["run_sessions_snapshot"]) == 2
    assert metadata["evaluator_prompt_id"] == "ACT_LONGITUDINAL_EVALUATOR_V0"
    manifest = json.loads(stored["transcript_manifest"])
    assert {item["session_id"] for item in manifest} == {
        "session-longitudinal-1",
        "session-longitudinal-2",
    }

    SessionService(manager).create_next_session(
        session_id="session-longitudinal-3",
        run_id="run-longitudinal",
        created_at=NOW,
        started_at=NOW,
    )
    assert service.get_evaluation(
        evaluation_id=response.data.evaluation_id
    )["stale"] is True
    assert service.list_run_evaluations(
        run_id="run-longitudinal"
    )[0]["stale"] is True


def test_longitudinal_report_is_current_with_preexisting_active_session(tmp_path):
    manager = make_manager(tmp_path)
    seed_completed_evaluation_session(
        manager,
        run_id="run-longitudinal-active",
        session_id="session-longitudinal-active-1",
        patient_message_id="patient-longitudinal-active-1",
        therapist_message_id="therapist-longitudinal-active-1",
    )
    seed_completed_evaluation_session(
        manager,
        run_id="run-longitudinal-active",
        session_id="session-longitudinal-active-2",
        patient_message_id="patient-longitudinal-active-2",
        therapist_message_id="therapist-longitudinal-active-2",
    )
    SessionService(manager).create_next_session(
        session_id="session-longitudinal-active-3",
        run_id="run-longitudinal-active",
        created_at=NOW,
        started_at=NOW,
    )
    service = EvaluationService(
        manager,
        EvaluatorAgent(
            FakeEvaluatorClient(),
            model="evaluator-test-model",
        ),
    )

    report = service.generate_run_evaluation(
        run_id="run-longitudinal-active"
    )

    assert report["stale"] is False
