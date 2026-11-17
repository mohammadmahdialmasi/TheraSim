"""Application service for simulation run lifecycle management."""

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.character_personality import (
    CharacterPersonalityRepository,
)
from app.persistence.repositories.character_runtime import (
    DEFAULT_CHARACTER_STATE_VALUES,
    RunCharacterRepository,
)
from app.services.character_model import CHARACTER_STATE_SCHEMA_VERSION
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.operations import AuditRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import (
    SESSION_PLANNING_POLICIES,
    SimulationRunRepository,
)


DEFAULT_PROTOCOL_ID = "ACT_EDUCATIONAL_SIMULATION"
DEFAULT_PROTOCOL_VERSION = "0.1"
DEFAULT_EVALUATION_RUBRIC_ID = "ACT_RUBRIC_V0"
DEFAULT_EVALUATION_RUBRIC_VERSION = "0.2"


class RunServiceError(Exception):
    """Base exception for simulation run operations."""


class RunCaseNotFoundError(RunServiceError):
    """The requested case does not exist."""


class RunCaseInactiveError(RunServiceError):
    """The case is not active and cannot start a simulation."""


class RunCaseVersionNotFoundError(RunServiceError):
    """The requested version does not belong to the specified case."""


class RunProtocolConfigurationError(RunServiceError):
    """The requested Run protocol configuration is unsupported."""


class RestrictedProfileNotFoundError(RunServiceError):
    """The matching restricted case profile does not exist."""


class RunNotFoundError(RunServiceError):
    """The requested simulation run does not exist."""


class RunConflictError(RunServiceError):
    """A run or audit identity conflicts with existing data."""


class RunStateTransitionError(RunServiceError):
    """The requested run status transition is not permitted."""


@dataclass(frozen=True, slots=True)
class SimulationRunRecord:
    run_id: str
    case_id: str
    case_version_id: str
    modality: str
    language: str
    status: str
    configuration_version: str
    started_at: str | None
    completed_at: str | None
    created_at: str
    protocol_id: str = DEFAULT_PROTOCOL_ID
    protocol_version: str = DEFAULT_PROTOCOL_VERSION
    session_planning_policy: str = "flexible"
    evaluation_rubric_id: str = DEFAULT_EVALUATION_RUBRIC_ID
    evaluation_rubric_version: str = DEFAULT_EVALUATION_RUBRIC_VERSION


class RunService:
    """Coordinates run creation, validation, status, and audit operations.

    Operational and restricted databases remain independent.

    Restricted case information is only checked for existence here.
    Its contents are never returned by this service.
    """

    _ALLOWED_TRANSITIONS = {
        "initialized": frozenset({"active", "failed"}),
        "active": frozenset({"interrupted", "completed", "failed"}),
        "interrupted": frozenset({"active", "failed"}),
        "completed": frozenset(),
        "failed": frozenset(),
    }

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")

        self._database_manager = database_manager

    @staticmethod
    def _from_row(row: sqlite3.Row) -> SimulationRunRecord:
        return SimulationRunRecord(
            run_id=row["run_id"],
            case_id=row["case_id"],
            case_version_id=row["case_version_id"],
            modality=row["modality"],
            language=row["language"],
            status=row["status"],
            configuration_version=row["configuration_version"],
            protocol_id=row["protocol_id"],
            protocol_version=row["protocol_version"],
            session_planning_policy=row["session_planning_policy"],
            evaluation_rubric_id=row["evaluation_rubric_id"],
            evaluation_rubric_version=row["evaluation_rubric_version"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _record_audit(
        repository: AuditRepository,
        *,
        run_id: str,
        operation_type: str,
        occurred_at: str,
        metadata: dict[str, object],
    ) -> None:
        repository.record(
            audit_event_id=uuid.uuid4().hex,
            component="run_service",
            operation_type=operation_type,
            entity_type="simulation_run",
            entity_id=run_id,
            run_id=run_id,
            operation_status="succeeded",
            metadata=metadata,
            created_at=occurred_at,
        )

    def create_run(
        self,
        *,
        run_id: str,
        case_id: str,
        case_version_id: str,
        configuration_version: str,
        created_at: str,
        protocol_id: str = DEFAULT_PROTOCOL_ID,
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
        session_planning_policy: str = "flexible",
        evaluation_rubric_id: str = DEFAULT_EVALUATION_RUBRIC_ID,
        evaluation_rubric_version: str = DEFAULT_EVALUATION_RUBRIC_VERSION,
    ) -> SimulationRunRecord:
        """Create an initialized run after validating both databases.

        Modality and language are copied from the selected case version.
        The restricted profile is checked but its contents are not exposed.
        """

        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                cases = CaseRepository(connection)

                case = cases.get_case(case_id)

                if case is None:
                    raise RunCaseNotFoundError(
                        "The requested case does not exist."
                    )

                if case["status"] != "active":
                    raise RunCaseInactiveError(
                        "Only active cases can start a simulation."
                    )

                version = cases.get_case_version_for_case(
                    case_id,
                    case_version_id,
                )

                if version is None:
                    raise RunCaseVersionNotFoundError(
                        "The requested version does not belong to this case."
                    )

                if (
                    protocol_id != DEFAULT_PROTOCOL_ID
                    or protocol_version != DEFAULT_PROTOCOL_VERSION
                    or version["modality"].casefold() != "act"
                    or evaluation_rubric_id != DEFAULT_EVALUATION_RUBRIC_ID
                    or evaluation_rubric_version
                    != DEFAULT_EVALUATION_RUBRIC_VERSION
                    or session_planning_policy not in SESSION_PLANNING_POLICIES
                ):
                    raise RunProtocolConfigurationError(
                        "The requested protocol configuration is unsupported."
                    )

                with self._database_manager.connection(
                    "restricted"
                ) as restricted_connection:
                    restricted_profile = RestrictedCaseRepository(
                        restricted_connection
                    ).get_profile(
                        case_id,
                        case_version_id,
                    )
                    personality_profile = CharacterPersonalityRepository(
                        restricted_connection
                    ).get_active_profile(
                        case_id,
                        case_version_id,
                    )

                if restricted_profile is None:
                    raise RestrictedProfileNotFoundError(
                        "The matching restricted case profile does not exist."
                    )

                runs = SimulationRunRepository(connection)

                runs.create_run(
                    run_id=run_id,
                    case_id=case_id,
                    case_version_id=case_version_id,
                    modality=version["modality"],
                    language=version["language"],
                    configuration_version=configuration_version,
                    created_at=created_at,
                    protocol_id=protocol_id,
                    protocol_version=protocol_version,
                    session_planning_policy=session_planning_policy,
                    evaluation_rubric_id=evaluation_rubric_id,
                    evaluation_rubric_version=evaluation_rubric_version,
                    status="initialized",
                )

                # Keep full personality content in the restricted Case Vault.
                # The operational database captures only an immutable version/hash
                # reference plus the run-specific dynamic-state baseline.
                character_repository = RunCharacterRepository(connection)

                if personality_profile is None:
                    character_id = "UNCONFIGURED_CHARACTER"
                    personality_profile_id = None
                    profile_version = None
                    theory_bundle_version = None
                    source_content_hash = None
                    personality_schema_version = "0.1"
                    initial_state = dict(DEFAULT_CHARACTER_STATE_VALUES)
                    profile_status = "unconfigured"
                else:
                    profile_json = personality_profile["profile_json"]
                    try:
                        profile_document = json.loads(profile_json)
                    except (TypeError, json.JSONDecodeError) as exc:
                        raise RunServiceError(
                            "The active character personality profile is invalid."
                        ) from exc

                    if not isinstance(profile_document, dict):
                        raise RunServiceError(
                            "The active character personality profile must be a JSON object."
                        )

                    actual_hash = hashlib.sha256(
                        profile_json.encode("utf-8")
                    ).hexdigest()
                    if actual_hash != personality_profile["content_hash"]:
                        raise RunServiceError(
                            "The active character personality profile failed its integrity check."
                        )

                    expected_identity = {
                        "personality_profile_id": personality_profile["personality_profile_id"],
                        "character_id": personality_profile["character_id"],
                        "case_id": case_id,
                        "case_version_id": case_version_id,
                        "profile_version": personality_profile["profile_version"],
                    }
                    if any(
                        profile_document.get(key) != value
                        for key, value in expected_identity.items()
                    ):
                        raise RunServiceError(
                            "The active personality profile identity is inconsistent."
                        )

                    character_id = personality_profile["character_id"]
                    personality_profile_id = personality_profile["personality_profile_id"]
                    profile_version = personality_profile["profile_version"]
                    theory_bundle_version = personality_profile["theory_bundle_version"]
                    source_content_hash = personality_profile["content_hash"]
                    personality_schema_version = personality_profile[
                        "personality_schema_version"
                    ]
                    initial_state = profile_document.get("initial_state")
                    if initial_state is None:
                        initial_state = dict(DEFAULT_CHARACTER_STATE_VALUES)
                    elif not isinstance(initial_state, dict):
                        raise RunServiceError(
                            "The active personality profile has an invalid initial state."
                        )
                    profile_status = "active"

                profile_snapshot_id = uuid.uuid4().hex
                character_repository.create_profile_snapshot(
                    snapshot_id=profile_snapshot_id,
                    run_id=run_id,
                    case_id=case_id,
                    case_version_id=case_version_id,
                    character_id=character_id,
                    profile_status=profile_status,
                    personality_profile_id=personality_profile_id,
                    profile_version=profile_version,
                    personality_schema_version=personality_schema_version,
                    theory_bundle_version=theory_bundle_version,
                    source_content_hash=source_content_hash,
                    captured_at=created_at,
                )

                character_state_snapshot_id = uuid.uuid4().hex
                character_repository.create_state_snapshot(
                    snapshot_id=character_state_snapshot_id,
                    run_id=run_id,
                    state_schema_version=CHARACTER_STATE_SCHEMA_VERSION,
                    snapshot_reason="run_initialization",
                    created_at=created_at,
                    values=initial_state,
                )

                row = runs.get_run(run_id)

                if row is None:
                    raise RunServiceError(
                        "Created simulation run could not be retrieved."
                    )

                self._record_audit(
                    AuditRepository(connection),
                    run_id=run_id,
                    operation_type="run_created",
                    occurred_at=created_at,
                    metadata={
                        "case_id": case_id,
                        "case_version_id": case_version_id,
                        "modality": version["modality"],
                        "language": version["language"],
                        "protocol_id": protocol_id,
                        "protocol_version": protocol_version,
                        "session_planning_policy": session_planning_policy,
                        "evaluation_rubric_id": evaluation_rubric_id,
                        "evaluation_rubric_version": evaluation_rubric_version,
                        "initial_status": "initialized",
                        "character_profile_status": profile_status,
                        "personality_profile_id": personality_profile_id,
                        "personality_profile_version": profile_version,
                        "character_profile_snapshot_id": profile_snapshot_id,
                        "character_state_snapshot_id": character_state_snapshot_id,
                    },
                )

                result = self._from_row(row)

        except sqlite3.IntegrityError as exc:
            raise RunConflictError(
                "The simulation run identifier conflicts with existing data."
            ) from exc

        return result

    def get_run(
        self,
        run_id: str,
    ) -> SimulationRunRecord | None:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = SimulationRunRepository(connection).get_run(run_id)

            return (
                self._from_row(row)
                if row is not None
                else None
            )

    def list_runs(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SimulationRunRecord]:
        with self._database_manager.connection(
            "operational"
        ) as connection:
            rows = SimulationRunRepository(connection).list_runs(
                status=status,
                limit=limit,
                offset=offset,
            )

            return [
                self._from_row(row)
                for row in rows
            ]

    def _transition(
        self,
        run_id: str,
        *,
        expected_statuses: frozenset[str],
        target_status: str,
        occurred_at: str,
    ) -> SimulationRunRecord:
        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                runs = SimulationRunRepository(connection)
                row = runs.get_run(run_id)

                if row is None:
                    raise RunNotFoundError(
                        "The requested simulation run does not exist."
                    )

                previous_status = row["status"]

                if (
                    previous_status not in expected_statuses
                    or target_status
                    not in self._ALLOWED_TRANSITIONS.get(
                        previous_status,
                        frozenset(),
                    )
                ):
                    raise RunStateTransitionError(
                        f"Cannot transition run from "
                        f"{previous_status} to {target_status}."
                    )

                if target_status == "completed":
                    sessions = SessionRepository(
                        connection
                    ).list_by_run(run_id)

                    expected_numbers = list(range(1, len(sessions) + 1))
                    actual_numbers = [
                        session["session_number"]
                        for session in sessions
                    ]

                    if not sessions:
                        raise RunStateTransitionError(
                            "A run must contain at least one completed session."
                        )

                    if actual_numbers != expected_numbers:
                        raise RunStateTransitionError(
                            "Run sessions must be sequential before completion."
                        )

                    if any(
                        session["status"] != "completed"
                        for session in sessions
                    ):
                        raise RunStateTransitionError(
                            "All created sessions must be completed "
                            "before completing the run."
                        )

                update_options: dict[str, str] = {}

                if target_status == "active" and previous_status == "initialized":
                    update_options["started_at"] = occurred_at

                if target_status == "completed":
                    update_options["completed_at"] = occurred_at

                updated = runs.update_status(
                    run_id,
                    target_status,
                    **update_options,
                )

                if not updated:
                    raise RunServiceError(
                        "Simulation run status could not be updated."
                    )

                self._record_audit(
                    AuditRepository(connection),
                    run_id=run_id,
                    operation_type="run_status_changed",
                    occurred_at=occurred_at,
                    metadata={
                        "previous_status": previous_status,
                        "new_status": target_status,
                    },
                )

                updated_row = runs.get_run(run_id)

                if updated_row is None:
                    raise RunServiceError(
                        "Updated simulation run could not be retrieved."
                    )

                result = self._from_row(updated_row)

        except sqlite3.IntegrityError as exc:
            raise RunConflictError(
                "The simulation run update conflicts with persisted data."
            ) from exc

        return result

    def start_run(
        self,
        run_id: str,
        *,
        started_at: str,
    ) -> SimulationRunRecord:
        return self._transition(
            run_id,
            expected_statuses=frozenset({"initialized"}),
            target_status="active",
            occurred_at=started_at,
        )

    def interrupt_run(
        self,
        run_id: str,
        *,
        interrupted_at: str,
    ) -> SimulationRunRecord:
        return self._transition(
            run_id,
            expected_statuses=frozenset({"active"}),
            target_status="interrupted",
            occurred_at=interrupted_at,
        )

    def resume_run(
        self,
        run_id: str,
        *,
        resumed_at: str,
    ) -> SimulationRunRecord:
        return self._transition(
            run_id,
            expected_statuses=frozenset({"interrupted"}),
            target_status="active",
            occurred_at=resumed_at,
        )

    def complete_run(
        self,
        run_id: str,
        *,
        completed_at: str,
    ) -> SimulationRunRecord:
        return self._transition(
            run_id,
            expected_statuses=frozenset({"active"}),
            target_status="completed",
            occurred_at=completed_at,
        )

    def fail_run(
        self,
        run_id: str,
        *,
        failed_at: str,
    ) -> SimulationRunRecord:
        return self._transition(
            run_id,
            expected_statuses=frozenset({
                "initialized",
                "active",
                "interrupted",
            }),
            target_status="failed",
            occurred_at=failed_at,
        )
