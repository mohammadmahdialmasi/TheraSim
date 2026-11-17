import sqlite3
from uuid import uuid4

import pytest

from app.persistence.database import DatabaseManager


def _seed_run(manager):
    manager.initialize()

    token = uuid4().hex
    now = "2026-11-16T12:00:00Z"

    ids = {
        "case_id": "case-" + token,
        "case_version_id": "version-" + token,
        "run_id": "run-" + token,
        "session_id": "session-" + token,
        "message_id": "message-" + token,
        "now": now,
    }

    with manager.transaction("operational") as connection:
        connection.execute(
            "INSERT INTO cases "
            "(case_id, case_code, display_name, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                ids["case_id"],
                "TEST-" + token[:10],
                "Synthetic test case",
                "active",
                now,
                now,
            ),
        )

        connection.execute(
            "INSERT INTO case_versions "
            "(case_version_id, case_id, version_number, modality, language, "
            "schema_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ids["case_version_id"],
                ids["case_id"],
                "0.2",
                "ACT",
                "fa",
                "0.2",
                now,
            ),
        )

        connection.execute(
            "INSERT INTO simulation_runs "
            "(run_id, case_id, case_version_id, modality, language, status, "
            "configuration_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ids["run_id"],
                ids["case_id"],
                ids["case_version_id"],
                "ACT",
                "fa",
                "initialized",
                "0.1",
                now,
            ),
        )

        connection.execute(
            "INSERT INTO sessions "
            "(session_id, run_id, session_number, status, transcript_version, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ids["session_id"],
                ids["run_id"],
                1,
                "active",
                1,
                now,
            ),
        )

        connection.execute(
            "INSERT INTO messages "
            "(message_id, session_id, sequence_number, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                ids["message_id"],
                ids["session_id"],
                1,
                "patient",
                "Ava disclosed an experience.",
                now,
            ),
        )

    return ids


def _insert_event(connection, ids, event_id=None, sequence=1, key=None):
    event_id = event_id or "event-" + uuid4().hex
    key = key or "event-operation-" + uuid4().hex

    connection.execute(
        "INSERT INTO events "
        "(event_id, run_id, session_id, sequence_number, event_type, actor, "
        "payload, extraction_method, event_status, idempotency_key, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            event_id,
            ids["run_id"],
            ids["session_id"],
            sequence,
            "message_received",
            "application",
            "{}",
            "application_rule",
            "accepted",
            key,
            ids["now"],
        ),
    )

    return event_id


def _insert_snapshot(connection, ids, snapshot_id, previous=None):
    connection.execute(
        "INSERT INTO state_snapshots "
        "(snapshot_id, run_id, session_id, previous_snapshot_id, "
        "state_schema_version, snapshot_reason, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            snapshot_id,
            ids["run_id"],
            ids["session_id"],
            previous,
            "0.1",
            "test_snapshot",
            ids["now"],
        ),
    )


def test_operational_table_inventory_and_database_separation(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    manager.initialize()

    expected_operational = {
        "cases",
        "case_versions",
        "public_case_profiles",
        "simulation_runs",
        "sessions",
        "run_character_profiles",
        "character_state_snapshots",
        "character_state_snapshot_values",
        "character_state_transitions",
        "character_state_transition_evidence",
        "messages",
        "interaction_requests",
        "case_fact_disclosures",
        "case_fact_disclosure_history",
        "events",
        "event_evidence",
        "event_reviews",
        "treatment_plan_revisions",
        "treatment_plan_reviews",
        "local_auth_users",
        "local_auth_sessions",
        "local_auth_login_attempts",
        "state_snapshots",
        "state_snapshot_values",
        "state_transitions",
        "transition_evidence",
        "memory_items",
        "memory_evidence",
        "memory_reviews",
        "memory_consolidation_sources",
        "memory_extraction_jobs",
        "rubric_versions",
        "evaluations",
        "evaluation_reviews",
        "evaluation_items",
        "evaluation_evidence",
        "model_runs",
        "audit_events",
        "schema_migrations",
    }

    with manager.connection("operational") as connection:
        actual = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert actual == expected_operational

    with manager.connection("restricted") as connection:
        restricted = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

    assert restricted == {
        "restricted_case_profiles",
        "case_facts",
        "character_personality_profiles",
        "schema_migrations",
    }


def test_domain_migration_is_idempotent_and_versioned(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")

    first = manager.initialize()
    second = manager.initialize()

    assert first == second
    assert first["operational"] == [
        "001_initial_core",
        "002_domain_persistence",
        "003_interaction_recovery",
        "004_session_transcript_integrity",
        "005_character_runtime",
        "006_unbounded_session_numbers",
        "007_memory_review_lifecycle",
        "008_memory_extraction_outbox",
        "009_memory_extraction_model_component",
        "010_versioned_run_protocols",
        "011_memory_extraction_state_context",
        "012_event_review_history",
        "013_versioned_treatment_plans",
        "014_local_authentication",
        "015_memory_consolidation_provenance",
        "016_local_login_throttling",
        "017_evaluation_reviews",
    ]

    with manager.connection("operational") as connection:
        rows = connection.execute(
            "SELECT version, migration_id FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert [(row["version"], row["migration_id"]) for row in rows] == [
        (1, "001_initial_core"),
        (2, "002_domain_persistence"),
        (3, "003_interaction_recovery"),
        (4, "004_session_transcript_integrity"),
        (5, "005_character_runtime"),
        (6, "006_unbounded_session_numbers"),
        (7, "007_memory_review_lifecycle"),
        (8, "008_memory_extraction_outbox"),
        (9, "009_memory_extraction_model_component"),
        (10, "010_versioned_run_protocols"),
        (11, "011_memory_extraction_state_context"),
        (12, "012_event_review_history"),
        (13, "013_versioned_treatment_plans"),
        (14, "014_local_authentication"),
        (15, "015_memory_consolidation_provenance"),
        (16, "016_local_login_throttling"),
        (17, "017_evaluation_reviews"),
    ]


def test_disclosure_and_history_constraints(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    ids = _seed_run(manager)

    with manager.transaction("operational") as connection:
        connection.execute(
            "INSERT INTO case_fact_disclosures "
            "(disclosure_id, run_id, case_id, case_version_id, case_fact_id, "
            "disclosure_status, source_message_id, evidence_start_offset, "
            "evidence_end_offset, validation_method, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "disclosure-1",
                ids["run_id"],
                ids["case_id"],
                ids["case_version_id"],
                "AVA-FACT-001",
                "candidate_disclosed",
                ids["message_id"],
                0,
                3,
                "validated_annotation",
                ids["now"],
                ids["now"],
            ),
        )

        connection.execute(
            "INSERT INTO case_fact_disclosure_history "
            "(history_id, disclosure_id, previous_status, new_status, "
            "source_message_id, operation_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "history-1",
                "disclosure-1",
                None,
                "candidate_disclosed",
                ids["message_id"],
                "disclosure-operation-1",
                ids["now"],
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO case_fact_disclosures "
                "(disclosure_id, run_id, case_id, case_version_id, case_fact_id, "
                "disclosure_status, validation_method, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "disclosure-duplicate",
                    ids["run_id"],
                    ids["case_id"],
                    ids["case_version_id"],
                    "AVA-FACT-001",
                    "not_disclosed",
                    "test",
                    ids["now"],
                    ids["now"],
                ),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO case_fact_disclosure_history "
                "(history_id, disclosure_id, new_status, operation_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    "history-duplicate",
                    "disclosure-1",
                    "requires_review",
                    "disclosure-operation-1",
                    ids["now"],
                ),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO case_fact_disclosures "
                "(disclosure_id, run_id, case_id, case_version_id, case_fact_id, "
                "disclosure_status, validation_method, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "disclosure-invalid",
                    ids["run_id"],
                    ids["case_id"],
                    ids["case_version_id"],
                    "AVA-FACT-002",
                    "confirmed_disclosed",
                    "test",
                    ids["now"],
                    ids["now"],
                ),
            )


def test_events_and_evidence_constraints(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    ids = _seed_run(manager)

    with manager.transaction("operational") as connection:
        event_id = _insert_event(connection, ids)

        connection.execute(
            "INSERT INTO event_evidence "
            "(event_id, message_id, evidence_type, start_offset, end_offset) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, ids["message_id"], "supporting", 0, 3),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            _insert_event(
                connection,
                ids,
                sequence=2,
                key="event-operation-" + "duplicate",
            )
            _insert_event(
                connection,
                ids,
                sequence=3,
                key="event-operation-" + "duplicate",
            )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO event_evidence "
                "(event_id, message_id, evidence_type, start_offset, end_offset) "
                "VALUES (?, ?, ?, ?, ?)",
                (event_id, ids["message_id"], "invalid_span", 8, 2),
            )


def test_session_scoped_events_cannot_reference_another_run(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    first = _seed_run(manager)
    second = _seed_run(manager)

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO events "
                "(event_id, run_id, session_id, sequence_number, event_type, "
                "actor, payload, extraction_method, event_status, "
                "idempotency_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "cross-run-event",
                    second["run_id"],
                    first["session_id"],
                    1,
                    "message_received",
                    "application",
                    "{}",
                    "application_rule",
                    "accepted",
                    "cross-run-key",
                    second["now"],
                ),
            )


def test_state_snapshot_values_and_transition_constraints(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    ids = _seed_run(manager)

    variables = (
        "therapeutic_alliance",
        "disclosure_readiness",
        "experiential_avoidance",
        "willingness",
        "values_clarity",
        "committed_action_readiness",
    )

    with manager.transaction("operational") as connection:
        event_id = _insert_event(connection, ids)
        _insert_snapshot(connection, ids, "snapshot-1")
        _insert_snapshot(connection, ids, "snapshot-2", "snapshot-1")

        for name in variables:
            connection.execute(
                "INSERT INTO state_snapshot_values "
                "(snapshot_id, variable_name, variable_value) VALUES (?, ?, ?)",
                ("snapshot-1", name, 1),
            )

        connection.execute(
            "INSERT INTO state_transitions "
            "(transition_id, run_id, session_id, event_id, variable_name, "
            "previous_value, proposed_value, accepted_value, validation_status, "
            "resulting_snapshot_id, idempotency_key, created_at, validated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "transition-1",
                ids["run_id"],
                ids["session_id"],
                event_id,
                "willingness",
                1,
                2,
                2,
                "accepted",
                "snapshot-2",
                "transition-operation-1",
                ids["now"],
                ids["now"],
            ),
        )

        connection.execute(
            "INSERT INTO transition_evidence "
            "(transition_id, message_id, evidence_role) VALUES (?, ?, ?)",
            ("transition-1", ids["message_id"], "supporting"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO state_snapshot_values "
                "(snapshot_id, variable_name, variable_value) VALUES (?, ?, ?)",
                ("snapshot-1", "unknown_variable", 2),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO state_snapshot_values "
                "(snapshot_id, variable_name, variable_value) VALUES (?, ?, ?)",
                ("snapshot-1", "willingness", 5),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO state_transitions "
                "(transition_id, run_id, session_id, variable_name, "
                "previous_value, proposed_value, accepted_value, "
                "validation_status, idempotency_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "invalid-transition",
                    ids["run_id"],
                    ids["session_id"],
                    "willingness",
                    1,
                    2,
                    2,
                    "rejected",
                    "invalid-transition-key",
                    ids["now"],
                ),
            )


def test_memory_constraints_and_evidence(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    ids = _seed_run(manager)

    with manager.transaction("operational") as connection:
        connection.execute(
            "INSERT INTO memory_items "
            "(memory_id, run_id, source_session_id, memory_type, "
            "information_class, content, confidence, status, memory_version, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "memory-1",
                ids["run_id"],
                ids["session_id"],
                "client_statement",
                "explicit_disclosure",
                "Ava described a previous experience.",
                0.75,
                "active",
                1,
                ids["now"],
                ids["now"],
            ),
        )

        connection.execute(
            "INSERT INTO memory_evidence "
            "(memory_id, message_id, relationship_type) VALUES (?, ?, ?)",
            ("memory-1", ids["message_id"], "source"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO memory_items "
                "(memory_id, run_id, memory_type, information_class, content, "
                "confidence, status, memory_version, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "memory-invalid",
                    ids["run_id"],
                    "invalid",
                    "confirmed_fact",
                    "Invalid confidence",
                    1.5,
                    "active",
                    1,
                    ids["now"],
                    ids["now"],
                ),
            )


def test_rubric_evaluation_scope_items_and_evidence(tmp_path):
    manager = DatabaseManager(data_dir=tmp_path / "data")
    ids = _seed_run(manager)

    with manager.transaction("operational") as connection:
        connection.execute(
            "INSERT INTO rubric_versions "
            "(rubric_version_id, rubric_id, version_number, modality, language, "
            "schema_version, rubric_definition, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rubric-version-1",
                "ACT_RUBRIC_V0",
                "0.2",
                "ACT",
                "fa",
                "0.1",
                "{}",
                ids["now"],
            ),
        )

        connection.execute(
            "INSERT INTO evaluations "
            "(evaluation_id, run_id, session_id, evaluation_scope, "
            "rubric_version_id, transcript_manifest, evaluation_revision, "
            "status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "evaluation-session-1",
                ids["run_id"],
                ids["session_id"],
                "session",
                "rubric-version-1",
                "[]",
                1,
                "completed",
                ids["now"],
            ),
        )

        connection.execute(
            "INSERT INTO evaluation_items "
            "(evaluation_item_id, evaluation_id, competency_id, rating_code, "
            "justification) VALUES (?, ?, ?, ?, ?)",
            (
                "evaluation-item-1",
                "evaluation-session-1",
                "ACT_COMPETENCY_001",
                "2",
                "Evidence-based justification.",
            ),
        )

        connection.execute(
            "INSERT INTO evaluation_evidence "
            "(evaluation_item_id, message_id, evidence_role, start_offset, "
            "end_offset, evidence_excerpt) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "evaluation-item-1",
                ids["message_id"],
                "supporting",
                0,
                3,
                "Ava",
            ),
        )

        connection.execute(
            "INSERT INTO evaluations "
            "(evaluation_id, run_id, evaluation_scope, rubric_version_id, "
            "transcript_manifest, evaluation_revision, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "evaluation-longitudinal-1",
                ids["run_id"],
                "longitudinal",
                "rubric-version-1",
                "[]",
                1,
                "pending",
                ids["now"],
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO evaluation_items "
                "(evaluation_item_id, evaluation_id, competency_id, rating_code) "
                "VALUES (?, ?, ?, ?)",
                (
                    "evaluation-item-duplicate",
                    "evaluation-session-1",
                    "ACT_COMPETENCY_001",
                    "3",
                ),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with manager.transaction("operational") as connection:
            connection.execute(
                "INSERT INTO evaluations "
                "(evaluation_id, run_id, session_id, evaluation_scope, "
                "rubric_version_id, transcript_manifest, evaluation_revision, "
                "status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "invalid-longitudinal-evaluation",
                    ids["run_id"],
                    ids["session_id"],
                    "longitudinal",
                    "rubric-version-1",
                    "[]",
                    1,
                    "pending",
                    ids["now"],
                ),
            )
