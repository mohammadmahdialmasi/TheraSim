"""Evaluation availability and read access for TheraSim reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid
from typing import NoReturn

from app.core.paths import project_root
from app.llm.client import ProviderConnectionError
from app.llm.evaluator_agent import (
    DEFAULT_RUBRIC_JSON_PATH,
    EVALUATOR_INPUT_SCHEMA_VERSION,
    EVALUATOR_OUTPUT_SCHEMA_VERSION,
    EVALUATOR_PROMPT_ID,
    EVALUATOR_PROMPT_VERSION,
    LONGITUDINAL_EVALUATOR_SYSTEM_PROMPT,
    EvaluatorAgent,
    EvaluatorAgentError,
)
from app.persistence.database import DatabaseManager
from app.persistence.repositories.evaluations import EvaluationRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import ModelRunRepository
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import SimulationRunRepository

try:
    _SESSION_RUBRIC_CONTRACT = json.loads(
        DEFAULT_RUBRIC_JSON_PATH.read_text(encoding="utf-8")
    )
except (OSError, json.JSONDecodeError) as exc:
    raise RuntimeError("The machine-readable ACT session rubric is unavailable.") from exc

if (
    not isinstance(_SESSION_RUBRIC_CONTRACT, dict)
    or not isinstance(_SESSION_RUBRIC_CONTRACT.get("competency_ids"), list)
    or not all(
        isinstance(item, str)
        for item in _SESSION_RUBRIC_CONTRACT["competency_ids"]
    )
):
    raise RuntimeError("The machine-readable ACT session rubric is invalid.")

SESSION_COMPETENCIES = tuple(_SESSION_RUBRIC_CONTRACT["competency_ids"])
SESSION_RUBRIC_ID = "ACT_RUBRIC_V0"
SESSION_RUBRIC_VERSION = "0.2"
LONGITUDINAL_RUBRIC_ID = "ACT_LONGITUDINAL_RUBRIC_V0"
LONGITUDINAL_RUBRIC_VERSION = "0.2"
LONGITUDINAL_PROMPT_ID = "ACT_LONGITUDINAL_EVALUATOR_V0"
LONGITUDINAL_PROMPT_VERSION = "0.1"
LONGITUDINAL_RUBRIC_JSON_PATH = (
    project_root()
    / "rubrics"
    / "act"
    / "ACT_LONGITUDINAL_RUBRIC_V0.json"
)


def _load_longitudinal_rubric_contract() -> tuple[dict[str, object], str, str]:
    try:
        definition_text = LONGITUDINAL_RUBRIC_JSON_PATH.read_text(
            encoding="utf-8"
        )
        definition = json.loads(definition_text)
        if not isinstance(definition, dict):
            raise ValueError
        source_document = definition.get("source_document")
        if not isinstance(source_document, str):
            raise ValueError
        rubric_document = LONGITUDINAL_RUBRIC_JSON_PATH.with_name(
            source_document
        ).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            "The machine-readable ACT longitudinal rubric is unavailable."
        ) from exc
    competency_ids = definition.get("competency_ids")
    documented_ids = tuple(
        re.findall(
            r"\*\*Competency ID:\*\*\s+([a-z0-9_]+)",
            rubric_document,
        )
    )
    if (
        definition.get("rubric_id") != LONGITUDINAL_RUBRIC_ID
        or definition.get("version") != LONGITUDINAL_RUBRIC_VERSION
        or definition.get("scope") != "longitudinal"
        or definition.get("rating_codes") != ["0", "1", "2", "3", "NE"]
        or not isinstance(competency_ids, list)
        or not all(isinstance(item, str) for item in competency_ids)
        or tuple(competency_ids) != documented_ids
        or len(documented_ids) != len(set(documented_ids))
    ):
        raise RuntimeError(
            "The ACT longitudinal rubric contract does not match its document."
        )
    return definition, rubric_document, definition_text


_LONGITUDINAL_RUBRIC, _LONGITUDINAL_RUBRIC_DOCUMENT, _LONGITUDINAL_RUBRIC_TEXT = (
    _load_longitudinal_rubric_contract()
)
LONGITUDINAL_COMPETENCIES = tuple(
    _LONGITUDINAL_RUBRIC["competency_ids"]
)


class EvaluationServiceError(Exception):
    """Base class for evaluation service errors."""


class EvaluationUnavailableError(EvaluationServiceError):
    """No genuine Evaluator Agent is configured for this installation."""


class EvaluationNotFoundError(EvaluationServiceError):
    """The requested evaluation is not present."""


class EvaluationReviewUnavailableError(EvaluationServiceError):
    """The evaluation cannot accept a human review."""


class EvaluationRubricError(EvaluationServiceError):
    """The requested rubric or version is unsupported or invalid."""


class EvaluationSessionError(EvaluationServiceError):
    """The evaluated session is not eligible for an evaluation."""


class EvaluationRunError(EvaluationServiceError):
    """The evaluated run is not eligible for a longitudinal evaluation."""


class EvaluationGenerationError(EvaluationServiceError):
    """The Evaluator Agent failed or returned an invalid report."""


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    evaluation_id: str
    run_id: str
    session_id: str | None
    evaluation_scope: str
    rubric_id: str
    rubric_version: str
    status: str
    created_at: str
    overall_summary: str | None


class EvaluationService:
    """Generate evidence-validated session reports and expose stored reports."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        evaluator_agent: EvaluatorAgent | None = None,
    ) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        self._database_manager = database_manager
        self._evaluator_agent = evaluator_agent

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash_json(value: object) -> str:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _read_session_transcript(
        connection: sqlite3.Connection,
        session_id: str,
    ) -> tuple[sqlite3.Row, sqlite3.Row, list[sqlite3.Row], str, list[dict]]:
        session = SessionRepository(connection).get_session(session_id)
        if session is None:
            raise EvaluationSessionError("The requested session does not exist.")
        if session["status"] != "completed":
            raise EvaluationSessionError(
                "Only a completed session can be evaluated."
            )

        run = SimulationRunRepository(connection).get_run(session["run_id"])
        if run is None:
            raise EvaluationSessionError(
                "The session references a missing simulation run."
            )

        messages: list[sqlite3.Row] = []
        offset = 0
        while True:
            page = MessageRepository(connection).list_by_session(
                session_id,
                limit=200,
                offset=offset,
            )
            messages.extend(page)
            if len(page) < 200:
                break
            offset += len(page)

        if not messages or not any(row["role"] == "therapist" for row in messages):
            raise EvaluationSessionError(
                "The completed session has no therapist transcript evidence."
            )

        transcript_items = [
            {
                "message_id": row["message_id"],
                "sequence_number": row["sequence_number"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
            for row in messages
        ]
        transcript_hash = EvaluationService._hash_json(transcript_items)
        stored_hash = session["transcript_hash"]
        if stored_hash is not None and stored_hash != transcript_hash:
            raise EvaluationSessionError(
                "The completed transcript failed its integrity check."
            )

        manifest = [
            {
                "message_id": row["message_id"],
                "sequence_number": row["sequence_number"],
                "role": row["role"],
                "created_at": row["created_at"],
                "content_sha256": hashlib.sha256(
                    row["content"].encode("utf-8")
                ).hexdigest(),
            }
            for row in messages
        ]
        return session, run, messages, transcript_hash, manifest

    @staticmethod
    def _read_longitudinal_scope(
        connection: sqlite3.Connection,
        run_id: str,
    ) -> tuple[
        sqlite3.Row,
        list[sqlite3.Row],
        list[sqlite3.Row],
        list[dict[str, object]],
        list[dict[str, object]],
        list[dict[str, object]],
    ]:
        run = SimulationRunRepository(connection).get_run(run_id)
        if run is None:
            raise EvaluationRunError("The simulation Run does not exist.")
        all_sessions = connection.execute(
            """
            SELECT * FROM sessions
            WHERE run_id = ?
            ORDER BY session_number
            """,
            (run_id,),
        ).fetchall()
        completed_sessions = [
            session for session in all_sessions
            if session["status"] == "completed"
        ]
        if len(completed_sessions) < 2:
            raise EvaluationRunError(
                "Longitudinal evaluation requires at least two completed sessions."
            )

        transcript: list[dict[str, object]] = []
        manifest: list[dict[str, object]] = []
        session_scope: list[dict[str, object]] = []
        for selected_session in completed_sessions:
            session, _, messages, transcript_hash, session_manifest = (
                EvaluationService._read_session_transcript(
                    connection,
                    selected_session["session_id"],
                )
            )
            session_scope.append(
                {
                    "session_id": session["session_id"],
                    "session_number": session["session_number"],
                    "transcript_sha256": transcript_hash,
                }
            )
            transcript.extend(
                {
                    "message_id": message["message_id"],
                    "sequence_number": message["sequence_number"],
                    "role": message["role"],
                    "content": message["content"],
                    "session_id": session["session_id"],
                    "session_number": session["session_number"],
                }
                for message in messages
            )
            manifest.extend(
                {
                    **item,
                    "session_id": session["session_id"],
                    "session_number": session["session_number"],
                }
                for item in session_manifest
            )
        return (
            run,
            list(all_sessions),
            completed_sessions,
            transcript,
            manifest,
            session_scope,
        )

    def _require_agent(self) -> EvaluatorAgent:
        if self._evaluator_agent is None:
            raise EvaluationUnavailableError(
                "No Evaluator Agent is configured; no evaluation was created."
            )
        return self._evaluator_agent

    def _fail_model_run(self, model_run_id: str) -> None:
        with self._database_manager.transaction("operational") as connection:
            ModelRunRepository(connection).fail(
                model_run_id,
                completed_at=self._utc_now(),
                output_validation_status="rejected",
            )

    def _load_rubric_version(
        self,
        connection: sqlite3.Connection,
        *,
        definition: dict[str, object],
        definition_text: str,
        rubric_document: str,
    ) -> tuple[str, str, str]:
        rubric_hash = hashlib.sha256(
            (definition_text + "\n" + rubric_document).encode("utf-8")
        ).hexdigest()
        rubric_id = definition["rubric_id"]
        version = definition["version"]
        if not isinstance(rubric_id, str) or not isinstance(version, str):
            raise EvaluationRubricError("The session rubric identity is invalid.")

        existing = connection.execute(
            """
            SELECT rubric_version_id, content_hash
            FROM rubric_versions
            WHERE rubric_id = ? AND version_number = ?
            """,
            (rubric_id, version),
        ).fetchone()
        if existing is not None:
            if existing["content_hash"] != rubric_hash:
                raise EvaluationRubricError(
                    "The stored rubric version differs from the current rubric."
                )
            return existing["rubric_version_id"], rubric_hash, version

        rubric_version_id = "rubric-" + hashlib.sha256(
            f"{rubric_id}:{version}:{rubric_hash}".encode("utf-8")
        ).hexdigest()[:32]
        EvaluationRepository(connection).create_rubric_version(
            rubric_version_id=rubric_version_id,
            rubric_id=rubric_id,
            version_number=version,
            modality="ACT",
            language="en",
            schema_version=EVALUATOR_OUTPUT_SCHEMA_VERSION,
            created_at=self._utc_now(),
            rubric_definition={
                **definition,
                "content_sha256": rubric_hash,
            },
            content_hash=rubric_hash,
        )
        return rubric_version_id, rubric_hash, version

    def generate_session_evaluation(
        self,
        *,
        session_id: str,
        rubric_id: str = SESSION_RUBRIC_ID,
        rubric_version: str = SESSION_RUBRIC_VERSION,
    ) -> dict:
        agent = self._require_agent()
        try:
            definition, rubric_document, definition_text = agent.load_rubric()
        except EvaluatorAgentError as exc:
            raise EvaluationRubricError(
                "The versioned ACT session rubric could not be loaded."
            ) from exc
        if (
            rubric_id != definition.get("rubric_id")
            or rubric_version != definition.get("version")
        ):
            raise EvaluationRubricError(
                "The requested ACT session rubric version is unsupported."
            )

        with self._database_manager.connection("operational") as connection:
            session, run, messages, transcript_hash, manifest = (
                self._read_session_transcript(connection, session_id)
            )
        if (
            run["modality"].casefold() != "act"
            or run["evaluation_rubric_id"] != rubric_id
            or run["evaluation_rubric_version"] != rubric_version
        ):
            raise EvaluationRubricError(
                "The session run is not configured for this ACT rubric."
            )

        transcript = [
            {
                "message_id": row["message_id"],
                "sequence_number": row["sequence_number"],
                "role": row["role"],
                "content": row["content"],
            }
            for row in messages
        ]
        rubric_hash = hashlib.sha256(
            (definition_text + "\n" + rubric_document).encode("utf-8")
        ).hexdigest()
        input_hash = self._hash_json({
            "transcript_hash": transcript_hash,
            "rubric_hash": rubric_hash,
            "prompt_id": EVALUATOR_PROMPT_ID,
            "prompt_version": EVALUATOR_PROMPT_VERSION,
        })
        model_run_id = "model-run-evaluator-" + uuid.uuid4().hex
        started_at = self._utc_now()
        provider_config = agent.client.config
        with self._database_manager.transaction("operational") as connection:
            ModelRunRepository(connection).create_model_run(
                model_run_id=model_run_id,
                run_id=run["run_id"],
                session_id=session_id,
                component="evaluator_agent",
                provider=provider_config.name,
                model_identifier=agent.model,
                execution_status="in_progress",
                started_at=started_at,
                generation_parameters={
                    "temperature": 0.0,
                    "max_tokens": agent.max_tokens,
                },
                prompt_id=EVALUATOR_PROMPT_ID,
                prompt_version=EVALUATOR_PROMPT_VERSION,
                input_schema_version=EVALUATOR_INPUT_SCHEMA_VERSION,
                output_schema_version=EVALUATOR_OUTPUT_SCHEMA_VERSION,
                input_hash=input_hash,
            )

        try:
            report = agent.evaluate(
                transcript,
                rubric_definition=definition,
                rubric_document=rubric_document,
            )
        except (EvaluatorAgentError, ProviderConnectionError) as exc:
            self._fail_model_run(model_run_id)
            raise EvaluationGenerationError(
                "The local Evaluator Agent failed to produce a validated report."
            ) from exc

        evaluation_id = "evaluation-" + uuid.uuid4().hex
        completed_at = self._utc_now()
        report_dict = report.model_dump(mode="json")
        report_metadata = {
            "experimental": True,
            "validation_status": "exact_transcript_references_validated",
            "human_review_required": True,
            "evaluator_model": agent.model,
            "evaluator_prompt_id": EVALUATOR_PROMPT_ID,
            "evaluator_prompt_version": EVALUATOR_PROMPT_VERSION,
            "rubric_content_sha256": rubric_hash,
            "transcript_sha256": transcript_hash,
            "competencies": {
                item.competency_id: {
                    "confidence": item.confidence,
                    "strengths": item.strengths,
                    "missing_evidence": item.missing_evidence,
                }
                for item in report.competencies
            },
            "limitations": definition.get("limitations", []),
        }

        try:
            with self._database_manager.transaction("operational") as connection:
                current_session, _, current_messages, current_hash, _ = (
                    self._read_session_transcript(connection, session_id)
                )
                if (
                    current_session["run_id"] != run["run_id"]
                    or current_hash != transcript_hash
                    or len(current_messages) != len(messages)
                ):
                    raise EvaluationSessionError(
                        "The transcript changed during evaluation."
                    )

                rubric_version_id, _, _ = self._load_rubric_version(
                    connection,
                    definition=definition,
                    definition_text=definition_text,
                    rubric_document=rubric_document,
                )
                revision = connection.execute(
                    """
                    SELECT COALESCE(MAX(evaluation_revision), 0) + 1
                    FROM evaluations
                    WHERE session_id = ? AND evaluation_scope = 'session'
                    """,
                    (session_id,),
                ).fetchone()[0]
                repository = EvaluationRepository(connection)
                repository.create_evaluation(
                    evaluation_id=evaluation_id,
                    run_id=run["run_id"],
                    session_id=session_id,
                    evaluation_scope="session",
                    rubric_version_id=rubric_version_id,
                    evaluation_revision=revision,
                    status="requires_review",
                    created_at=completed_at,
                    transcript_manifest=manifest,
                    evaluator_model_run_id=model_run_id,
                    overall_summary=report.overall_summary,
                    report_metadata=report_metadata,
                )

                message_by_id = {
                    row["message_id"]: row
                    for row in current_messages
                }
                for item in report.competencies:
                    item_id = "evaluation-item-" + uuid.uuid4().hex
                    repository.create_item(
                        evaluation_item_id=item_id,
                        evaluation_id=evaluation_id,
                        competency_id=item.competency_id,
                        rating_code=item.rating_code,
                        justification=item.explanation,
                        alternative_response=item.alternative_response,
                        limitations="\n".join(item.limitations) or None,
                        uncertainty_notes=item.uncertainty_notes or None,
                    )
                    for evidence in item.evidence:
                        source = message_by_id[evidence.message_id]
                        start_offset = source["content"].find(evidence.excerpt)
                        repository.add_evidence(
                            evaluation_item_id=item_id,
                            message_id=evidence.message_id,
                            evidence_role=evidence.evidence_role,
                            start_offset=start_offset,
                            end_offset=start_offset + len(evidence.excerpt),
                            evidence_excerpt=evidence.excerpt,
                            evidence_note=evidence.evidence_note or None,
                        )

                output_hash = hashlib.sha256(
                    json.dumps(
                        report_dict,
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
                if not ModelRunRepository(connection).complete(
                    model_run_id,
                    completed_at=completed_at,
                    output_hash=output_hash,
                    output_validation_status="valid",
                ):
                    raise EvaluationGenerationError(
                        "The evaluator execution record could not be completed."
                    )
        except EvaluationServiceError:
            self._fail_model_run(model_run_id)
            raise
        except (sqlite3.Error, ValueError) as exc:
            self._fail_model_run(model_run_id)
            raise EvaluationGenerationError(
                "The validated evaluation could not be persisted."
            ) from exc

        record = self.get_evaluation(evaluation_id=evaluation_id)
        if record is None:
            raise EvaluationServiceError(
                "The persisted evaluation could not be retrieved."
            )
        return record

    def generate_run_evaluation(
        self,
        *,
        run_id: str,
        rubric_id: str = LONGITUDINAL_RUBRIC_ID,
        rubric_version: str = LONGITUDINAL_RUBRIC_VERSION,
    ) -> dict:
        if (
            rubric_id != LONGITUDINAL_RUBRIC_ID
            or rubric_version != LONGITUDINAL_RUBRIC_VERSION
        ):
            raise EvaluationRubricError(
                "The requested longitudinal ACT rubric version is unsupported."
            )
        with self._database_manager.connection("operational") as connection:
            (
                run,
                all_sessions,
                _,
                transcript,
                manifest,
                session_scope,
            ) = self._read_longitudinal_scope(connection, run_id)
        run_sessions_snapshot = [
            {
                "session_id": item["session_id"],
                "session_number": item["session_number"],
                "status": item["status"],
            }
            for item in all_sessions
        ]
        if run["modality"].casefold() != "act":
            raise EvaluationRubricError(
                "The longitudinal ACT rubric requires an ACT Run."
            )
        agent = self._require_agent()

        rubric_hash = hashlib.sha256(
            (
                _LONGITUDINAL_RUBRIC_TEXT
                + "\n"
                + _LONGITUDINAL_RUBRIC_DOCUMENT
            ).encode("utf-8")
        ).hexdigest()
        scope_hash = self._hash_json(session_scope)
        input_hash = self._hash_json(
            {
                "session_scope_sha256": scope_hash,
                "rubric_sha256": rubric_hash,
                "prompt_id": LONGITUDINAL_PROMPT_ID,
                "prompt_version": LONGITUDINAL_PROMPT_VERSION,
            }
        )
        model_run_id = "model-run-evaluator-" + uuid.uuid4().hex
        started_at = self._utc_now()
        provider_config = agent.client.config
        with self._database_manager.transaction("operational") as connection:
            ModelRunRepository(connection).create_model_run(
                model_run_id=model_run_id,
                run_id=run_id,
                session_id=None,
                component="evaluator_agent",
                provider=provider_config.name,
                model_identifier=agent.model,
                execution_status="in_progress",
                started_at=started_at,
                generation_parameters={
                    "temperature": 0.0,
                    "max_tokens": agent.max_tokens,
                },
                prompt_id=LONGITUDINAL_PROMPT_ID,
                prompt_version=LONGITUDINAL_PROMPT_VERSION,
                input_schema_version=EVALUATOR_INPUT_SCHEMA_VERSION,
                output_schema_version=EVALUATOR_OUTPUT_SCHEMA_VERSION,
                input_hash=input_hash,
            )

        try:
            report = agent.evaluate(
                transcript,
                rubric_definition=_LONGITUDINAL_RUBRIC,
                rubric_document=_LONGITUDINAL_RUBRIC_DOCUMENT,
                system_prompt=LONGITUDINAL_EVALUATOR_SYSTEM_PROMPT,
                require_multi_session_evidence=True,
            )
        except (EvaluatorAgentError, ProviderConnectionError) as exc:
            self._fail_model_run(model_run_id)
            raise EvaluationGenerationError(
                "The longitudinal Evaluator Agent failed to produce a "
                "validated report."
            ) from exc

        evaluation_id = "evaluation-" + uuid.uuid4().hex
        completed_at = self._utc_now()
        report_dict = report.model_dump(mode="json")
        report_metadata = {
            "experimental": True,
            "validation_status": "exact_cross_session_references_validated",
            "human_review_required": True,
            "evaluator_model": agent.model,
            "evaluator_prompt_id": LONGITUDINAL_PROMPT_ID,
            "evaluator_prompt_version": LONGITUDINAL_PROMPT_VERSION,
            "rubric_content_sha256": rubric_hash,
            "session_scope_sha256": scope_hash,
            "longitudinal_session_scope": session_scope,
            "run_sessions_snapshot": run_sessions_snapshot,
            "competencies": {
                item.competency_id: {
                    "confidence": item.confidence,
                    "strengths": item.strengths,
                    "missing_evidence": item.missing_evidence,
                }
                for item in report.competencies
            },
            "limitations": _LONGITUDINAL_RUBRIC.get("limitations", []),
        }

        try:
            with self._database_manager.transaction("operational") as connection:
                (
                    current_run,
                    current_all_sessions,
                    _,
                    current_transcript,
                    _,
                    current_scope,
                ) = self._read_longitudinal_scope(connection, run_id)
                if (
                    current_run["modality"] != run["modality"]
                    or [
                        {
                            "session_id": row["session_id"],
                            "session_number": row["session_number"],
                            "status": row["status"],
                        }
                        for row in current_all_sessions
                    ]
                    != run_sessions_snapshot
                    or current_scope != session_scope
                    or len(current_transcript) != len(transcript)
                ):
                    raise EvaluationRunError(
                        "The Run's session scope changed during evaluation."
                    )

                rubric_version_id, _, _ = self._load_rubric_version(
                    connection,
                    definition=_LONGITUDINAL_RUBRIC,
                    definition_text=_LONGITUDINAL_RUBRIC_TEXT,
                    rubric_document=_LONGITUDINAL_RUBRIC_DOCUMENT,
                )
                revision = connection.execute(
                    """
                    SELECT COALESCE(MAX(evaluation_revision), 0) + 1
                    FROM evaluations
                    WHERE run_id = ? AND evaluation_scope = 'longitudinal'
                    """,
                    (run_id,),
                ).fetchone()[0]
                repository = EvaluationRepository(connection)
                repository.create_evaluation(
                    evaluation_id=evaluation_id,
                    run_id=run_id,
                    session_id=None,
                    evaluation_scope="longitudinal",
                    rubric_version_id=rubric_version_id,
                    evaluation_revision=revision,
                    status="requires_review",
                    created_at=completed_at,
                    transcript_manifest=manifest,
                    evaluator_model_run_id=model_run_id,
                    overall_summary=report.overall_summary,
                    report_metadata=report_metadata,
                )

                message_by_id = {
                    item["message_id"]: item for item in current_transcript
                }
                for item in report.competencies:
                    item_id = "evaluation-item-" + uuid.uuid4().hex
                    repository.create_item(
                        evaluation_item_id=item_id,
                        evaluation_id=evaluation_id,
                        competency_id=item.competency_id,
                        rating_code=item.rating_code,
                        justification=item.explanation,
                        alternative_response=item.alternative_response,
                        limitations="\n".join(item.limitations) or None,
                        uncertainty_notes=item.uncertainty_notes or None,
                    )
                    for evidence in item.evidence:
                        source = message_by_id[evidence.message_id]
                        start_offset = source["content"].find(evidence.excerpt)
                        repository.add_evidence(
                            evaluation_item_id=item_id,
                            message_id=evidence.message_id,
                            evidence_role=evidence.evidence_role,
                            start_offset=start_offset,
                            end_offset=start_offset + len(evidence.excerpt),
                            evidence_excerpt=evidence.excerpt,
                            evidence_note=evidence.evidence_note or None,
                        )

                output_hash = hashlib.sha256(
                    json.dumps(
                        report_dict,
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()
                if not ModelRunRepository(connection).complete(
                    model_run_id,
                    completed_at=completed_at,
                    output_hash=output_hash,
                    output_validation_status="valid",
                ):
                    raise EvaluationGenerationError(
                        "The longitudinal evaluator execution record could "
                        "not be completed."
                    )
        except EvaluationServiceError:
            self._fail_model_run(model_run_id)
            raise
        except (sqlite3.Error, ValueError) as exc:
            self._fail_model_run(model_run_id)
            raise EvaluationGenerationError(
                "The validated longitudinal evaluation could not be persisted."
            ) from exc

        record = self.get_evaluation(evaluation_id=evaluation_id)
        if record is None:
            raise EvaluationServiceError(
                "The persisted longitudinal evaluation could not be retrieved."
            )
        return record

    def _is_run_evaluation_stale(self, record: dict) -> bool:
        if record.get("evaluation_scope") != "longitudinal":
            return False
        raw_metadata = record.get("report_metadata")
        try:
            metadata = (
                json.loads(raw_metadata)
                if isinstance(raw_metadata, str)
                else None
            )
        except json.JSONDecodeError as exc:
            raise EvaluationServiceError(
                "Stored longitudinal evaluation metadata is invalid."
            ) from exc
        session_scope = (
            metadata.get("longitudinal_session_scope")
            if isinstance(metadata, dict)
            else None
        )
        run_sessions_snapshot = (
            metadata.get("run_sessions_snapshot")
            if isinstance(metadata, dict)
            else None
        )
        if not isinstance(session_scope, list) or len(session_scope) < 2:
            return True
        if not isinstance(run_sessions_snapshot, list):
            return True
        snapshot_by_id: dict[str, tuple[int, str]] = {}
        for item in run_sessions_snapshot:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("session_id"), str)
                or isinstance(item.get("session_number"), bool)
                or not isinstance(item.get("session_number"), int)
                or not isinstance(item.get("status"), str)
            ):
                return True
            snapshot_by_id[item["session_id"]] = (
                item["session_number"],
                item["status"],
            )
        if len(snapshot_by_id) != len(run_sessions_snapshot):
            return True
        expected: dict[str, tuple[int, str]] = {}
        for item in session_scope:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("session_id"), str)
                or isinstance(item.get("session_number"), bool)
                or not isinstance(item.get("session_number"), int)
                or not isinstance(item.get("transcript_sha256"), str)
            ):
                return True
            expected[item["session_id"]] = (
                item["session_number"],
                item["transcript_sha256"],
            )
            if snapshot_by_id.get(item["session_id"]) != (
                item["session_number"],
                "completed",
            ):
                return True
        if len(expected) != len(session_scope):
            return True
        if list(expected) != [
            item["session_id"]
            for item in run_sessions_snapshot
            if item["status"] == "completed"
        ]:
            return True

        with self._database_manager.connection("operational") as connection:
            sessions = connection.execute(
                """
                SELECT session_id, session_number, status
                FROM sessions
                WHERE run_id = ?
                ORDER BY session_number
                """,
                (record["run_id"],),
            ).fetchall()
            current_snapshot = [
                {
                    "session_id": row["session_id"],
                    "session_number": row["session_number"],
                    "status": row["status"],
                }
                for row in sessions
            ]
            if current_snapshot != run_sessions_snapshot:
                return True
            for row in sessions:
                if row["session_id"] not in expected:
                    continue
                if row["status"] != "completed":
                    return True
                _, _, _, transcript_hash, _ = self._read_session_transcript(
                    connection,
                    row["session_id"],
                )
                if expected[row["session_id"]] != (
                    row["session_number"],
                    transcript_hash,
                ):
                    return True
        return False

    def list_session_evaluations(self, *, session_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT e.*, rv.rubric_id, rv.version_number AS rubric_version,
                       rv.rubric_version_id,
                       rv.content_hash AS rubric_content_hash
                FROM evaluations e
                JOIN rubric_versions rv ON rv.rubric_version_id = e.rubric_version_id
                WHERE e.session_id = ?
                ORDER BY e.created_at DESC, e.evaluation_id
                """,
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_run_evaluations(self, *, run_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT e.*, rv.rubric_id, rv.version_number AS rubric_version,
                       rv.rubric_version_id,
                       rv.content_hash AS rubric_content_hash
                FROM evaluations e
                JOIN rubric_versions rv ON rv.rubric_version_id = e.rubric_version_id
                WHERE e.run_id = ?
                ORDER BY e.created_at DESC, e.evaluation_id
                """,
                (run_id,),
            ).fetchall()
            records = [dict(row) for row in rows]
        for record in records:
            record["stale"] = self._is_run_evaluation_stale(record)
        return records

    def get_evaluation(self, *, evaluation_id: str) -> dict | None:
        with self._database_manager.connection("operational") as connection:
            row = connection.execute(
                """
                SELECT e.*, rv.rubric_id, rv.version_number AS rubric_version,
                       rv.rubric_version_id,
                       rv.content_hash AS rubric_content_hash
                FROM evaluations e
                JOIN rubric_versions rv ON rv.rubric_version_id = e.rubric_version_id
                WHERE e.evaluation_id = ?
                """,
                (evaluation_id,),
            ).fetchone()
            record = dict(row) if row is not None else None
        if record is not None:
            record["stale"] = self._is_run_evaluation_stale(record)
        return record

    def list_items(self, *, evaluation_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM evaluation_items
                WHERE evaluation_id = ?
                ORDER BY competency_id
                """,
                (evaluation_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_evidence_for_item(self, *, evaluation_item_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            rows = connection.execute(
                """
                SELECT evidence.*,
                       messages.session_id,
                       sessions.session_number,
                       messages.role AS source_role,
                       messages.content AS source_message_content
                FROM evaluation_evidence AS evidence
                LEFT JOIN messages
                    ON messages.message_id = evidence.message_id
                LEFT JOIN sessions
                    ON sessions.session_id = messages.session_id
                WHERE evidence.evaluation_item_id = ?
                ORDER BY evidence.message_id
                """,
                (evaluation_item_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_reviews(self, *, evaluation_id: str) -> list[dict]:
        with self._database_manager.connection("operational") as connection:
            if EvaluationRepository(connection).get_evaluation(evaluation_id) is None:
                raise EvaluationNotFoundError(
                    "The requested evaluation does not exist."
                )
            reviews = EvaluationRepository(connection).list_reviews(
                evaluation_id
            )
            return [dict(review) for review in reviews]

    def add_review(
        self,
        *,
        evaluation_id: str,
        reviewer_user_id: str,
        decision: str,
        feedback: str,
    ) -> dict:
        if not isinstance(feedback, str) or not 1 <= len(feedback.strip()) <= 4000:
            raise ValueError(
                "Evaluation review feedback must contain 1 to 4000 characters."
            )
        if not isinstance(decision, str) or decision not in {
            "accepted",
            "revision_requested",
        }:
            raise ValueError("Invalid evaluation review decision.")
        if not isinstance(reviewer_user_id, str) or not reviewer_user_id.strip():
            raise ValueError("reviewer_user_id must be non-empty text.")

        with self._database_manager.transaction("operational") as connection:
            repository = EvaluationRepository(connection)
            row = repository.get_evaluation(evaluation_id)
            if row is None:
                raise EvaluationNotFoundError(
                    "The requested evaluation does not exist."
                )
            record = dict(row)
            if (
                record["evaluator_model_run_id"] is None
                or record["status"] not in {"requires_review", "completed"}
                or self._is_run_evaluation_stale(record)
            ):
                raise EvaluationReviewUnavailableError(
                    "The evaluation is not eligible for human review."
                )
            review_number = repository.next_review_number(evaluation_id)
            repository.create_review(
                review_id="evaluation-review-" + uuid.uuid4().hex,
                evaluation_id=evaluation_id,
                review_number=review_number,
                reviewer_user_id=reviewer_user_id.strip(),
                decision=decision,
                feedback=feedback.strip(),
                created_at=self._utc_now(),
            )
            return dict(repository.list_reviews(evaluation_id)[-1])
