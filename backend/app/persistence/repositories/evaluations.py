"""Repositories for rubric versions and evidence-linked evaluation reports."""

import sqlite3
from collections.abc import Mapping, Sequence

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    json_text,
    require_message_for_run,
    require_offsets,
    require_session_for_run,
    require_text,
)


EVALUATION_SCOPES = {"session", "longitudinal"}
EVALUATION_STATUSES = {"pending", "completed", "failed", "requires_review"}
RATING_CODES = {"0", "1", "2", "3", "NE"}


class EvaluationRepository(ConnectionBoundRepository):
    """Persists rubric and evaluation records, not evaluator reasoning access."""

    def create_rubric_version(
        self,
        *,
        rubric_version_id: str,
        rubric_id: str,
        version_number: str,
        modality: str,
        language: str,
        schema_version: str,
        created_at: str,
        rubric_definition: Mapping[str, object],
        content_hash: str | None = None,
    ) -> None:
        for name, value in (
            ("rubric_version_id", rubric_version_id),
            ("rubric_id", rubric_id),
            ("version_number", version_number),
            ("modality", modality),
            ("language", language),
            ("schema_version", schema_version),
            ("created_at", created_at),
        ):
            require_text(value, name)

        self._connection.execute(
            """
            INSERT INTO rubric_versions (
                rubric_version_id, rubric_id, version_number,
                modality, language, schema_version,
                rubric_definition, content_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rubric_version_id,
                rubric_id,
                version_number,
                modality,
                language,
                schema_version,
                json_text(rubric_definition, "rubric_definition"),
                content_hash,
                created_at,
            ),
        )

    def get_rubric_version(
        self,
        rubric_version_id: str,
    ) -> sqlite3.Row | None:
        self.require_text(rubric_version_id, "rubric_version_id")
        return self._connection.execute(
            "SELECT * FROM rubric_versions WHERE rubric_version_id = ?",
            (rubric_version_id,),
        ).fetchone()

    def create_evaluation(
        self,
        *,
        evaluation_id: str,
        run_id: str,
        evaluation_scope: str,
        rubric_version_id: str,
        evaluation_revision: int,
        status: str,
        created_at: str,
        transcript_manifest: Sequence[Mapping[str, object]],
        session_id: str | None = None,
        evaluator_model_run_id: str | None = None,
        overall_summary: str | None = None,
        report_metadata: Mapping[str, object] | None = None,
    ) -> None:
        for name, value in (
            ("evaluation_id", evaluation_id),
            ("run_id", run_id),
            ("rubric_version_id", rubric_version_id),
            ("created_at", created_at),
        ):
            require_text(value, name)

        if evaluation_scope not in EVALUATION_SCOPES:
            raise ValueError("Invalid evaluation scope.")

        if status not in EVALUATION_STATUSES:
            raise ValueError("Invalid evaluation status.")

        if isinstance(evaluation_revision, bool) or not isinstance(evaluation_revision, int) or evaluation_revision < 1:
            raise ValueError("Evaluation revision must be positive.")

        if not isinstance(transcript_manifest, Sequence) or isinstance(transcript_manifest, (str, bytes)):
            raise ValueError("Transcript manifest must be a sequence.")

        if evaluation_scope == "session":
            if session_id is None:
                raise ValueError("Session evaluation requires session_id.")
            require_session_for_run(self._connection, session_id, run_id)
        elif session_id is not None:
            raise ValueError("Longitudinal evaluation must not have session_id.")

        if self.get_rubric_version(rubric_version_id) is None:
            raise ValueError("Rubric version does not exist.")

        if evaluator_model_run_id is not None:
            model_run = self._connection.execute(
                "SELECT run_id, component FROM model_runs WHERE model_run_id = ?",
                (evaluator_model_run_id,),
            ).fetchone()
            if (
                model_run is None
                or model_run["component"] != "evaluator_agent"
                or model_run["run_id"] != run_id
            ):
                raise ValueError("Evaluation model run is not a matching evaluator run.")

        metadata = (
            json_text(report_metadata, "report_metadata")
            if report_metadata is not None
            else None
        )

        self._connection.execute(
            """
            INSERT INTO evaluations (
                evaluation_id, run_id, session_id, evaluation_scope,
                rubric_version_id, transcript_manifest,
                evaluator_model_run_id, overall_summary,
                report_metadata, evaluation_revision, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_id,
                run_id,
                session_id,
                evaluation_scope,
                rubric_version_id,
                json_text(list(transcript_manifest), "transcript_manifest"),
                evaluator_model_run_id,
                overall_summary,
                metadata,
                evaluation_revision,
                status,
                created_at,
            ),
        )

    def get_evaluation(self, evaluation_id: str) -> sqlite3.Row | None:
        self.require_text(evaluation_id, "evaluation_id")
        return self._connection.execute(
            "SELECT * FROM evaluations WHERE evaluation_id = ?",
            (evaluation_id,),
        ).fetchone()

    def create_item(
        self,
        *,
        evaluation_item_id: str,
        evaluation_id: str,
        competency_id: str,
        rating_code: str,
        justification: str | None = None,
        alternative_response: str | None = None,
        limitations: str | None = None,
        uncertainty_notes: str | None = None,
    ) -> None:
        for name, value in (
            ("evaluation_item_id", evaluation_item_id),
            ("evaluation_id", evaluation_id),
            ("competency_id", competency_id),
        ):
            require_text(value, name)

        if rating_code not in RATING_CODES:
            raise ValueError("Invalid competency rating.")

        if self.get_evaluation(evaluation_id) is None:
            raise ValueError("Evaluation does not exist.")

        self._connection.execute(
            """
            INSERT INTO evaluation_items (
                evaluation_item_id, evaluation_id, competency_id,
                rating_code, justification, alternative_response,
                limitations, uncertainty_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_item_id,
                evaluation_id,
                competency_id,
                rating_code,
                justification,
                alternative_response,
                limitations,
                uncertainty_notes,
            ),
        )

    def add_evidence(
        self,
        *,
        evaluation_item_id: str,
        message_id: str,
        evidence_role: str,
        start_offset: int | None = None,
        end_offset: int | None = None,
        evidence_excerpt: str | None = None,
        evidence_note: str | None = None,
    ) -> bool:
        for name, value in (
            ("evaluation_item_id", evaluation_item_id),
            ("message_id", message_id),
            ("evidence_role", evidence_role),
        ):
            require_text(value, name)

        item = self._connection.execute(
            """
            SELECT e.run_id, e.session_id, e.evaluation_scope
            FROM evaluation_items AS i
            JOIN evaluations AS e ON e.evaluation_id = i.evaluation_id
            WHERE i.evaluation_item_id = ?
            """,
            (evaluation_item_id,),
        ).fetchone()

        if item is None:
            raise ValueError("Evaluation item does not exist.")

        message = require_message_for_run(
            self._connection,
            message_id,
            item["run_id"],
        )

        if item["evaluation_scope"] == "session":
            if message["session_id"] != item["session_id"]:
                raise ValueError("Evidence message is outside the evaluated session.")

        require_offsets(message["content"], start_offset, end_offset)

        if evidence_excerpt is not None:
            if start_offset is None or end_offset is None:
                raise ValueError("Evidence excerpt requires offsets.")
            if message["content"][start_offset:end_offset] != evidence_excerpt:
                raise ValueError("Evidence excerpt does not match the original message.")

        previous = self._connection.execute(
            """
            SELECT * FROM evaluation_evidence
            WHERE evaluation_item_id = ? AND message_id = ? AND evidence_role = ?
            """,
            (evaluation_item_id, message_id, evidence_role),
        ).fetchone()

        supplied = (
            start_offset,
            end_offset,
            evidence_excerpt,
            evidence_note,
        )

        if previous is not None:
            existing = (
                previous["start_offset"],
                previous["end_offset"],
                previous["evidence_excerpt"],
                previous["evidence_note"],
            )
            if existing == supplied:
                return False
            raise ValueError("Evaluation evidence identity already exists.")

        self._connection.execute(
            """
            INSERT INTO evaluation_evidence (
                evaluation_item_id, message_id, evidence_role,
                start_offset, end_offset, evidence_excerpt, evidence_note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_item_id,
                message_id,
                evidence_role,
                start_offset,
                end_offset,
                evidence_excerpt,
                evidence_note,
            ),
        )
        return True

    def list_items(self, evaluation_id: str) -> list[sqlite3.Row]:
        self.require_text(evaluation_id, "evaluation_id")
        return list(
            self._connection.execute(
                """
                SELECT * FROM evaluation_items
                WHERE evaluation_id = ?
                ORDER BY competency_id
                """,
                (evaluation_id,),
            ).fetchall()
        )

    def next_review_number(self, evaluation_id: str) -> int:
        self.require_text(evaluation_id, "evaluation_id")
        row = self._connection.execute(
            """
            SELECT COALESCE(MAX(review_number), 0) + 1
            FROM evaluation_reviews
            WHERE evaluation_id = ?
            """,
            (evaluation_id,),
        ).fetchone()
        return int(row[0])

    def create_review(
        self,
        *,
        review_id: str,
        evaluation_id: str,
        review_number: int,
        reviewer_user_id: str,
        decision: str,
        feedback: str,
        created_at: str,
    ) -> None:
        for name, value in (
            ("review_id", review_id),
            ("evaluation_id", evaluation_id),
            ("reviewer_user_id", reviewer_user_id),
            ("decision", decision),
            ("feedback", feedback),
            ("created_at", created_at),
        ):
            require_text(value, name)
        if isinstance(review_number, bool) or not isinstance(
            review_number, int
        ) or review_number < 1:
            raise ValueError("Review number must be a positive integer.")
        if not isinstance(decision, str) or decision not in {
            "accepted",
            "revision_requested",
        }:
            raise ValueError("Invalid evaluation review decision.")
        if not 1 <= len(feedback.strip()) <= 4000:
            raise ValueError("Evaluation review feedback is invalid.")

        self._connection.execute(
            """
            INSERT INTO evaluation_reviews (
                review_id, evaluation_id, review_number,
                reviewer_user_id, decision, feedback, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                evaluation_id,
                review_number,
                reviewer_user_id,
                decision,
                feedback.strip(),
                created_at,
            ),
        )

    def list_reviews(self, evaluation_id: str) -> list[sqlite3.Row]:
        self.require_text(evaluation_id, "evaluation_id")
        return list(
            self._connection.execute(
                """
                SELECT reviews.review_id, reviews.evaluation_id,
                       reviews.review_number, reviews.reviewer_user_id,
                       users.reviewer_name, reviews.decision,
                       reviews.feedback, reviews.created_at
                FROM evaluation_reviews AS reviews
                JOIN local_auth_users AS users
                  ON users.user_id = reviews.reviewer_user_id
                WHERE reviews.evaluation_id = ?
                ORDER BY reviews.review_number
                """,
                (evaluation_id,),
            ).fetchall()
        )
