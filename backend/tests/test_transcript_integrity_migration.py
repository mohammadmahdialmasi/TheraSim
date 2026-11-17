import sqlite3

import pytest

from app.persistence.database import DatabaseManager


@pytest.fixture
def manager(tmp_path):
    result = DatabaseManager(data_dir=tmp_path / "transcript-integrity")
    result.initialize()
    return result


def seed_completed_session(manager):
    """Create a completed session containing one transcript message."""

    with manager.transaction("operational") as connection:
        connection.execute(
            """
            INSERT INTO cases (
                case_id, case_code, display_name,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "case-1",
                "CASE-001",
                "Synthetic Case",
                "active",
                "2026-11-16T12:00:00Z",
                "2026-11-16T12:00:00Z",
            ),
        )

        connection.execute(
            """
            INSERT INTO case_versions (
                case_version_id, case_id, version_number,
                modality, language, schema_version,
                content_hash, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "version-1",
                "case-1",
                "1.0",
                "ACT",
                "fa",
                "0.2",
                None,
                "2026-11-16T12:00:00Z",
            ),
        )

        connection.execute(
            """
            INSERT INTO simulation_runs (
                run_id, case_id, case_version_id,
                modality, language, status,
                configuration_version, started_at,
                completed_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-1",
                "case-1",
                "version-1",
                "ACT",
                "fa",
                "active",
                "0.1.0",
                "2026-11-16T12:00:00Z",
                None,
                "2026-11-16T12:00:00Z",
            ),
        )

        connection.execute(
            """
            INSERT INTO sessions (
                session_id, run_id, session_number,
                status, transcript_version,
                started_at, ended_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-1",
                "run-1",
                1,
                "active",
                1,
                "2026-11-16T12:00:00Z",
                None,
                "2026-11-16T12:00:00Z",
            ),
        )

        connection.execute(
            """
            INSERT INTO messages (
                message_id, session_id, sequence_number,
                role, content, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "message-1",
                "session-1",
                1,
                "therapist",
                "سلام. امروز چه چیزی برای شما مهم است؟",
                "2026-11-16T12:01:00Z",
            ),
        )

        connection.execute(
            """
            UPDATE sessions
            SET status = 'completed',
                ended_at = ?
            WHERE session_id = ?
            """,
            (
                "2026-11-16T12:30:00Z",
                "session-1",
            ),
        )


def test_migration_adds_transcript_hash_and_version(manager):
    migrations = manager.initialize()

    assert migrations["operational"] == [
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
    ]

    with manager.connection("operational") as connection:
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(sessions)"
            )
        }

        triggers = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                """
            )
        }

    assert "transcript_hash" in columns

    assert {
        "messages_reject_insert_after_session_completion",
        "messages_reject_update_after_session_completion",
        "messages_reject_delete_after_session_completion",
        "completed_session_status_is_terminal",
        "completed_transcript_hash_is_immutable",
    }.issubset(triggers)


def test_completed_session_rejects_new_messages(manager):
    seed_completed_session(manager)

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
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "message-2",
                    "session-1",
                    2,
                    "patient",
                    "پاسخ جدید",
                    "2026-11-16T12:31:00Z",
                ),
            )


def test_completed_session_rejects_message_updates(manager):
    seed_completed_session(manager)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="completed_session_transcript_immutable",
    ):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                UPDATE messages
                SET content = ?
                WHERE message_id = ?
                """,
                ("متن تغییر یافته", "message-1"),
            )


def test_completed_session_rejects_message_deletions(manager):
    seed_completed_session(manager)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="completed_session_transcript_immutable",
    ):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                DELETE FROM messages
                WHERE message_id = ?
                """,
                ("message-1",),
            )


def test_completed_session_cannot_be_reopened(manager):
    seed_completed_session(manager)

    with pytest.raises(
        sqlite3.IntegrityError,
        match="completed_session_status_is_terminal",
    ):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                UPDATE sessions
                SET status = 'active'
                WHERE session_id = ?
                """,
                ("session-1",),
            )


def test_transcript_hash_can_be_set_once_but_not_replaced(manager):
    seed_completed_session(manager)

    with manager.transaction("operational") as connection:
        connection.execute(
            """
            UPDATE sessions
            SET transcript_hash = ?
            WHERE session_id = ?
            """,
            ("first-hash", "session-1"),
        )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="completed_transcript_hash_is_immutable",
    ):
        with manager.transaction("operational") as connection:
            connection.execute(
                """
                UPDATE sessions
                SET transcript_hash = ?
                WHERE session_id = ?
                """,
                ("second-hash", "session-1"),
            )

    with manager.connection("operational") as connection:
        stored_hash = connection.execute(
            """
            SELECT transcript_hash
            FROM sessions
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()["transcript_hash"]

    assert stored_hash == "first-hash"
