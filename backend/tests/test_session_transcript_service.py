import hashlib
import json
import sqlite3

import pytest

from app.persistence.database import DatabaseManager
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.operations import AuditRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)
from app.services.cases import CaseService
from app.services.runs import RunService
from app.services.sessions import (
    SessionInvalidCompletionReasonError,
    SessionNotFoundError,
    SessionService,
)


NOW = "2026-11-16T12:00:00Z"


@pytest.fixture
def session_context(tmp_path):
    manager = DatabaseManager(
        data_dir=tmp_path / "transcript-service-tests"
    )
    manager.initialize()

    cases = CaseService(manager)

    cases.create_case(
        case_id="case-1",
        case_code="CASE-001",
        display_name="Synthetic Test Case",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )

    cases.create_case_version(
        case_version_id="version-1",
        case_id="case-1",
        version_number="1.0",
        modality="ACT",
        language="fa",
        schema_version="0.2",
        created_at=NOW,
    )

    with manager.transaction("restricted") as connection:
        RestrictedCaseRepository(connection).create_profile(
            restricted_profile_id="profile-1",
            case_id="case-1",
            case_version_id="version-1",
            clinical_formulation={"synthetic": True},
            created_at=NOW,
        )

    runs = RunService(manager)

    runs.create_run(
        run_id="run-1",
        case_id="case-1",
        case_version_id="version-1",
        configuration_version="0.1",
        created_at=NOW,
    )

    runs.start_run(
        "run-1",
        started_at=NOW,
    )

    sessions = SessionService(manager)

    session = sessions.create_next_session(
        session_id="session-1",
        run_id="run-1",
        created_at=NOW,
    )

    return {
        "manager": manager,
        "sessions": sessions,
        "session": session,
    }


def add_messages(manager, messages):
    with manager.transaction("operational") as connection:
        repository = MessageRepository(connection)

        for message in messages:
            repository.create_message(
                message_id=message["message_id"],
                session_id="session-1",
                sequence_number=message["sequence_number"],
                role=message["role"],
                content=message["content"],
                created_at=message["created_at"],
            )


def expected_transcript_hash(messages):
    payload = [
        {
            "message_id": message["message_id"],
            "sequence_number": message["sequence_number"],
            "role": message["role"],
            "content": message["content"],
            "created_at": message["created_at"],
        }
        for message in messages
    ]

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


def test_completion_persists_correct_sha256_and_audit(session_context):
    manager = session_context["manager"]
    sessions = session_context["sessions"]

    messages = [
        {
            "message_id": "message-1",
            "sequence_number": 1,
            "role": "therapist",
            "content": "سلام. امروز چه چیزی برای شما مهم است؟",
            "created_at": "2026-11-16T12:01:00Z",
        },
        {
            "message_id": "message-2",
            "sequence_number": 2,
            "role": "patient",
            "content": "این روزها اضطراب زیادی دارم.",
            "created_at": "2026-11-16T12:02:00Z",
        },
    ]

    add_messages(manager, messages)

    result = sessions.complete_session(
        "session-1",
        completed_at="2026-11-16T12:30:00Z",
        completion_reason="normal",
    )

    expected_hash = expected_transcript_hash(messages)

    assert result.status == "completed"
    assert result.ended_at == "2026-11-16T12:30:00Z"

    with manager.connection("operational") as connection:
        stored = connection.execute(
            """
            SELECT transcript_hash
            FROM sessions
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()

        events = AuditRepository(connection).list_for_entity(
            "session",
            "session-1",
        )

    assert stored["transcript_hash"] == expected_hash
    assert len(stored["transcript_hash"]) == 64

    completion_events = [
        event for event in events
        if event["operation_type"] == "session_completed"
    ]

    assert len(completion_events) == 1

    metadata = json.loads(completion_events[0]["metadata"])
    assert metadata["completion_reason"] == "normal"
    assert metadata["transcript_hash"] == expected_hash


def test_empty_transcript_has_deterministic_sha256(session_context):
    manager = session_context["manager"]
    sessions = session_context["sessions"]

    result = sessions.complete_session(
        "session-1",
        completed_at="2026-11-16T12:30:00Z",
    )

    with manager.connection("operational") as connection:
        row = connection.execute(
            """
            SELECT transcript_hash
            FROM sessions
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()

    assert result.status == "completed"
    assert row["transcript_hash"] == hashlib.sha256(b"[]").hexdigest()


def test_repeated_completion_does_not_change_result_or_duplicate_audit(
    session_context,
):
    manager = session_context["manager"]
    sessions = session_context["sessions"]

    messages = [
        {
            "message_id": "message-1",
            "sequence_number": 1,
            "role": "therapist",
            "content": "Let's review today's session.",
            "created_at": "2026-11-16T12:01:00Z",
        },
    ]

    add_messages(manager, messages)

    first = sessions.complete_session(
        "session-1",
        completed_at="2026-11-16T12:30:00Z",
        completion_reason="normal",
    )

    with manager.connection("operational") as connection:
        before = connection.execute(
            """
            SELECT ended_at, transcript_hash
            FROM sessions
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()

    second = sessions.complete_session(
        "session-1",
        completed_at="2026-11-16T13:00:00Z",
        completion_reason="trainee_ended",
    )

    with manager.connection("operational") as connection:
        after = connection.execute(
            """
            SELECT ended_at, transcript_hash
            FROM sessions
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()

        events = AuditRepository(connection).list_for_entity(
            "session",
            "session-1",
        )

    completion_events = [
        event for event in events
        if event["operation_type"] == "session_completed"
    ]

    assert first == second
    assert before["ended_at"] == after["ended_at"]
    assert before["transcript_hash"] == after["transcript_hash"]
    assert len(completion_events) == 1


def test_legacy_completed_session_hash_is_backfilled(session_context):
    manager = session_context["manager"]
    sessions = session_context["sessions"]

    messages = [
        {
            "message_id": "message-1",
            "sequence_number": 1,
            "role": "therapist",
            "content": "Legacy transcript.",
            "created_at": "2026-11-16T12:01:00Z",
        },
    ]

    add_messages(manager, messages)

    # Simulate a session completed before migration 004.
    with manager.transaction("operational") as connection:
        connection.execute(
            """
            UPDATE sessions
            SET status = 'completed',
                ended_at = ?
            WHERE session_id = ?
            """,
            ("2026-11-16T12:30:00Z", "session-1"),
        )

    result = sessions.complete_session(
        "session-1",
        completed_at="2026-11-16T13:00:00Z",
    )

    with manager.connection("operational") as connection:
        row = connection.execute(
            """
            SELECT transcript_hash, ended_at
            FROM sessions
            WHERE session_id = ?
            """,
            ("session-1",),
        ).fetchone()

    assert result.status == "completed"
    assert row["transcript_hash"] == expected_transcript_hash(messages)
    assert row["ended_at"] == "2026-11-16T12:30:00Z"


def test_list_messages_returns_ordered_paginated_transcript(session_context):
    manager = session_context["manager"]
    sessions = session_context["sessions"]

    messages = [
        {
            "message_id": f"message-{number}",
            "sequence_number": number,
            "role": "therapist" if number % 2 else "patient",
            "content": f"Message {number}",
            "created_at": f"2026-11-16T12:0{number}:00Z",
        }
        for number in range(1, 4)
    ]

    add_messages(manager, messages)

    page, total = sessions.list_messages(
        "session-1",
        limit=2,
        offset=1,
    )

    assert total == 3
    assert [message.sequence_number for message in page] == [2, 3]
    assert [message.content for message in page] == [
        "Message 2",
        "Message 3",
    ]

    assert [message.role for message in page] == [
        "patient",
        "therapist",
    ]


def test_list_messages_rejects_invalid_pagination(session_context):
    sessions = session_context["sessions"]

    with pytest.raises(ValueError):
        sessions.list_messages(
            "session-1",
            limit=0,
        )

    with pytest.raises(ValueError):
        sessions.list_messages(
            "session-1",
            offset=-1,
        )

    with pytest.raises(ValueError):
        sessions.list_messages(
            "session-1",
            limit=True,
        )


def test_list_messages_rejects_missing_session(session_context):
    sessions = session_context["sessions"]

    with pytest.raises(SessionNotFoundError):
        sessions.list_messages("missing-session")


def test_completion_rejects_unsupported_reason(session_context):
    sessions = session_context["sessions"]

    with pytest.raises(SessionInvalidCompletionReasonError):
        sessions.complete_session(
            "session-1",
            completed_at="2026-11-16T12:30:00Z",
            completion_reason="unknown",
        )

    assert sessions.get_session("session-1").status == "active"
