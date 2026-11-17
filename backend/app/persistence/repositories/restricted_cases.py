"""Restricted case-vault repository.

This repository accepts only DatabaseManager restricted connections.
It does not own transactions or expose database connections to agents.
"""

import sqlite3
from collections.abc import Mapping, Sequence

from app.persistence.repositories.base import ConnectionBoundRepository
from app.persistence.repositories.domain_helpers import (
    json_text,
    require_mapping,
    require_sequence,
)


INFORMATION_CLASSES = frozenset({
    "established_fact",
    "case_hypothesis",
    "unspecified_information",
})

DISCLOSURE_POLICIES = frozenset({
    "initial_disclosure",
    "contextually_disclosable",
    "restricted",
    "not_applicable",
})


class RestrictedCaseRepository(ConnectionBoundRepository):
    """Persistence access for restricted case profiles and facts."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(connection)

        try:
            row = self._connection.execute(
                "SELECT _therasim_database_role()"
            ).fetchone()
        except sqlite3.Error as exc:
            raise ValueError(
                "RestrictedCaseRepository requires a "
                "DatabaseManager restricted connection."
            ) from exc

        if row is None or row[0] != "restricted":
            raise ValueError(
                "A restricted connection is required; operational database connections are not permitted."
            )

    @staticmethod
    def _validate_case_identity(
        case_id: str,
        case_version_id: str,
    ) -> None:
        ConnectionBoundRepository.require_text(case_id, "case_id")
        ConnectionBoundRepository.require_text(
            case_version_id,
            "case_version_id",
        )

    def create_profile(
        self,
        *,
        restricted_profile_id: str,
        case_id: str,
        case_version_id: str,
        created_at: str,
        clinical_formulation: Mapping[str, object] | None = None,
        relevant_personal_history: Mapping[str, object] | None = None,
        maintaining_factors: Sequence[object] = (),
        avoidance_patterns: Sequence[object] = (),
        hypothesized_functions: Mapping[str, object] | None = None,
        initial_safety_baseline: Mapping[str, object] | None = None,
        patient_simulation_instructions: str | None = None,
    ) -> None:
        """Create one immutable restricted profile for a case version."""

        for name, value in (
            ("restricted_profile_id", restricted_profile_id),
            ("created_at", created_at),
        ):
            self.require_text(value, name)

        self._validate_case_identity(case_id, case_version_id)

        mapping_values = (
            ("clinical_formulation", clinical_formulation),
            ("relevant_personal_history", relevant_personal_history),
            ("hypothesized_functions", hypothesized_functions),
            ("initial_safety_baseline", initial_safety_baseline),
        )

        serialized_mappings = {}

        for name, value in mapping_values:
            normalized = {} if value is None else value
            require_mapping(normalized, name)
            serialized_mappings[name] = json_text(normalized, name)

        sequence_values = (
            ("maintaining_factors", maintaining_factors),
            ("avoidance_patterns", avoidance_patterns),
        )

        serialized_sequences = {}

        for name, value in sequence_values:
            require_sequence(value, name)
            serialized_sequences[name] = json_text(value, name)

        if patient_simulation_instructions is not None:
            self.require_text(
                patient_simulation_instructions,
                "patient_simulation_instructions",
            )

        self._connection.execute(
            """
            INSERT INTO restricted_case_profiles (
                restricted_profile_id,
                case_id,
                case_version_id,
                clinical_formulation,
                relevant_personal_history,
                maintaining_factors,
                avoidance_patterns,
                hypothesized_functions,
                initial_safety_baseline,
                patient_simulation_instructions,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                restricted_profile_id,
                case_id,
                case_version_id,
                serialized_mappings["clinical_formulation"],
                serialized_mappings["relevant_personal_history"],
                serialized_sequences["maintaining_factors"],
                serialized_sequences["avoidance_patterns"],
                serialized_mappings["hypothesized_functions"],
                serialized_mappings["initial_safety_baseline"],
                patient_simulation_instructions,
                created_at,
            ),
        )

    def get_profile(
        self,
        case_id: str,
        case_version_id: str,
    ) -> sqlite3.Row | None:
        """Retrieve a restricted profile by its complete case identity."""

        self._validate_case_identity(case_id, case_version_id)

        return self._connection.execute(
            """
            SELECT *
            FROM restricted_case_profiles
            WHERE case_id = ? AND case_version_id = ?
            """,
            (case_id, case_version_id),
        ).fetchone()

    def get_profile_by_version(
        self,
        case_version_id: str,
    ) -> sqlite3.Row | None:
        """Retrieve a profile by its globally unique case version."""

        self.require_text(case_version_id, "case_version_id")

        return self._connection.execute(
            """
            SELECT *
            FROM restricted_case_profiles
            WHERE case_version_id = ?
            """,
            (case_version_id,),
        ).fetchone()

    def create_fact(
        self,
        *,
        case_id: str,
        case_version_id: str,
        case_fact_id: str,
        fact_category: str,
        information_class: str,
        content: str,
        disclosure_policy: str,
        created_at: str,
        relevance_metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Create a restricted fact belonging to an existing case version."""

        self._validate_case_identity(case_id, case_version_id)

        for name, value in (
            ("case_fact_id", case_fact_id),
            ("fact_category", fact_category),
            ("content", content),
            ("created_at", created_at),
        ):
            self.require_text(value, name)

        if information_class not in INFORMATION_CLASSES:
            raise ValueError("Invalid information_class.")

        if disclosure_policy not in DISCLOSURE_POLICIES:
            raise ValueError("Invalid disclosure_policy.")

        if relevance_metadata is None:
            metadata_text = None
        else:
            require_mapping(relevance_metadata, "relevance_metadata")
            metadata_text = json_text(
                relevance_metadata,
                "relevance_metadata",
            )

        self._connection.execute(
            """
            INSERT INTO case_facts (
                case_id,
                case_version_id,
                case_fact_id,
                fact_category,
                information_class,
                content,
                disclosure_policy,
                relevance_metadata,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                case_version_id,
                case_fact_id,
                fact_category,
                information_class,
                content,
                disclosure_policy,
                metadata_text,
                created_at,
            ),
        )

    def get_fact(
        self,
        case_id: str,
        case_version_id: str,
        case_fact_id: str,
    ) -> sqlite3.Row | None:
        """Retrieve a fact using its complete composite primary key."""

        self._validate_case_identity(case_id, case_version_id)
        self.require_text(case_fact_id, "case_fact_id")

        return self._connection.execute(
            """
            SELECT *
            FROM case_facts
            WHERE case_id = ?
              AND case_version_id = ?
              AND case_fact_id = ?
            """,
            (case_id, case_version_id, case_fact_id),
        ).fetchone()

    def list_facts(
        self,
        case_id: str,
        case_version_id: str,
        *,
        fact_category: str | None = None,
        information_class: str | None = None,
        disclosure_policy: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[sqlite3.Row]:
        """List facts for one exact case version with validated filters."""

        self._validate_case_identity(case_id, case_version_id)
        self.require_pagination(limit, offset)

        filters = (
            ("fact_category", fact_category, None),
            ("information_class", information_class, INFORMATION_CLASSES),
            ("disclosure_policy", disclosure_policy, DISCLOSURE_POLICIES),
        )

        conditions = [
            "case_id = ?",
            "case_version_id = ?",
        ]
        parameters: list[object] = [case_id, case_version_id]

        for name, value, allowed_values in filters:
            if value is None:
                continue

            self.require_text(value, name)

            if allowed_values is not None and value not in allowed_values:
                raise ValueError(f"Invalid {name}.")

            conditions.append(f"{name} = ?")
            parameters.append(value)

        parameters.extend([limit, offset])

        query = f"""
            SELECT *
            FROM case_facts
            WHERE {" AND ".join(conditions)}
            ORDER BY case_fact_id
            LIMIT ? OFFSET ?
        """

        return self._connection.execute(
            query,
            parameters,
        ).fetchall()
