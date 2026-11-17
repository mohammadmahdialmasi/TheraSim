"""Evidence-validated memory candidates and controlled review transitions."""

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import sqlite3
import unicodedata
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.domain_helpers import (
    require_message_for_run,
    require_session_for_run,
)
from app.persistence.repositories.memory import (
    MEMORY_SCOPES,
    MemoryRepository,
)
from app.persistence.repositories.operations import AuditRepository
from app.services.character_model import MemoryProposal


class MemoryServiceError(RuntimeError):
    """Base error for longitudinal memory operations."""


class MemoryRequestNotFoundError(MemoryServiceError):
    """The source interaction request does not exist in the specified Run."""


class MemoryRequestNotCompletedError(MemoryServiceError):
    """Memory proposals can only follow a persisted completed interaction."""


class MemoryEvidenceValidationError(MemoryServiceError):
    """A proposal's quoted evidence is invalid or unavailable at that time."""


class MemoryIdempotencyConflictError(MemoryServiceError):
    """An interaction proposal index was reused with different content."""


class MemoryNotFoundError(MemoryServiceError):
    """The requested memory item does not exist."""


class MemoryReviewConflictError(MemoryServiceError):
    """The requested review conflicts with the memory's current state."""


class MemoryConsolidationError(MemoryServiceError):
    """A memory consolidation proposal is invalid or unsupported by evidence."""


@dataclass(frozen=True, slots=True)
class MemoryRecord:
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
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class MemoryReviewRecord:
    review_id: str
    memory_id: str
    decision: str
    reviewer_id: str
    rationale: str
    reviewed_at: str


@dataclass(frozen=True, slots=True)
class MemoryEvidenceRecord:
    message_id: str
    relationship_type: str
    start_offset: int | None
    end_offset: int | None
    excerpt: str | None


@dataclass(frozen=True, slots=True)
class MemoryConsolidationSource:
    source_memory_id: str
    source_memory_version: int
    relationship_type: str
    content: str
    source_session_id: str


@dataclass(frozen=True, slots=True)
class MemoryConsolidationSuggestion:
    source_memory_ids: tuple[str, str]
    relationship_type: str
    similarity: float
    sources: tuple[MemoryConsolidationSource, MemoryConsolidationSource]


class MemoryService:
    """Persists untrusted proposals as evidence-linked, inactive candidates."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        *,
        id_factory=None,
    ) -> None:
        if not isinstance(database_manager, DatabaseManager):
            raise TypeError("A DatabaseManager instance is required.")
        if id_factory is not None and not callable(id_factory):
            raise TypeError("id_factory must be callable.")
        self._database_manager = database_manager
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            memory_id=row["memory_id"],
            run_id=row["run_id"],
            source_session_id=row["source_session_id"],
            memory_type=row["memory_type"],
            information_class=row["information_class"],
            content=row["content"],
            confidence=row["confidence"],
            status=row["status"],
            memory_version=row["memory_version"],
            memory_scope=row["memory_scope"],
            supersedes_memory_id=row["supersedes_memory_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _review_from_row(row: sqlite3.Row) -> MemoryReviewRecord:
        return MemoryReviewRecord(
            review_id=row["review_id"],
            memory_id=row["memory_id"],
            decision=row["decision"],
            reviewer_id=row["reviewer_id"],
            rationale=row["rationale"],
            reviewed_at=row["reviewed_at"],
        )

    def _new_id(self, prefix: str) -> str:
        value = self._id_factory()
        if not isinstance(value, str) or not value.strip():
            raise TypeError("id_factory must return non-empty text.")
        return f"{prefix}-{value}"

    @staticmethod
    def _resolve_evidence(
        connection: sqlite3.Connection,
        *,
        proposal: MemoryProposal,
        run_id: str,
        as_of_session_number: int,
        as_of_sequence_number: int,
        as_of_session_id: str,
        require_patient_authored_evidence: bool,
    ) -> list[tuple[str, int, int, str]]:
        evidence: list[tuple[str, int, int, str]] = []
        seen_message_ids: set[str] = set()
        patient_authored_source = False

        for quote in proposal.evidence:
            if quote.message_id in seen_message_ids:
                raise MemoryEvidenceValidationError(
                    "A memory proposal may cite each source message only once."
                )
            seen_message_ids.add(quote.message_id)

            try:
                message = require_message_for_run(
                    connection,
                    quote.message_id,
                    run_id,
                )
            except ValueError as exc:
                raise MemoryEvidenceValidationError(
                    "Memory evidence must reference a message in the same Run."
                ) from exc

            source_session = require_session_for_run(
                connection,
                message["session_id"],
                run_id,
            )
            source_session_number = source_session["session_number"]
            if source_session_number > as_of_session_number:
                raise MemoryEvidenceValidationError(
                    "Memory evidence cannot reference a future session."
                )
            if (
                message["session_id"] == as_of_session_id
                and message["sequence_number"] > as_of_sequence_number
            ):
                raise MemoryEvidenceValidationError(
                    "Memory evidence cannot reference a future message."
                )

            start_offset = message["content"].find(quote.exact_quote)
            if start_offset < 0:
                raise MemoryEvidenceValidationError(
                    "Quoted memory evidence does not match the original message."
                )
            end_offset = start_offset + len(quote.exact_quote)
            evidence.append(
                (
                    quote.message_id,
                    start_offset,
                    end_offset,
                    message["role"],
                )
            )
            patient_authored_source |= message["role"] == "patient"

        if proposal.information_class in {
            "confirmed_fact",
            "explicit_disclosure",
            "reported_outcome",
        } and not patient_authored_source:
            raise MemoryEvidenceValidationError(
                "Client-fact memories require patient-authored evidence."
            )

        if require_patient_authored_evidence and any(
            role != "patient" for _message_id, _start, _end, role in evidence
        ):
            raise MemoryEvidenceValidationError(
                "Automatic memory extraction requires patient-authored evidence."
            )

        return evidence

    @staticmethod
    def _matches_existing_candidate(
        repository: MemoryRepository,
        existing: sqlite3.Row,
        *,
        run_id: str,
        session_id: str,
        memory_type: str,
        information_class: str,
        content: str,
        confidence: float,
        memory_scope: str,
        supersedes_memory_id: str | None,
        evidence: list[tuple[str, int, int, str]],
    ) -> bool:
        expected = (
            existing["run_id"],
            existing["source_session_id"],
            existing["memory_type"],
            existing["information_class"],
            existing["content"],
            existing["confidence"],
            existing["memory_scope"],
            existing["supersedes_memory_id"],
        )
        supplied = (
            run_id,
            session_id,
            memory_type,
            information_class,
            content,
            confidence,
            memory_scope,
            supersedes_memory_id,
        )
        if expected != supplied:
            return False

        saved_evidence = repository.list_evidence(existing["memory_id"])
        saved = sorted([
            (
                row["message_id"],
                row["start_offset"],
                row["end_offset"],
                row["relationship_type"],
            )
            for row in saved_evidence
        ])
        supplied_evidence = sorted([
            (message_id, start, end, "supporting_quote")
            for message_id, start, end, _role in evidence
        ])
        return saved == supplied_evidence

    def create_candidate(
        self,
        *,
        run_id: str,
        session_id: str,
        interaction_request_id: str,
        proposal_index: int,
        memory_scope: str,
        proposal: MemoryProposal,
        created_at: str,
        supersedes_memory_id: str | None = None,
        require_patient_authored_evidence: bool = False,
    ) -> MemoryRecord:
        """Validate proposal evidence, then persist an inactive candidate.

        The proposal's own identifier is not trusted as a database identity.
        Retries are keyed by the completed interaction request and backend-owned
        proposal index.
        """

        if not isinstance(proposal, MemoryProposal):
            raise TypeError("proposal must be a validated MemoryProposal.")
        if memory_scope not in MEMORY_SCOPES - {"legacy_unclassified"}:
            raise ValueError("A classified memory scope is required.")
        if isinstance(proposal_index, bool) or not isinstance(proposal_index, int) or proposal_index < 0:
            raise ValueError("proposal_index must be a non-negative integer.")
        for name, value in (
            ("run_id", run_id),
            ("session_id", session_id),
            ("interaction_request_id", interaction_request_id),
            ("created_at", created_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text.")
        if supersedes_memory_id is not None and (
            not isinstance(supersedes_memory_id, str)
            or not supersedes_memory_id.strip()
        ):
            raise ValueError("supersedes_memory_id must be non-empty text or None.")

        with self._database_manager.transaction("operational") as connection:
            interaction = connection.execute(
                """
                SELECT r.processing_status, r.patient_message_id,
                       s.run_id, s.session_number, s.session_id
                FROM interaction_requests AS r
                JOIN sessions AS s ON s.session_id = r.session_id
                WHERE r.request_id = ? AND r.session_id = ?
                """,
                (interaction_request_id, session_id),
            ).fetchone()
            if interaction is None or interaction["run_id"] != run_id:
                raise MemoryRequestNotFoundError(
                    "The source interaction does not belong to this Run and session."
                )
            if (
                interaction["processing_status"] != "completed"
                or interaction["patient_message_id"] is None
            ):
                raise MemoryRequestNotCompletedError(
                    "Memory proposals require a completed persisted interaction."
                )

            as_of_message = require_message_for_run(
                connection,
                interaction["patient_message_id"],
                run_id,
                role="patient",
            )
            if as_of_message["session_id"] != session_id:
                raise MemoryEvidenceValidationError(
                    "The completed interaction response belongs to another session."
                )
            evidence = self._resolve_evidence(
                connection,
                proposal=proposal,
                run_id=run_id,
                as_of_session_number=interaction["session_number"],
                as_of_sequence_number=as_of_message["sequence_number"],
                as_of_session_id=session_id,
                require_patient_authored_evidence=(
                    require_patient_authored_evidence
                ),
            )

            repository = MemoryRepository(connection)
            existing = repository.get_by_origin(
                interaction_request_id,
                proposal_index,
            )
            if existing is not None:
                if not self._matches_existing_candidate(
                    repository,
                    existing,
                    run_id=run_id,
                    session_id=session_id,
                    memory_type=proposal.memory_type,
                    information_class=proposal.information_class,
                    content=proposal.content,
                    confidence=proposal.confidence,
                    memory_scope=memory_scope,
                    supersedes_memory_id=supersedes_memory_id,
                    evidence=evidence,
                ):
                    raise MemoryIdempotencyConflictError(
                        "The proposal index was reused with different memory data."
                    )
                return self._memory_from_row(existing)

            memory_version = 1
            if supersedes_memory_id is not None:
                previous = repository.get(supersedes_memory_id)
                if previous is None or previous["run_id"] != run_id:
                    raise MemoryReviewConflictError(
                        "A revised memory must supersede an item in the same Run."
                    )
                if previous["status"] != "active":
                    raise MemoryReviewConflictError(
                        "Only an active memory can be superseded."
                    )
                if previous["information_class"] != proposal.information_class:
                    raise MemoryEvidenceValidationError(
                        "A revision cannot change the memory information class."
                    )
                memory_version = previous["memory_version"] + 1

            memory_id = self._new_id("memory")
            repository.create_memory(
                memory_id=memory_id,
                run_id=run_id,
                source_session_id=session_id,
                memory_type=proposal.memory_type,
                information_class=proposal.information_class,
                content=proposal.content,
                confidence=proposal.confidence,
                status="requires_review",
                memory_version=memory_version,
                memory_scope=memory_scope,
                supersedes_memory_id=supersedes_memory_id,
                origin_interaction_request_id=interaction_request_id,
                proposal_index=proposal_index,
                created_at=created_at,
                updated_at=created_at,
            )
            for message_id, start, end, _role in evidence:
                repository.add_evidence(
                    memory_id,
                    message_id,
                    "supporting_quote",
                    start_offset=start,
                    end_offset=end,
                )
            AuditRepository(connection).record(
                audit_event_id=self._new_id("audit"),
                component="memory_service",
                operation_type="memory_candidate_created",
                entity_type="memory_item",
                entity_id=memory_id,
                run_id=run_id,
                session_id=session_id,
                operation_status="succeeded",
                metadata={
                    "information_class": proposal.information_class,
                    "memory_scope": memory_scope,
                    "origin_interaction_request_id": interaction_request_id,
                    "proposal_index": proposal_index,
                    "source_message_ids": [
                        item[0] for item in evidence
                    ],
                    "supersedes_memory_id": supersedes_memory_id,
                },
                created_at=created_at,
            )
            row = repository.get(memory_id)
            if row is None:
                raise MemoryServiceError(
                    "Created memory candidate could not be retrieved."
                )
            return self._memory_from_row(row)

    def review_candidate(
        self,
        memory_id: str,
        *,
        decision: str,
        reviewer_id: str,
        rationale: str,
        reviewed_at: str,
    ) -> tuple[MemoryRecord, MemoryReviewRecord]:
        if decision not in {"accepted", "rejected"}:
            raise ValueError("decision must be accepted or rejected.")
        for name, value in (
            ("memory_id", memory_id),
            ("reviewer_id", reviewer_id),
            ("rationale", rationale),
            ("reviewed_at", reviewed_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text.")

        with self._database_manager.transaction("operational") as connection:
            repository = MemoryRepository(connection)
            memory = repository.get(memory_id)
            if memory is None:
                raise MemoryNotFoundError("The memory candidate does not exist.")

            previous_review = repository.get_review(memory_id)
            if previous_review is not None:
                if (
                    previous_review["decision"] == decision
                    and previous_review["reviewer_id"] == reviewer_id
                    and previous_review["rationale"] == rationale
                ):
                    return (
                        self._memory_from_row(memory),
                        self._review_from_row(previous_review),
                    )
                raise MemoryReviewConflictError(
                    "The memory candidate already has a different review."
                )
            if memory["status"] != "requires_review":
                raise MemoryReviewConflictError(
                    "Only an unreviewed candidate can be reviewed."
                )

            if decision == "accepted" and memory["supersedes_memory_id"] is not None:
                previous = repository.get(memory["supersedes_memory_id"])
                if previous is None or previous["status"] != "active":
                    raise MemoryReviewConflictError(
                        "The memory being revised is no longer active."
                    )
                if not repository.update_status(
                    previous["memory_id"],
                    expected_status="active",
                    status="superseded",
                    updated_at=reviewed_at,
                ):
                    raise MemoryReviewConflictError(
                        "The previous memory changed during review."
                    )

            target_status = (
                "active" if decision == "accepted" else "rejected"
            )
            if not repository.update_status(
                memory_id,
                expected_status="requires_review",
                status=target_status,
                updated_at=reviewed_at,
            ):
                raise MemoryReviewConflictError(
                    "The memory candidate changed during review."
                )

            review_id = self._new_id("memory-review")
            repository.create_review(
                review_id=review_id,
                memory_id=memory_id,
                decision=decision,
                reviewer_id=reviewer_id,
                rationale=rationale,
                reviewed_at=reviewed_at,
            )
            AuditRepository(connection).record(
                audit_event_id=self._new_id("audit"),
                component="memory_service",
                operation_type=f"memory_{decision}",
                entity_type="memory_item",
                entity_id=memory_id,
                run_id=memory["run_id"],
                session_id=memory["source_session_id"],
                operation_status="succeeded",
                metadata={
                    "decision": decision,
                    "reviewer_id": reviewer_id,
                    "supersedes_memory_id": memory["supersedes_memory_id"],
                },
                created_at=reviewed_at,
            )
            updated_memory = repository.get(memory_id)
            saved_review = repository.get_review(memory_id)
            if updated_memory is None or saved_review is None:
                raise MemoryServiceError(
                    "Reviewed memory could not be retrieved."
                )
            return (
                self._memory_from_row(updated_memory),
                self._review_from_row(saved_review),
            )

    def list_memories(
        self,
        run_id: str,
        *,
        status: str | None = None,
    ) -> list[MemoryRecord]:
        with self._database_manager.connection("operational") as connection:
            rows = MemoryRepository(connection).list_by_run(
                run_id,
                status=status,
            )
            return [self._memory_from_row(row) for row in rows]

    def list_evidence(
        self,
        memory_id: str,
    ) -> list[MemoryEvidenceRecord]:
        with self._database_manager.connection("operational") as connection:
            if MemoryRepository(connection).get(memory_id) is None:
                raise MemoryNotFoundError("The memory item does not exist.")
            rows = connection.execute(
                """
                SELECT e.message_id, e.relationship_type,
                       e.start_offset, e.end_offset, m.content
                FROM memory_evidence AS e
                JOIN messages AS m ON m.message_id = e.message_id
                WHERE e.memory_id = ?
                ORDER BY e.message_id
                """,
                (memory_id,),
            ).fetchall()
            return [
                MemoryEvidenceRecord(
                    message_id=row["message_id"],
                    relationship_type=row["relationship_type"],
                    start_offset=row["start_offset"],
                    end_offset=row["end_offset"],
                    excerpt=(
                        row["content"][
                            row["start_offset"]:row["end_offset"]
                        ]
                        if row["start_offset"] is not None
                        and row["end_offset"] is not None
                        else None
                    ),
                )
                for row in rows
            ]

    @staticmethod
    def _memory_tokens(content: str) -> set[str]:
        normalized = unicodedata.normalize("NFKC", content).casefold()
        stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "but", "for",
            "from", "had", "has", "have", "he", "her", "his", "i", "in",
            "is", "it", "of", "on", "or", "she", "that", "the", "their",
            "they", "to", "was", "were", "with", "my", "me", "we", "you",
            "من", "او", "به", "در", "و", "از", "که", "را", "با",
        }
        return {
            token
            for token in re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
            if len(token) > 1 and token not in stop_words
        }

    @staticmethod
    def _is_negated(content: str) -> bool:
        normalized = unicodedata.normalize("NFKC", content).casefold()
        return bool(
            re.search(
                r"\b(?:not|never|no|without|cannot|can't|didn't|isn't|don't)\b",
                normalized,
            )
            or "نمی" in normalized
            or re.search(r"\b(?:نیست|نیستم|نیستند|هرگز)\b", normalized)
        )

    @classmethod
    def _relationship(
        cls,
        first: str,
        second: str,
    ) -> tuple[str, float] | None:
        first_tokens = cls._memory_tokens(first)
        second_tokens = cls._memory_tokens(second)
        if not first_tokens or not second_tokens:
            return None
        shared = first_tokens & second_tokens
        similarity = len(shared) / len(first_tokens | second_tokens)
        if len(shared) < 2 or similarity < 0.22:
            return None
        if cls._is_negated(first) != cls._is_negated(second):
            return "potential_contradiction", similarity
        relation = "repeated" if similarity >= 0.5 else "related"
        return relation, similarity

    def list_consolidation_suggestions(
        self,
        run_id: str,
    ) -> list[MemoryConsolidationSuggestion]:
        with self._database_manager.connection("operational") as connection:
            repository = MemoryRepository(connection)
            memories = repository.list_active_for_consolidation(run_id)
            suggestions: list[MemoryConsolidationSuggestion] = []
            for index, first in enumerate(memories):
                for second in memories[index + 1:]:
                    if first["source_session_id"] == second["source_session_id"]:
                        continue
                    relationship = self._relationship(
                        first["content"],
                        second["content"],
                    )
                    if relationship is None:
                        continue
                    relationship_type, similarity = relationship
                    suggestions.append(
                        MemoryConsolidationSuggestion(
                            source_memory_ids=(
                                first["memory_id"],
                                second["memory_id"],
                            ),
                            relationship_type=relationship_type,
                            similarity=round(similarity, 4),
                            sources=(
                                MemoryConsolidationSource(
                                    source_memory_id=first["memory_id"],
                                    source_memory_version=first["memory_version"],
                                    relationship_type=relationship_type,
                                    content=first["content"],
                                    source_session_id=first["source_session_id"],
                                ),
                                MemoryConsolidationSource(
                                    source_memory_id=second["memory_id"],
                                    source_memory_version=second["memory_version"],
                                    relationship_type=relationship_type,
                                    content=second["content"],
                                    source_session_id=second["source_session_id"],
                                ),
                            ),
                        )
                    )
            return sorted(
                suggestions,
                key=lambda item: (
                    item.relationship_type == "potential_contradiction",
                    item.similarity,
                    item.source_memory_ids,
                ),
                reverse=True,
            )

    def list_consolidation_sources(
        self,
        memory_id: str,
    ) -> list[MemoryConsolidationSource]:
        with self._database_manager.connection("operational") as connection:
            repository = MemoryRepository(connection)
            if repository.get(memory_id) is None:
                raise MemoryNotFoundError("The memory item does not exist.")
            return [
                MemoryConsolidationSource(
                    source_memory_id=row["source_memory_id"],
                    source_memory_version=row["source_memory_version"],
                    relationship_type=row["relationship_type"],
                    content=row["content"],
                    source_session_id=row["source_session_id"],
                )
                for row in repository.list_consolidation_sources(memory_id)
            ]

    def propose_consolidation(
        self,
        run_id: str,
        *,
        source_memory_ids: list[str],
        content: str,
    ) -> MemoryRecord:
        if not isinstance(run_id, str) or not run_id.strip():
            raise MemoryConsolidationError("A Run ID is required.")
        if (
            not isinstance(source_memory_ids, list)
            or not 2 <= len(source_memory_ids) <= 5
            or any(not isinstance(item, str) or not item.strip()
                   for item in source_memory_ids)
            or len(set(source_memory_ids)) != len(source_memory_ids)
        ):
            raise MemoryConsolidationError(
                "Choose between two and five distinct source memories."
            )
        if not isinstance(content, str) or not content.strip():
            raise MemoryConsolidationError(
                "A proposed consolidated memory is required."
            )
        if len(content) > 12000:
            raise MemoryConsolidationError(
                "A proposed consolidated memory is too long."
            )

        created_at = datetime.now(timezone.utc).isoformat()
        with self._database_manager.transaction("operational") as connection:
            repository = MemoryRepository(connection)
            source_rows = [
                repository.get(memory_id)
                for memory_id in source_memory_ids
            ]
            if any(
                row is None
                or row["run_id"] != run_id
                or row["status"] != "active"
                or row["source_session_id"] is None
                for row in source_rows
            ):
                raise MemoryConsolidationError(
                    "Every source must be an active memory from this Run."
                )
            memories = [row for row in source_rows if row is not None]
            if len({row["source_session_id"] for row in memories}) < 2:
                raise MemoryConsolidationError(
                    "Consolidation requires memories from at least two sessions."
                )

            relationships: list[tuple[int, int, str]] = []
            connected: set[int] = set()
            for first_index, first in enumerate(memories):
                for second_index in range(first_index + 1, len(memories)):
                    second = memories[second_index]
                    relationship = self._relationship(
                        first["content"],
                        second["content"],
                    )
                    if relationship is None:
                        continue
                    relationships.append(
                        (first_index, second_index, relationship[0])
                    )
                    connected.update((first_index, second_index))
            if len(connected) != len(memories):
                raise MemoryConsolidationError(
                    "Each source must be related to another selected memory."
                )

            source_evidence = {
                row["memory_id"]: repository.list_evidence(row["memory_id"])
                for row in memories
            }
            if any(not items for items in source_evidence.values()):
                raise MemoryConsolidationError(
                    "Every source memory must have transcript evidence."
                )

            latest = max(
                memories,
                key=lambda row: (
                    row["created_at"],
                    row["source_session_id"],
                ),
            )
            confidence_values = [row["confidence"] for row in memories]
            confidence = (
                min(confidence_values)
                if all(value is not None for value in confidence_values)
                else None
            )
            memory_id = self._new_id("memory")
            repository.create_memory(
                memory_id=memory_id,
                run_id=run_id,
                source_session_id=latest["source_session_id"],
                memory_type="consolidated_pattern",
                information_class="structured_observation",
                content=content.strip(),
                memory_version=1,
                created_at=created_at,
                updated_at=created_at,
                status="requires_review",
                confidence=confidence,
                memory_scope="semantic",
            )

            source_relations = ["related"] * len(memories)
            for first_index, second_index, relationship_type in relationships:
                if relationship_type == "potential_contradiction":
                    source_relations[first_index] = relationship_type
                    source_relations[second_index] = relationship_type
                elif (
                    relationship_type == "repeated"
                    and source_relations[first_index] == "related"
                    and source_relations[second_index] == "related"
                ):
                    source_relations[first_index] = "repeated"
                    source_relations[second_index] = "repeated"

            for index, source in enumerate(memories):
                repository.create_consolidation_source(
                    consolidated_memory_id=memory_id,
                    source_memory_id=source["memory_id"],
                    source_memory_version=source["memory_version"],
                    source_session_id=source["source_session_id"],
                    source_content=source["content"],
                    relationship_type=source_relations[index],
                    created_at=created_at,
                )
                for evidence in source_evidence[source["memory_id"]]:
                    repository.add_evidence(
                        memory_id,
                        evidence["message_id"],
                        "supports",
                        start_offset=evidence["start_offset"],
                        end_offset=evidence["end_offset"],
                    )

            AuditRepository(connection).record(
                audit_event_id=self._new_id("audit"),
                component="memory_service",
                operation_type="memory_consolidation_proposed",
                entity_type="memory_item",
                entity_id=memory_id,
                run_id=run_id,
                session_id=latest["source_session_id"],
                operation_status="succeeded",
                metadata={
                    "source_memory_ids": source_memory_ids,
                    "source_count": len(source_memory_ids),
                    "review_required": True,
                },
                created_at=created_at,
            )
            created = repository.get(memory_id)
            if created is None:
                raise MemoryServiceError(
                    "Consolidated memory proposal could not be retrieved."
                )
            return self._memory_from_row(created)
