import sqlite3
import shutil

import pytest

import app.persistence.migrations as migrations
from app.persistence.database import DatabaseManager
from app.persistence.repositories.operations import ModelRunRepository
from app.persistence.repositories.sessions import SessionRepository


NOW = "2026-11-17T10:00:00Z"


def test_upgrade_preserves_existing_sessions_and_references(
    tmp_path,
    monkeypatch,
):
    current_migrations_root = migrations.MIGRATIONS_ROOT
    legacy_migrations_root = tmp_path / "legacy-migrations"
    legacy_operational = legacy_migrations_root / "operational"
    legacy_operational.mkdir(parents=True)

    for migration_file in sorted(
        (current_migrations_root / "operational").glob("00[1-5]_*.sql")
    ):
        shutil.copyfile(
            migration_file,
            legacy_operational / migration_file.name,
        )

    monkeypatch.setattr(migrations, "MIGRATIONS_ROOT", legacy_migrations_root)
    manager = DatabaseManager(data_dir=tmp_path / "existing-database")
    migrations.apply_migrations(manager, "operational")

    with manager.transaction("operational") as connection:
        connection.execute(
            """
            INSERT INTO cases (
                case_id, case_code, display_name, status, created_at, updated_at
            ) VALUES ('case-1', 'CASE-001', 'Synthetic case', 'active', ?, ?)
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO case_versions (
                case_version_id, case_id, version_number, modality,
                language, schema_version, created_at
            ) VALUES ('version-1', 'case-1', '1.0', 'ACT', 'en', '0.2', ?)
            """,
            (NOW,),
        )
        connection.execute(
            """
            INSERT INTO simulation_runs (
                run_id, case_id, case_version_id, modality, language, status,
                configuration_version, created_at
            ) VALUES (
                'run-1', 'case-1', 'version-1', 'ACT', 'en', 'active', '0.1', ?
            )
            """,
            (NOW,),
        )

        for number in range(1, 4):
            session_id = f"session-{number}"
            message_id = f"message-{number}"
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, run_id, session_number, status,
                    transcript_version, started_at, created_at
                ) VALUES (?, 'run-1', ?, 'active', 1, ?, ?)
                """,
                (session_id, number, NOW, NOW),
            )
            model_run_id = None
            if number == 1:
                model_run_id = "model-run-legacy"
                connection.execute(
                    """
                    INSERT INTO model_runs (
                        model_run_id, run_id, session_id, component, provider,
                        model_identifier, execution_status,
                        output_validation_status, started_at, completed_at
                    ) VALUES (
                        ?, 'run-1', ?, 'patient_agent', 'ollama',
                        'legacy-model', 'completed', 'valid', ?, ?
                    )
                    """,
                    (model_run_id, session_id, NOW, NOW),
                )
            connection.execute(
                """
                INSERT INTO messages (
                    message_id, session_id, sequence_number, role, content,
                    model_run_id, created_at
                ) VALUES (?, ?, 1, 'patient', ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    f"Message for {session_id}",
                    model_run_id,
                    NOW,
                ),
            )
            connection.execute(
                """
                UPDATE sessions
                SET status = 'completed', ended_at = ?
                WHERE session_id = ?
                """,
                (NOW, session_id),
            )

        connection.execute(
            """
            INSERT INTO interaction_requests (
                request_id, session_id, idempotency_key, request_hash,
                therapist_message_id, processing_status, created_at, completed_at
            ) VALUES (
                'request-1', 'session-1', 'key-1', 'hash-1',
                'message-1', 'completed', ?, ?
            )
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO memory_items (
                memory_id, run_id, source_session_id, memory_type,
                information_class, content, confidence, status,
                memory_version, memory_scope, created_at, updated_at
            ) VALUES (
                'memory-legacy', 'run-1', 'session-1', 'reported_experience',
                'confirmed_fact', 'A preserved historical memory.', 0.9,
                'active', 1, 'semantic', ?, ?
            )
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            INSERT INTO memory_evidence (
                memory_id, message_id, relationship_type
            ) VALUES ('memory-legacy', 'message-1', 'supports')
            """
        )

    monkeypatch.setattr(
        migrations,
        "MIGRATIONS_ROOT",
        current_migrations_root,
    )
    applied = migrations.apply_migrations(manager, "operational")

    assert applied[-10:] == [
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
        sessions = connection.execute(
            """
            SELECT session_id, session_number, status
            FROM sessions
            WHERE run_id = 'run-1'
            ORDER BY session_number
            """
        ).fetchall()
        message_count = connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]
        request = connection.execute(
            """
            SELECT session_id, therapist_message_id
            FROM interaction_requests
            WHERE request_id = 'request-1'
            """
        ).fetchone()
        memory = connection.execute(
            """
            SELECT status, memory_version, memory_scope,
                   supersedes_memory_id, origin_interaction_request_id
            FROM memory_items
            WHERE memory_id = 'memory-legacy'
            """
        ).fetchone()
        preserved_model = connection.execute(
            """
            SELECT run_id, session_id, component, model_identifier,
                   execution_status
            FROM model_runs
            WHERE model_run_id = 'model-run-legacy'
            """
        ).fetchone()
        preserved_message = connection.execute(
            """
            SELECT model_run_id
            FROM messages
            WHERE message_id = 'message-1'
            """
        ).fetchone()
        assert preserved_model is not None
        assert preserved_model["session_id"] == "session-1"
        assert preserved_model["component"] == "patient_agent"
        assert preserved_model["model_identifier"] == "legacy-model"
        assert preserved_model["execution_status"] == "completed"
        assert preserved_message["model_run_id"] == "model-run-legacy"

        ModelRunRepository(connection).create_model_run(
            model_run_id="model-run-memory-extraction",
            run_id="run-1",
            session_id="session-1",
            component="memory_extraction_agent",
            provider="ollama",
            model_identifier="memory-model",
            execution_status="in_progress",
            started_at=NOW,
            generation_parameters={"temperature": 0.0, "max_tokens": 64},
            input_schema_version="0.1",
            output_schema_version="0.1",
            input_hash="sha256:input",
        )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        assert violations == []
        memory_evidence = connection.execute(
            """
            SELECT message_id, start_offset, end_offset
            FROM memory_evidence
            WHERE memory_id = 'memory-legacy'
            """
        ).fetchone()
        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        foreign_keys_enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

    assert [(row["session_id"], row["session_number"], row["status"]) for row in sessions] == [
        ("session-1", 1, "completed"),
        ("session-2", 2, "completed"),
        ("session-3", 3, "completed"),
    ]
    assert message_count == 3
    assert tuple(request) == ("session-1", "message-1")
    assert tuple(memory) == ("active", 1, "semantic", None, None)
    assert tuple(memory_evidence) == ("message-1", None, None)
    assert foreign_key_violations == []
    assert foreign_keys_enabled == 1

    with pytest.raises(
        sqlite3.IntegrityError,
        match="completed_session_transcript_immutable",
    ):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    message_id, session_id, sequence_number,
                    role, content, created_at
                ) VALUES ('message-late', 'session-1', 2, 'patient', 'late', ?)
                """,
                (NOW,),
            )

    with manager.transaction("operational") as connection:
        repository = SessionRepository(connection)
        assert repository.create_next_session(
            session_id="session-4",
            run_id="run-1",
            created_at=NOW,
        ) == 4
