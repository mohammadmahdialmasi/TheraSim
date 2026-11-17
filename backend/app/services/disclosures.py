"""Application service for evidence-based disclosure management."""

from dataclasses import dataclass
import sqlite3
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.disclosures import (
    DisclosureRepository,
)
from app.persistence.repositories.operations import AuditRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)


class DisclosureServiceError(Exception):
    """Base exception for disclosure application operations."""


class DisclosureRunNotFoundError(DisclosureServiceError):
    """The simulation run does not exist."""


class DisclosureNotFoundError(DisclosureServiceError):
    """The requested disclosure does not exist."""


class DisclosureDataIntegrityError(DisclosureServiceError):
    """Operational disclosure metadata does not match the case vault."""


class DisclosurePolicyViolationError(DisclosureServiceError):
    """The case-fact disclosure policy does not permit the requested action."""


class DisclosureTransitionError(DisclosureServiceError):
    """The requested disclosure status transition is not permitted."""


class DisclosureEvidenceError(DisclosureServiceError):
    """The supplied patient-message evidence is invalid."""


class DisclosureOperationConflictError(DisclosureServiceError):
    """An operation identifier was reused for a different operation."""


class DisclosureConflictError(DisclosureServiceError):
    """A disclosure persistence constraint was violated."""


@dataclass(frozen=True, slots=True)
class DisclosureRecord:
    """Safe disclosure metadata without restricted fact content."""

    disclosure_id: str
    run_id: str
    case_id: str
    case_version_id: str
    case_fact_id: str
    disclosure_status: str
    source_message_id: str | None
    evidence_start_offset: int | None
    evidence_end_offset: int | None
    validation_method: str
    validation_notes: str | None
    created_at: str
    updated_at: str
    fact_category: str
    information_class: str
    disclosure_policy: str


class DisclosureService:
    """Coordinates disclosure decisions across the two SQLite databases.

    Restricted fact content is read only for validation.
    It is never included in returned disclosure DTOs.

    The service owns operational transactions. It does not expose database
    connections or repository objects to agents.
    """

    _ALLOWED_TRANSITIONS = {
        "not_disclosed": frozenset({
            "candidate_disclosed",
            "requires_review",
        }),
        "candidate_disclosed": frozenset({
            "confirmed_disclosed",
            "requires_review",
            "not_disclosed",
        }),
        "requires_review": frozenset({
            "candidate_disclosed",
            "confirmed_disclosed",
            "not_disclosed",
        }),
        "confirmed_disclosed": frozenset({
            "requires_review",
        }),
    }

    _DISCLOSABLE_POLICIES = frozenset({
        "initial_disclosure",
        "contextually_disclosable",
    })

    def __init__(self, database_manager: DatabaseManager) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")

        self._database_manager = database_manager

    @staticmethod
    def _require_text(value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string.")

    @staticmethod
    def _validate_evidence_offsets(
        source_message_id: str,
        start_offset: int | None,
        end_offset: int | None,
    ) -> None:
        DisclosureService._require_text(
            source_message_id,
            "source_message_id",
        )

        if start_offset is None or end_offset is None:
            raise DisclosureEvidenceError(
                "Both evidence offsets are required."
            )

        if (
            isinstance(start_offset, bool)
            or not isinstance(start_offset, int)
            or isinstance(end_offset, bool)
            or not isinstance(end_offset, int)
        ):
            raise DisclosureEvidenceError(
                "Evidence offsets must be integers."
            )

        if start_offset < 0 or end_offset <= start_offset:
            raise DisclosureEvidenceError(
                "Evidence must identify a non-empty text range."
            )

    @staticmethod
    def _from_rows(
        disclosure: sqlite3.Row,
        fact: sqlite3.Row,
    ) -> DisclosureRecord:
        return DisclosureRecord(
            disclosure_id=disclosure["disclosure_id"],
            run_id=disclosure["run_id"],
            case_id=disclosure["case_id"],
            case_version_id=disclosure["case_version_id"],
            case_fact_id=disclosure["case_fact_id"],
            disclosure_status=disclosure["disclosure_status"],
            source_message_id=disclosure["source_message_id"],
            evidence_start_offset=disclosure["evidence_start_offset"],
            evidence_end_offset=disclosure["evidence_end_offset"],
            validation_method=disclosure["validation_method"],
            validation_notes=disclosure["validation_notes"],
            created_at=disclosure["created_at"],
            updated_at=disclosure["updated_at"],
            fact_category=fact["fact_category"],
            information_class=fact["information_class"],
            disclosure_policy=fact["disclosure_policy"],
        )

    def _get_run_identity(self, run_id: str) -> dict[str, str]:
        self._require_text(run_id, "run_id")

        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = connection.execute(
                """
                SELECT case_id, case_version_id, status
                FROM simulation_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            raise DisclosureRunNotFoundError(
                "The simulation run does not exist."
            )

        return {
            "case_id": row["case_id"],
            "case_version_id": row["case_version_id"],
            "status": row["status"],
        }

    def _get_restricted_fact(
        self,
        case_id: str,
        case_version_id: str,
        case_fact_id: str,
    ) -> sqlite3.Row:
        with self._database_manager.connection(
            "restricted"
        ) as connection:
            fact = RestrictedCaseRepository(connection).get_fact(
                case_id,
                case_version_id,
                case_fact_id,
            )

        if fact is None:
            raise DisclosureDataIntegrityError(
                "The disclosure references a fact missing from the case vault."
            )

        return fact

    def _list_restricted_facts(
        self,
        case_id: str,
        case_version_id: str,
    ) -> list[sqlite3.Row]:
        result = []
        offset = 0
        page_size = 200

        with self._database_manager.connection(
            "restricted"
        ) as connection:
            repository = RestrictedCaseRepository(connection)

            while True:
                page = repository.list_facts(
                    case_id,
                    case_version_id,
                    limit=page_size,
                    offset=offset,
                )

                result.extend(page)

                if len(page) < page_size:
                    break

                offset += page_size

        return result

    def initialize_run_disclosures(
        self,
        run_id: str,
        *,
        created_at: str,
    ) -> tuple[DisclosureRecord, ...]:
        """Initialize one not-disclosed ledger entry for every case fact.

        Repeated initialization is idempotent.
        Existing entries must match the run's exact case and version.
        """

        self._require_text(run_id, "run_id")
        self._require_text(created_at, "created_at")

        identity = self._get_run_identity(run_id)

        if identity["status"] not in {"initialized", "active"}:
            raise DisclosureTransitionError(
                "Disclosure initialization requires a non-terminal run."
            )

        facts = self._list_restricted_facts(
            identity["case_id"],
            identity["case_version_id"],
        )

        facts_by_id = {
            fact["case_fact_id"]: fact
            for fact in facts
        }

        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                current_run = connection.execute(
                    """
                    SELECT case_id, case_version_id, status
                    FROM simulation_runs
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchone()

                if current_run is None:
                    raise DisclosureRunNotFoundError(
                        "The simulation run no longer exists."
                    )

                if (
                    current_run["case_id"] != identity["case_id"]
                    or current_run["case_version_id"]
                    != identity["case_version_id"]
                ):
                    raise DisclosureDataIntegrityError(
                        "Run identity changed during disclosure initialization."
                    )

                if current_run["status"] not in {"initialized", "active"}:
                    raise DisclosureTransitionError(
                        "The simulation run no longer permits initialization."
                    )

                repository = DisclosureRepository(connection)
                existing_rows = repository.list_by_run(run_id)

                for existing in existing_rows:
                    fact = facts_by_id.get(existing["case_fact_id"])

                    if fact is None:
                        raise DisclosureDataIntegrityError(
                            "An existing disclosure references a missing case fact."
                        )

                    if (
                        existing["case_id"] != identity["case_id"]
                        or existing["case_version_id"]
                        != identity["case_version_id"]
                    ):
                        raise DisclosureDataIntegrityError(
                            "An existing disclosure has an invalid case identity."
                        )

                created_count = 0

                for fact in facts:
                    case_fact_id = fact["case_fact_id"]

                    existing = repository.get_by_fact(
                        run_id,
                        case_fact_id,
                    )

                    if existing is not None:
                        continue

                    repository.create_disclosure(
                        disclosure_id=uuid.uuid4().hex,
                        run_id=run_id,
                        case_id=identity["case_id"],
                        case_version_id=identity["case_version_id"],
                        case_fact_id=case_fact_id,
                        created_at=created_at,
                        operation_id=(
                            f"initialize:{run_id}:{case_fact_id}"
                        ),
                        validation_method="initialization",
                        disclosure_status="not_disclosed",
                    )

                    created_count += 1

                if created_count:
                    AuditRepository(connection).record(
                        audit_event_id=uuid.uuid4().hex,
                        component="disclosure_service",
                        operation_type="run_disclosures_initialized",
                        entity_type="simulation_run",
                        entity_id=run_id,
                        run_id=run_id,
                        operation_status="succeeded",
                        metadata={
                            "case_version_id": identity["case_version_id"],
                            "created_count": created_count,
                            "total_fact_count": len(facts),
                        },
                        created_at=created_at,
                    )

                rows = repository.list_by_run(run_id)

                return tuple(
                    self._from_rows(
                        row,
                        facts_by_id[row["case_fact_id"]],
                    )
                    for row in rows
                )

        except sqlite3.IntegrityError as exc:
            raise DisclosureConflictError(
                "Disclosure initialization violated a persistence constraint."
            ) from exc

    def get_disclosure(
        self,
        run_id: str,
        case_fact_id: str,
    ) -> DisclosureRecord | None:
        self._require_text(run_id, "run_id")
        self._require_text(case_fact_id, "case_fact_id")

        identity = self._get_run_identity(run_id)

        with self._database_manager.connection(
            "operational"
        ) as connection:
            row = DisclosureRepository(connection).get_by_fact(
                run_id,
                case_fact_id,
            )

        if row is None:
            return None

        if (
            row["case_id"] != identity["case_id"]
            or row["case_version_id"] != identity["case_version_id"]
        ):
            raise DisclosureDataIntegrityError(
                "Disclosure case identity does not match its run."
            )

        fact = self._get_restricted_fact(
            row["case_id"],
            row["case_version_id"],
            case_fact_id,
        )

        return self._from_rows(row, fact)

    def list_disclosures(
        self,
        run_id: str,
    ) -> tuple[DisclosureRecord, ...]:
        self._require_text(run_id, "run_id")
        identity = self._get_run_identity(run_id)

        with self._database_manager.connection(
            "operational"
        ) as connection:
            rows = DisclosureRepository(connection).list_by_run(run_id)

        facts = self._list_restricted_facts(
            identity["case_id"],
            identity["case_version_id"],
        )

        facts_by_id = {
            fact["case_fact_id"]: fact
            for fact in facts
        }

        records = []

        for row in rows:
            if (
                row["case_id"] != identity["case_id"]
                or row["case_version_id"] != identity["case_version_id"]
            ):
                raise DisclosureDataIntegrityError(
                    "Disclosure case identity does not match its run."
                )

            fact = facts_by_id.get(row["case_fact_id"])

            if fact is None:
                raise DisclosureDataIntegrityError(
                    "A disclosure references a missing case-vault fact."
                )

            records.append(self._from_rows(row, fact))

        return tuple(records)

    def _change_status(
        self,
        *,
        run_id: str,
        case_fact_id: str,
        target_status: str,
        operation_id: str,
        occurred_at: str,
        validation_method: str,
        source_message_id: str,
        evidence_start_offset: int,
        evidence_end_offset: int,
        validation_notes: str | None,
        evidence_description: str | None,
    ) -> DisclosureRecord:
        for name, value in (
            ("run_id", run_id),
            ("case_fact_id", case_fact_id),
            ("operation_id", operation_id),
            ("occurred_at", occurred_at),
            ("validation_method", validation_method),
        ):
            self._require_text(value, name)

        self._validate_evidence_offsets(
            source_message_id,
            evidence_start_offset,
            evidence_end_offset,
        )

        identity = self._get_run_identity(run_id)

        if identity["status"] not in {"initialized", "active", "interrupted"}:
            raise DisclosureTransitionError(
                "Disclosure changes are not permitted for a terminal run."
            )

        with self._database_manager.connection(
            "operational"
        ) as connection:
            initial_row = DisclosureRepository(connection).get_by_fact(
                run_id,
                case_fact_id,
            )

        if initial_row is None:
            raise DisclosureNotFoundError(
                "No disclosure record exists for this run and case fact."
            )

        if (
            initial_row["case_id"] != identity["case_id"]
            or initial_row["case_version_id"]
            != identity["case_version_id"]
        ):
            raise DisclosureDataIntegrityError(
                "Disclosure identity does not match the simulation run."
            )

        fact = self._get_restricted_fact(
            initial_row["case_id"],
            initial_row["case_version_id"],
            case_fact_id,
        )

        policy = fact["disclosure_policy"]
        information_class = fact["information_class"]

        if target_status in {
            "candidate_disclosed",
            "confirmed_disclosed",
        }:
            if policy not in self._DISCLOSABLE_POLICIES:
                raise DisclosurePolicyViolationError(
                    "The case-fact disclosure policy does not permit disclosure."
                )

        if target_status == "confirmed_disclosed":
            if information_class != "established_fact":
                raise DisclosurePolicyViolationError(
                    "Only established facts may become confirmed disclosures."
                )

            if initial_row["disclosure_status"] not in {
                "candidate_disclosed",
                "requires_review",
            }:
                raise DisclosureTransitionError(
                    "A disclosure must first be a candidate or require review."
                )

        try:
            with self._database_manager.transaction(
                "operational"
            ) as connection:
                repository = DisclosureRepository(connection)

                current = repository.get_by_fact(
                    run_id,
                    case_fact_id,
                )

                if current is None:
                    raise DisclosureNotFoundError(
                        "The disclosure record no longer exists."
                    )

                if current["disclosure_id"] != initial_row["disclosure_id"]:
                    raise DisclosureDataIntegrityError(
                        "Disclosure identity changed during the operation."
                    )

                previous_status = current["disclosure_status"]

                if previous_status == target_status:
                    return self._from_rows(current, fact)

                allowed = self._ALLOWED_TRANSITIONS.get(
                    previous_status,
                    frozenset(),
                )

                if target_status not in allowed:
                    raise DisclosureTransitionError(
                        f"Cannot transition disclosure from "
                        f"{previous_status} to {target_status}."
                    )

                try:
                    changed = repository.update_status(
                        current["disclosure_id"],
                        target_status,
                        operation_id=operation_id,
                        created_at=occurred_at,
                        validation_method=validation_method,
                        source_message_id=source_message_id,
                        evidence_start_offset=evidence_start_offset,
                        evidence_end_offset=evidence_end_offset,
                        validation_notes=validation_notes,
                        evidence_description=evidence_description,
                    )
                except ValueError as exc:
                    if "operation ID was reused" in str(exc):
                        raise DisclosureOperationConflictError(
                            "The operation identifier was already used for another disclosure change."
                        ) from exc

                    raise DisclosureEvidenceError(
                        str(exc)
                    ) from exc

                if not changed:
                    raise DisclosureDataIntegrityError(
                        "Disclosure status was not changed as expected."
                    )

                AuditRepository(connection).record(
                    audit_event_id=uuid.uuid4().hex,
                    component="disclosure_service",
                    operation_type=f"disclosure_{target_status}",
                    entity_type="case_fact_disclosure",
                    entity_id=current["disclosure_id"],
                    run_id=run_id,
                    operation_status="succeeded",
                    metadata={
                        "case_fact_id": case_fact_id,
                        "previous_status": previous_status,
                        "new_status": target_status,
                        "information_class": information_class,
                        "disclosure_policy": policy,
                        "validation_method": validation_method,
                    },
                    created_at=occurred_at,
                )

                updated = repository.get(
                    current["disclosure_id"]
                )

                if updated is None:
                    raise DisclosureDataIntegrityError(
                        "Updated disclosure could not be retrieved."
                    )

                return self._from_rows(updated, fact)

        except sqlite3.IntegrityError as exc:
            raise DisclosureConflictError(
                "Disclosure update violated a persistence constraint."
            ) from exc

    def mark_candidate_disclosed(
        self,
        run_id: str,
        case_fact_id: str,
        *,
        operation_id: str,
        occurred_at: str,
        source_message_id: str,
        evidence_start_offset: int,
        evidence_end_offset: int,
        evidence_description: str | None = None,
    ) -> DisclosureRecord:
        """Record a candidate disclosure supported by patient transcript."""

        return self._change_status(
            run_id=run_id,
            case_fact_id=case_fact_id,
            target_status="candidate_disclosed",
            operation_id=operation_id,
            occurred_at=occurred_at,
            validation_method="patient_annotation",
            source_message_id=source_message_id,
            evidence_start_offset=evidence_start_offset,
            evidence_end_offset=evidence_end_offset,
            validation_notes=None,
            evidence_description=evidence_description,
        )

    def confirm_disclosure(
        self,
        run_id: str,
        case_fact_id: str,
        *,
        operation_id: str,
        confirmed_at: str,
        source_message_id: str,
        evidence_start_offset: int,
        evidence_end_offset: int,
        evidence_description: str | None = None,
    ) -> DisclosureRecord:
        """Confirm an established fact after an explicit manual review.

        This method is reserved for an authorized application workflow.
        It must not be exposed as an unrestricted agent operation.
        """

        return self._change_status(
            run_id=run_id,
            case_fact_id=case_fact_id,
            target_status="confirmed_disclosed",
            operation_id=operation_id,
            occurred_at=confirmed_at,
            validation_method="manual_review",
            source_message_id=source_message_id,
            evidence_start_offset=evidence_start_offset,
            evidence_end_offset=evidence_end_offset,
            validation_notes="Confirmed through manual review.",
            evidence_description=evidence_description,
        )

    def flag_for_review(
        self,
        run_id: str,
        case_fact_id: str,
        *,
        operation_id: str,
        occurred_at: str,
        source_message_id: str,
        evidence_start_offset: int,
        evidence_end_offset: int,
        review_reason: str,
        evidence_description: str | None = None,
    ) -> DisclosureRecord:
        """Flag a possible disclosure without confirming its truth."""

        self._require_text(review_reason, "review_reason")

        return self._change_status(
            run_id=run_id,
            case_fact_id=case_fact_id,
            target_status="requires_review",
            operation_id=operation_id,
            occurred_at=occurred_at,
            validation_method="review_required",
            source_message_id=source_message_id,
            evidence_start_offset=evidence_start_offset,
            evidence_end_offset=evidence_end_offset,
            validation_notes=review_reason,
            evidence_description=evidence_description,
        )
