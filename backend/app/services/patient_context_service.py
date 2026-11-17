"""Application service for constructing authorized Patient Agent context."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from app.persistence.database import DatabaseManager
from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.character_personality import (
    CharacterPersonalityRepository,
)
from app.persistence.repositories.character_runtime import RunCharacterRepository
from app.persistence.repositories.memory import MemoryRepository
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.persistence.repositories.sessions import SessionRepository
from app.persistence.repositories.simulation_runs import (
    SimulationRunRepository,
)
from app.persistence.repositories.state import StateRepository
from app.services.disclosures import (
    DisclosureService,
    DisclosureServiceError,
)
from app.services.patient_context import (
    PATIENT_MEMORY_INFORMATION_CLASSES,
    STATE_VARIABLES,
    CharacterPersonalityContext,
    FrozenJSONObject,
    PatientCharacterState,
    PatientCharacterStateVariable,
    PatientCaseFact,
    PatientContext,
    PatientIdentity,
    PatientMemoryItem,
    PatientState,
    PatientStateVariable,
    PatientTranscriptMessage,
    RestrictedProfileContext,
    freeze_json_object,
    parse_json_array,
    parse_json_object,
)


class PatientContextServiceError(RuntimeError):
    """Base exception for PatientContextService operations."""


class PatientContextRunNotFoundError(PatientContextServiceError):
    """The requested simulation run does not exist."""


class PatientContextSessionNotFoundError(PatientContextServiceError):
    """The requested session does not belong to the simulation run."""


class PatientContextMessageNotFoundError(PatientContextServiceError):
    """The requested persisted therapist message does not exist."""


class PatientContextRunNotActiveError(PatientContextServiceError):
    """The simulation run is not active."""


class PatientContextSessionNotActiveError(PatientContextServiceError):
    """The requested session is not active."""


class PatientContextTurnConflictError(PatientContextServiceError):
    """The requested therapist turn is no longer the current turn."""


class PatientContextDataIntegrityError(PatientContextServiceError):
    """Persisted data does not satisfy the PatientContext contract."""


class PatientContextStateIntegrityError(PatientContextDataIntegrityError):
    """The canonical state snapshot chain is missing or inconsistent."""


class PatientContextService:
    """Build an immutable, authorized context for the Patient Agent.

    This service is the only application boundary that combines operational
    simulation data with restricted synthetic case-vault data.

    It performs read-only operations. It does not update canonical state,
    disclosures, transcript messages, memory records, or run/session status.
    It returns typed DTOs and never returns database connections or
    repository instances.
    """

    _PAGE_SIZE = 200

    def __init__(
        self,
        database_manager: DatabaseManager,
        *,
        max_transcript_messages: int = 80,
        max_memory_items: int = 40,
    ) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")

        for name, value in (
            ("max_transcript_messages", max_transcript_messages),
            ("max_memory_items", max_memory_items),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 200
            ):
                raise ValueError(
                    f"{name} must be an integer between 1 and 200."
                )

        self._database_manager = database_manager
        self._disclosure_service = DisclosureService(database_manager)
        self._max_transcript_messages = max_transcript_messages
        self._max_memory_items = max_memory_items

    @staticmethod
    def _require_text(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")

    @staticmethod
    def _row_dict(row: sqlite3.Row) -> dict[str, object]:
        return {
            key: row[key]
            for key in row.keys()
        }

    @classmethod
    def _list_all_messages(
        cls,
        repository: MessageRepository,
        session_id: str,
    ) -> list[sqlite3.Row]:
        """Retrieve every message without silently truncating pagination."""

        result: list[sqlite3.Row] = []
        offset = 0

        while True:
            page = repository.list_by_session(
                session_id,
                limit=cls._PAGE_SIZE,
                offset=offset,
            )

            result.extend(page)

            if len(page) < cls._PAGE_SIZE:
                break

            offset += cls._PAGE_SIZE

        return result

    @staticmethod
    def _message_from_row(
        row: sqlite3.Row,
        session_number: int,
    ) -> PatientTranscriptMessage:
        return PatientTranscriptMessage(
            message_id=row["message_id"],
            session_id=row["session_id"],
            session_number=session_number,
            sequence_number=row["sequence_number"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _load_current_state(
        connection: sqlite3.Connection,
        run_id: str,
        session_numbers: dict[str, int],
        current_session_number: int,
    ) -> PatientState:
        """Resolve and validate the unique head of the snapshot chain."""

        rows = connection.execute(
            """
            SELECT *
            FROM state_snapshots
            WHERE run_id = ?
            ORDER BY created_at, snapshot_id
            """,
            (run_id,),
        ).fetchall()

        if not rows:
            raise PatientContextStateIntegrityError(
                "The simulation run has no canonical state snapshot."
            )

        snapshots_by_id = {
            row["snapshot_id"]: row
            for row in rows
        }

        if len(snapshots_by_id) != len(rows):
            raise PatientContextStateIntegrityError(
                "State snapshot identifiers are not unique."
            )

        referenced_parents = {
            row["previous_snapshot_id"]
            for row in rows
            if row["previous_snapshot_id"] is not None
        }

        leaves = [
            row
            for row in rows
            if row["snapshot_id"] not in referenced_parents
        ]

        if len(leaves) != 1:
            raise PatientContextStateIntegrityError(
                "The state snapshot chain must have exactly one current head."
            )

        visited: set[str] = set()
        reverse_chain: list[sqlite3.Row] = []
        cursor = leaves[0]

        while cursor is not None:
            snapshot_id = cursor["snapshot_id"]

            if snapshot_id in visited:
                raise PatientContextStateIntegrityError(
                    "The state snapshot chain contains a cycle."
                )

            visited.add(snapshot_id)
            reverse_chain.append(cursor)

            previous_id = cursor["previous_snapshot_id"]

            if previous_id is None:
                break

            previous = snapshots_by_id.get(previous_id)

            if previous is None:
                raise PatientContextStateIntegrityError(
                    "A state snapshot references a missing predecessor."
                )

            cursor = previous

        if len(visited) != len(rows):
            raise PatientContextStateIntegrityError(
                "The state snapshot records do not form one complete chain."
            )

        # Validate the chain from its root to its current head.
        # Session numbers may advance or remain equal, never regress.
        chain = tuple(reversed(reverse_chain))
        previous_session_number = 0

        for index, snapshot in enumerate(chain):
            snapshot_session_id = snapshot["session_id"]

            if snapshot_session_id is None:
                if index != 0:
                    raise PatientContextStateIntegrityError(
                        "Only the root state snapshot may omit a session."
                    )
                continue

            snapshot_session_number = session_numbers.get(
                snapshot_session_id
            )

            if snapshot_session_number is None:
                raise PatientContextStateIntegrityError(
                    "A state snapshot references a session outside this run."
                )

            if snapshot_session_number < previous_session_number:
                raise PatientContextStateIntegrityError(
                    "The state snapshot chain moves backwards across sessions."
                )

            if snapshot_session_number > current_session_number:
                raise PatientContextStateIntegrityError(
                    "A state snapshot belongs to a future session."
                )

            previous_session_number = snapshot_session_number

        current = leaves[0]

        values = StateRepository(connection).get_snapshot_values(
            current["snapshot_id"]
        )

        if set(values) != STATE_VARIABLES:
            raise PatientContextStateIntegrityError(
                "The current state snapshot does not contain every required variable."
            )

        try:
            return PatientState(
                snapshot_id=current["snapshot_id"],
                state_schema_version=current["state_schema_version"],
                values=tuple(
                    PatientStateVariable(
                        name=name,
                        value=values[name],
                    )
                    for name in sorted(STATE_VARIABLES)
                ),
            )
        except (TypeError, ValueError) as exc:
            raise PatientContextStateIntegrityError(
                "The current state snapshot violates the state contract."
            ) from exc

    @staticmethod
    def _load_public_identity(
        case_row: sqlite3.Row,
        profile_row: sqlite3.Row,
    ) -> PatientIdentity:
        try:
            parsed_concerns = parse_json_array(
                profile_row["presenting_concerns"],
                "presenting_concerns",
            )

            if not all(
                isinstance(item, str) and item.strip()
                for item in parsed_concerns
            ):
                raise ValueError(
                    "Presenting concerns must be non-empty strings."
                )

            return PatientIdentity(
                display_name=case_row["display_name"],
                age=profile_row["age"],
                occupation=profile_row["occupation"],
                presenting_concerns=tuple(parsed_concerns),
                initial_disclosure=profile_row["initial_disclosure"],
            )
        except (TypeError, ValueError) as exc:
            raise PatientContextDataIntegrityError(
                "The public case identity violates its data contract."
            ) from exc

    @staticmethod
    def _load_character_state(
        connection: sqlite3.Connection,
        run_id: str,
        session_numbers: dict[str, int],
        current_session_number: int,
    ) -> PatientCharacterState:
        """Load and validate the unique run-local character-state chain."""

        rows = connection.execute(
            """
            SELECT *
            FROM character_state_snapshots
            WHERE run_id = ?
            ORDER BY created_at, snapshot_id
            """,
            (run_id,),
        ).fetchall()

        if not rows:
            raise PatientContextStateIntegrityError(
                "The run has no character-state snapshot."
            )

        snapshots = {row["snapshot_id"]: row for row in rows}

        if len(snapshots) != len(rows):
            raise PatientContextStateIntegrityError(
                "Character-state snapshot identifiers are duplicated."
            )

        referenced = {
            row["previous_snapshot_id"]
            for row in rows
            if row["previous_snapshot_id"] is not None
        }

        leaves = [
            row for row in rows
            if row["snapshot_id"] not in referenced
        ]

        if len(leaves) != 1:
            raise PatientContextStateIntegrityError(
                "Character-state history must have exactly one current head."
            )

        visited = set()
        reverse_chain = []
        cursor = leaves[0]

        while cursor is not None:
            snapshot_id = cursor["snapshot_id"]

            if snapshot_id in visited:
                raise PatientContextStateIntegrityError(
                    "Character-state history contains a cycle."
                )

            visited.add(snapshot_id)
            reverse_chain.append(cursor)

            previous_id = cursor["previous_snapshot_id"]
            cursor = snapshots.get(previous_id) if previous_id else None

            if previous_id is not None and cursor is None:
                raise PatientContextStateIntegrityError(
                    "Character-state history references a missing predecessor."
                )

        if len(visited) != len(rows):
            raise PatientContextStateIntegrityError(
                "Character-state records do not form one complete chain."
            )

        previous_session_number = 0

        for snapshot in reversed(reverse_chain):
            session_id = snapshot["session_id"]

            if session_id is None:
                continue

            number = session_numbers.get(session_id)

            if number is None or number > current_session_number:
                raise PatientContextStateIntegrityError(
                    "Character-state snapshot references an unavailable session."
                )

            if number < previous_session_number:
                raise PatientContextStateIntegrityError(
                    "Character-state history moves backwards across sessions."
                )

            previous_session_number = number

        latest = leaves[0]

        value_rows = connection.execute(
            """
            SELECT variable_name, variable_value
            FROM character_state_snapshot_values
            WHERE snapshot_id = ?
            ORDER BY variable_name
            """,
            (latest["snapshot_id"],),
        ).fetchall()

        try:
            values = tuple(
                PatientCharacterStateVariable(
                    name=row["variable_name"],
                    value=row["variable_value"],
                )
                for row in value_rows
            )

            return PatientCharacterState(
                snapshot_id=latest["snapshot_id"],
                state_schema_version=latest["state_schema_version"],
                values=values,
            )
        except (TypeError, ValueError) as exc:
            raise PatientContextStateIntegrityError(
                "The current character-state snapshot violates its contract."
            ) from exc

    @staticmethod
    def _load_memory_items(
        connection: sqlite3.Connection,
        run_id: str,
        session_numbers: dict[str, int],
        current_session_number: int,
        current_therapist_message: PatientTranscriptMessage,
        messages_by_id: dict[str, sqlite3.Row],
        max_items: int,
    ) -> tuple[PatientMemoryItem, ...]:
        """Select only allowed, evidence-linked longitudinal memory."""

        memory_repository = MemoryRepository(connection)
        items: list[tuple[str, str, PatientMemoryItem]] = []

        rows = memory_repository.list_by_run(
            run_id,
            status="active",
        )

        for row in rows:
            information_class = row["information_class"]

            # Hypotheses and structured observations are not patient knowledge.
            if information_class not in PATIENT_MEMORY_INFORMATION_CLASSES:
                continue

            evidence_rows = memory_repository.list_evidence(
                row["memory_id"]
            )

            if not evidence_rows:
                raise PatientContextDataIntegrityError(
                    "An authorized memory item has no transcript evidence."
                )

            evidence_positions: list[tuple[int, int, str]] = []
            has_patient_authored_evidence = False

            for evidence in evidence_rows:
                message_id = evidence["message_id"]
                source_message = messages_by_id.get(message_id)

                if source_message is None:
                    raise PatientContextDataIntegrityError(
                        "A memory item references a message outside the accessible run history."
                    )

                if source_message["role"] == "patient":
                    has_patient_authored_evidence = True

                source_session_id = source_message["session_id"]

                source_session_number = session_numbers.get(
                    source_session_id
                )

                if source_session_number is None:
                    raise PatientContextDataIntegrityError(
                        "A memory evidence message belongs to an unknown session."
                    )

                if source_session_number > current_session_number:
                    raise PatientContextDataIntegrityError(
                        "Memory evidence references a future session."
                    )

                if source_session_number == current_session_number:
                    if (
                        source_message["sequence_number"]
                        >= current_therapist_message.sequence_number
                    ):
                        raise PatientContextDataIntegrityError(
                            "Memory evidence references the current or a later therapist turn."
                        )

                evidence_positions.append(
                    (
                        source_session_number,
                        source_message["sequence_number"],
                        message_id,
                    )
                )

            if (
                information_class == "explicit_disclosure"
                and not has_patient_authored_evidence
            ):
                raise PatientContextDataIntegrityError(
                    "Explicit-disclosure memory requires at least one "
                    "patient-authored transcript evidence message."
                )

            source_session_id = row["source_session_id"]

            if source_session_id is not None:
                source_session_number = session_numbers.get(
                    source_session_id
                )

                if (
                    source_session_number is None
                    or source_session_number > current_session_number
                ):
                    raise PatientContextDataIntegrityError(
                        "A memory item references a session outside the available history."
                    )

            evidence_positions.sort()

            try:
                item = PatientMemoryItem(
                    memory_id=row["memory_id"],
                    source_session_id=source_session_id,
                    memory_type=row["memory_type"],
                    information_class=information_class,
                    content=row["content"],
                    source_message_ids=tuple(
                        position[2]
                        for position in evidence_positions
                    ),
                    confidence=row["confidence"],
                    memory_version=row["memory_version"],
                    memory_scope=row["memory_scope"],
                )
            except (TypeError, ValueError) as exc:
                raise PatientContextDataIntegrityError(
                    "An authorized memory item violates its data contract."
                ) from exc

            items.append(
                (
                    row["created_at"],
                    row["memory_id"],
                    item,
                )
            )

        items.sort(key=lambda item: (item[0], item[1]))

        return tuple(
            item[2]
            for item in items[-max_items:]
        )

    def _load_operational_data(
        self,
        run_id: str,
        session_id: str,
        therapist_message_id: str,
    ) -> dict[str, object]:
        """Load run, session, messages, state, and memory from the operational DB."""

        with self._database_manager.connection(
            "operational"
        ) as connection:
            connection.execute("BEGIN")

            runs = SimulationRunRepository(connection)
            run_row = runs.get_run(run_id)

            if run_row is None:
                raise PatientContextRunNotFoundError(
                    "The requested simulation run does not exist."
                )

            if run_row["status"] != "active":
                raise PatientContextRunNotActiveError(
                    "Patient context can only be built for an active run."
                )

            cases = CaseRepository(connection)
            case_row = cases.get_case(run_row["case_id"])

            if case_row is None:
                raise PatientContextDataIntegrityError(
                    "The simulation run references a missing case."
                )

            version_row = cases.get_case_version_for_case(
                run_row["case_id"],
                run_row["case_version_id"],
            )

            if version_row is None:
                raise PatientContextDataIntegrityError(
                    "The simulation run references a missing case version."
                )

            if (
                version_row["modality"] != run_row["modality"]
                or version_row["language"] != run_row["language"]
            ):
                raise PatientContextDataIntegrityError(
                    "Run modality or language does not match its case version."
                )

            public_profile_row = cases.get_public_profile(
                run_row["case_version_id"]
            )

            if public_profile_row is None:
                raise PatientContextDataIntegrityError(
                    "The case version has no public identity profile."
                )

            session_repository = SessionRepository(connection)
            sessions = session_repository.list_by_run(run_id)

            if not sessions:
                raise PatientContextSessionNotFoundError(
                    "The simulation run has no sessions."
                )

            session_numbers_in_order = [
                row["session_number"]
                for row in sessions
            ]

            if session_numbers_in_order != list(
                range(1, len(sessions) + 1)
            ):
                raise PatientContextDataIntegrityError(
                    "The session sequence for this run is not continuous."
                )

            sessions_by_id = {
                row["session_id"]: row
                for row in sessions
            }

            current_session = sessions_by_id.get(session_id)

            if current_session is None:
                raise PatientContextSessionNotFoundError(
                    "The requested session does not belong to this run."
                )

            current_session_number = current_session["session_number"]

            if sessions[-1]["session_id"] != session_id:
                raise PatientContextTurnConflictError(
                    "The requested session is not the current run session."
                )

            if current_session["status"] != "active":
                raise PatientContextSessionNotActiveError(
                    "Patient context can only be built for an active session."
                )

            for previous_session in sessions[:-1]:
                if previous_session["status"] != "completed":
                    raise PatientContextTurnConflictError(
                        "Every previous session must be completed."
                    )

            session_numbers = {
                row["session_id"]: row["session_number"]
                for row in sessions
            }

            message_repository = MessageRepository(connection)
            messages_by_session: dict[str, list[sqlite3.Row]] = {}
            messages_by_id: dict[str, sqlite3.Row] = {}

            for session in sessions:
                session_messages = self._list_all_messages(
                    message_repository,
                    session["session_id"],
                )

                messages_by_session[session["session_id"]] = session_messages

                for message in session_messages:
                    message_id = message["message_id"]

                    if message_id in messages_by_id:
                        raise PatientContextDataIntegrityError(
                            "A transcript message identifier is duplicated."
                        )

                    messages_by_id[message_id] = message

            therapist_row = message_repository.get_message(
                therapist_message_id
            )

            if therapist_row is None:
                raise PatientContextMessageNotFoundError(
                    "The requested therapist message does not exist."
                )

            if (
                therapist_row["session_id"] != session_id
                or therapist_row["role"] != "therapist"
            ):
                raise PatientContextMessageNotFoundError(
                    "The requested message is not a therapist message in this session."
                )

            current_session_messages = messages_by_session[session_id]

            if not any(
                row["message_id"] == therapist_message_id
                for row in current_session_messages
            ):
                raise PatientContextDataIntegrityError(
                    "The current therapist message is missing from its session transcript."
                )

            latest_sequence = max(
                (
                    row["sequence_number"]
                    for row in current_session_messages
                ),
                default=0,
            )

            if latest_sequence != therapist_row["sequence_number"]:
                raise PatientContextTurnConflictError(
                    "The therapist message is no longer the latest message in the session."
                )

            therapist_message = self._message_from_row(
                therapist_row,
                current_session_number,
            )

            transcript_rows: list[tuple[int, sqlite3.Row]] = []

            for session in sessions:
                number = session["session_number"]

                for message in messages_by_session[session["session_id"]]:
                    if number < current_session_number:
                        transcript_rows.append((number, message))
                    elif (
                        number == current_session_number
                        and message["sequence_number"]
                        < therapist_row["sequence_number"]
                    ):
                        transcript_rows.append((number, message))

            transcript_rows.sort(
                key=lambda item: (
                    item[0],
                    item[1]["sequence_number"],
                )
            )

            transcript_rows = transcript_rows[
                -self._max_transcript_messages:
            ]

            try:
                recent_transcript = tuple(
                    self._message_from_row(message, number)
                    for number, message in transcript_rows
                )
            except (TypeError, ValueError) as exc:
                raise PatientContextDataIntegrityError(
                    "The recent transcript violates its data contract."
                ) from exc

            patient_state = self._load_current_state(
                connection,
                run_id,
                session_numbers,
                current_session_number,
            )

            character_repository = RunCharacterRepository(connection)
            profile_reference_row = character_repository.get_profile_snapshot(
                run_id
            )

            if profile_reference_row is None:
                raise PatientContextDataIntegrityError(
                    "The run has no immutable character-profile reference."
                )

            profile_reference = self._row_dict(profile_reference_row)

            if (
                profile_reference["case_id"] != run_row["case_id"]
                or profile_reference["case_version_id"] != run_row["case_version_id"]
            ):
                raise PatientContextDataIntegrityError(
                    "Character-profile reference belongs to another case version."
                )

            profile_status = profile_reference["profile_status"]

            if profile_status == "unconfigured":
                if any(
                    profile_reference[key] is not None
                    for key in (
                        "personality_profile_id",
                        "profile_version",
                        "theory_bundle_version",
                        "source_content_hash",
                    )
                ):
                    raise PatientContextDataIntegrityError(
                        "Unconfigured character reference contains profile metadata."
                    )
            elif profile_status == "active":
                if any(
                    profile_reference[key] is None
                    for key in (
                        "personality_profile_id",
                        "profile_version",
                        "theory_bundle_version",
                        "source_content_hash",
                    )
                ):
                    raise PatientContextDataIntegrityError(
                        "Active character reference is incomplete."
                    )

                source_hash = profile_reference["source_content_hash"]
                if (
                    not isinstance(source_hash, str)
                    or len(source_hash) != 64
                    or any(c not in "0123456789abcdef" for c in source_hash)
                ):
                    raise PatientContextDataIntegrityError(
                        "Character-profile reference has an invalid content hash."
                    )
            else:
                raise PatientContextDataIntegrityError(
                    "Character-profile reference has an unknown status."
                )

            character_state = self._load_character_state(
                connection,
                run_id,
                session_numbers,
                current_session_number,
            )

            memory_items = self._load_memory_items(
                connection,
                run_id,
                session_numbers,
                current_session_number,
                therapist_message,
                messages_by_id,
                self._max_memory_items,
            )

            public_identity = self._load_public_identity(
                case_row,
                public_profile_row,
            )

            result = {
                "run": self._row_dict(run_row),
                "session": self._row_dict(current_session),
                "public_identity": public_identity,
                "therapist_message": therapist_message,
                "recent_transcript": recent_transcript,
                "current_state": patient_state,
                "character_state": character_state,
                "character_profile_reference": profile_reference,
                "longitudinal_memory": memory_items,
            }

            connection.commit()

            return result

    def _load_restricted_data(
        self,
        case_id: str,
        case_version_id: str,
    ) -> tuple[RestrictedProfileContext, tuple[dict[str, object], ...]]:
        """Read restricted case profile and all facts for the exact version."""

        with self._database_manager.connection(
            "restricted"
        ) as connection:
            connection.execute("BEGIN")

            repository = RestrictedCaseRepository(connection)

            profile_row = repository.get_profile(
                case_id,
                case_version_id,
            )

            if profile_row is None:
                raise PatientContextDataIntegrityError(
                    "The matching restricted case profile does not exist."
                )

            fact_rows: list[sqlite3.Row] = []
            offset = 0

            while True:
                page = repository.list_facts(
                    case_id,
                    case_version_id,
                    limit=self._PAGE_SIZE,
                    offset=offset,
                )

                fact_rows.extend(page)

                if len(page) < self._PAGE_SIZE:
                    break

                offset += self._PAGE_SIZE

            profile_data = self._row_dict(profile_row)
            facts_data = tuple(
                self._row_dict(row)
                for row in fact_rows
            )

            connection.commit()

        try:
            restricted_profile = RestrictedProfileContext(
                clinical_formulation=parse_json_object(
                    profile_data["clinical_formulation"],
                    "clinical_formulation",
                ),
                relevant_personal_history=parse_json_object(
                    profile_data["relevant_personal_history"],
                    "relevant_personal_history",
                ),
                maintaining_factors=parse_json_array(
                    profile_data["maintaining_factors"],
                    "maintaining_factors",
                ),
                avoidance_patterns=parse_json_array(
                    profile_data["avoidance_patterns"],
                    "avoidance_patterns",
                ),
                hypothesized_functions=parse_json_object(
                    profile_data["hypothesized_functions"],
                    "hypothesized_functions",
                ),
                initial_safety_baseline=parse_json_object(
                    profile_data["initial_safety_baseline"],
                    "initial_safety_baseline",
                ),
                patient_simulation_instructions=profile_data[
                    "patient_simulation_instructions"
                ],
            )
        except (TypeError, ValueError) as exc:
            raise PatientContextDataIntegrityError(
                "The restricted case profile violates its data contract."
            ) from exc

        return restricted_profile, facts_data

    def _load_character_personality(
        self,
        run: dict[str, object],
        reference: dict[str, object],
    ) -> CharacterPersonalityContext:
        """Load the exact immutable personality version captured by this run."""

        if reference["profile_status"] == "unconfigured":
            return CharacterPersonalityContext(
                configured=False,
                profile_version=None,
                profile_data=FrozenJSONObject(()),
            )

        profile_id = reference["personality_profile_id"]

        with self._database_manager.connection("restricted") as connection:
            repository = CharacterPersonalityRepository(connection)
            row = repository.get_profile(profile_id)

        if row is None:
            raise PatientContextDataIntegrityError(
                "The run's referenced personality profile no longer exists."
            )

        if (
            row["case_id"] != run["case_id"]
            or row["case_version_id"] != run["case_version_id"]
            or row["personality_profile_id"] != profile_id
            or row["profile_version"] != reference["profile_version"]
            or row["character_id"] != reference["character_id"]
            or row["personality_schema_version"]
                != reference["personality_schema_version"]
            or row["theory_bundle_version"] != reference["theory_bundle_version"]
            or row["content_hash"] != reference["source_content_hash"]
        ):
            raise PatientContextDataIntegrityError(
                "The referenced personality profile does not match the run snapshot."
            )

        # A profile can be retired after a run has captured it. Historical runs
        # must continue using that exact version.
        if row["authoring_status"] not in {"active", "retired"}:
            raise PatientContextDataIntegrityError(
                "The run references a personality profile that was never active."
            )

        raw_profile = row["profile_json"]

        if not isinstance(raw_profile, str):
            raise PatientContextDataIntegrityError(
                "Personality profile content is not text."
            )

        actual_hash = hashlib.sha256(raw_profile.encode("utf-8")).hexdigest()

        if actual_hash != reference["source_content_hash"]:
            raise PatientContextDataIntegrityError(
                "Personality profile content failed its integrity check."
            )

        try:
            document = json.loads(raw_profile)
        except (TypeError, json.JSONDecodeError) as exc:
            raise PatientContextDataIntegrityError(
                "Personality profile contains invalid JSON."
            ) from exc

        expected_identity = {
            "personality_profile_id": profile_id,
            "character_id": reference["character_id"],
            "case_id": run["case_id"],
            "case_version_id": run["case_version_id"],
            "profile_version": reference["profile_version"],
        }

        if not isinstance(document, dict) or any(
            document.get(key) != value
            for key, value in expected_identity.items()
        ):
            raise PatientContextDataIntegrityError(
                "Personality profile JSON identity is inconsistent."
            )

        allowed_sections = (
            "big_five",
            "attachment",
            "interpersonal",
            "schema_themes",
            "emotion_regulation_patterns",
            "value_hypotheses",
            "communication_style",
        )

        excluded_keys = {
            "personality_profile_id",
            "character_id",
            "case_id",
            "case_version_id",
            "profile_version",
            "personality_schema_version",
            "theory_bundle_version",
            "initial_state",
            "authoring_notes",
            "source_refs",
            "theme_id",
            "pattern_id",
        }

        def curate(value):
            if isinstance(value, dict):
                return {
                    key: curate(item)
                    for key, item in value.items()
                    if key not in excluded_keys
                }

            if isinstance(value, list):
                return [curate(item) for item in value]

            return value

        curated = {
            key: curate(document[key])
            for key in allowed_sections
            if key in document
            and document[key] not in (None, [], {})
        }

        try:
            return CharacterPersonalityContext(
                configured=True,
                profile_version=reference["profile_version"],
                profile_data=freeze_json_object(
                    curated,
                    "character_personality",
                ),
            )
        except (TypeError, ValueError) as exc:
            raise PatientContextDataIntegrityError(
                "Curated personality data violates its context contract."
            ) from exc

    @staticmethod
    def _build_case_facts(
        case_rows: tuple[dict[str, object], ...],
        disclosure_records: tuple[object, ...],
        run_id: str,
        case_id: str,
        case_version_id: str,
    ) -> tuple[PatientCaseFact, ...]:
        """Join restricted fact content with its validated disclosure metadata."""

        facts_by_id = {
            row["case_fact_id"]: row
            for row in case_rows
        }

        if len(facts_by_id) != len(case_rows):
            raise PatientContextDataIntegrityError(
                "Restricted case-fact identifiers are duplicated."
            )

        disclosures_by_id = {
            record.case_fact_id: record
            for record in disclosure_records
        }

        if len(disclosures_by_id) != len(disclosure_records):
            raise PatientContextDataIntegrityError(
                "Disclosure identifiers are duplicated."
            )

        if set(facts_by_id) != set(disclosures_by_id):
            raise PatientContextDataIntegrityError(
                "Every case fact must have exactly one disclosure record."
            )

        result: list[PatientCaseFact] = []

        for case_fact_id, fact in facts_by_id.items():
            disclosure = disclosures_by_id[case_fact_id]

            if (
                disclosure.run_id != run_id
                or disclosure.case_id != case_id
                or disclosure.case_version_id != case_version_id
                or disclosure.case_fact_id != case_fact_id
            ):
                raise PatientContextDataIntegrityError(
                    "Disclosure identity does not match its case fact and run."
                )

            if (
                disclosure.information_class != fact["information_class"]
                or disclosure.disclosure_policy != fact["disclosure_policy"]
            ):
                raise PatientContextDataIntegrityError(
                    "Disclosure metadata does not match the restricted case fact."
                )

            try:
                relevance_raw = fact["relevance_metadata"]

                relevance_metadata = (
                    None
                    if relevance_raw is None
                    else parse_json_object(
                        relevance_raw,
                        "relevance_metadata",
                    )
                )

                result.append(
                    PatientCaseFact(
                        case_fact_id=case_fact_id,
                        fact_category=fact["fact_category"],
                        information_class=fact["information_class"],
                        content=fact["content"],
                        disclosure_policy=fact["disclosure_policy"],
                        disclosure_status=disclosure.disclosure_status,
                        relevance_metadata=relevance_metadata,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise PatientContextDataIntegrityError(
                    "A restricted case fact violates its PatientContext contract."
                ) from exc

        result.sort(key=lambda item: item.case_fact_id)

        return tuple(result)

    def _verify_current_turn(
        self,
        run_id: str,
        session_id: str,
        therapist_message_id: str,
    ) -> None:
        """Recheck lifecycle and message ordering after cross-database reads."""

        with self._database_manager.connection(
            "operational"
        ) as connection:
            run = SimulationRunRepository(connection).get_run(run_id)

            if run is None:
                raise PatientContextRunNotFoundError(
                    "The simulation run no longer exists."
                )

            if run["status"] != "active":
                raise PatientContextRunNotActiveError(
                    "The simulation run is no longer active."
                )

            sessions = SessionRepository(connection).list_by_run(run_id)

            if not sessions or sessions[-1]["session_id"] != session_id:
                raise PatientContextTurnConflictError(
                    "The requested session is no longer the current run session."
                )

            session = SessionRepository(connection).get_session(session_id)

            if session is None:
                raise PatientContextSessionNotFoundError(
                    "The requested session no longer exists."
                )

            if session["status"] != "active":
                raise PatientContextSessionNotActiveError(
                    "The requested session is no longer active."
                )

            message = MessageRepository(connection).get_message(
                therapist_message_id
            )

            if (
                message is None
                or message["session_id"] != session_id
                or message["role"] != "therapist"
            ):
                raise PatientContextTurnConflictError(
                    "The requested therapist message is no longer valid."
                )

            latest_sequence = connection.execute(
                """
                SELECT MAX(sequence_number)
                FROM messages
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()[0]

            if latest_sequence != message["sequence_number"]:
                raise PatientContextTurnConflictError(
                    "A newer message was persisted while PatientContext was being built."
                )

    def build_patient_context(
        self,
        run_id: str,
        session_id: str,
        therapist_message_id: str,
    ) -> PatientContext:
        """Build the context for one exact, already-persisted therapist turn.

        The therapist message is retrieved by ID from the operational
        transcript. Arbitrary caller-supplied message text is never accepted.
        """

        self._require_text(run_id, "run_id")
        self._require_text(session_id, "session_id")
        self._require_text(therapist_message_id, "therapist_message_id")

        operational = self._load_operational_data(
            run_id,
            session_id,
            therapist_message_id,
        )

        run = operational["run"]

        restricted_profile, case_rows = self._load_restricted_data(
            run["case_id"],
            run["case_version_id"],
        )

        character_personality = self._load_character_personality(
            run,
            operational["character_profile_reference"],
        )

        try:
            disclosure_records = self._disclosure_service.list_disclosures(
                run_id
            )
        except DisclosureServiceError as exc:
            raise PatientContextDataIntegrityError(
                "The run disclosure ledger could not be validated."
            ) from exc

        case_facts = self._build_case_facts(
            case_rows,
            disclosure_records,
            run_id,
            run["case_id"],
            run["case_version_id"],
        )

        try:
            result = PatientContext(
                case_id=run["case_id"],
                case_version_id=run["case_version_id"],
                run_id=run_id,
                session_id=session_id,
                session_number=operational["session"]["session_number"],
                language=run["language"],
                modality=run["modality"],
                public_identity=operational["public_identity"],
                restricted_profile=restricted_profile,
                relevant_case_facts=case_facts,
                current_state=operational["current_state"],
                character_personality=character_personality,
                character_state=operational["character_state"],
                longitudinal_memory=operational["longitudinal_memory"],
                recent_transcript=operational["recent_transcript"],
                therapist_message=operational["therapist_message"],
            )
        except (TypeError, ValueError) as exc:
            raise PatientContextDataIntegrityError(
                "The assembled PatientContext violates its contract."
            ) from exc

        self._verify_current_turn(
            run_id,
            session_id,
            therapist_message_id,
        )

        return result
