import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.persistence.repositories.messages import MessageRepository
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)


def calculate_expected_hash(messages):
    serialized = json.dumps(
        messages,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


@pytest.mark.parametrize("session_count", [1, 2, 5])
def test_complete_variable_length_run_end_to_end(
    tmp_path,
    monkeypatch,
    session_count,
):
    data_dir = tmp_path / f"variable-session-integration-{session_count}"
    monkeypatch.setenv("THERASIM_DATA_DIR", str(data_dir))

    with TestClient(app) as client:
        manager = app.state.database_manager
        case_service = app.state.case_service

        # 1. Prepare an active synthetic case and public version.
        case_service.create_case(
            case_id="e2e-case-1",
            case_code="E2E-001",
            display_name="Integration Test Case",
            status="active",
            created_at="2026-11-16T12:00:00Z",
            updated_at="2026-11-16T12:00:00Z",
        )

        case_service.create_case_version(
            case_version_id="e2e-version-1",
            case_id="e2e-case-1",
            version_number="1.0",
            modality="ACT",
            language="fa",
            schema_version="0.2",
            created_at="2026-11-16T12:00:00Z",
        )

        case_service.create_public_profile(
            case_version_id="e2e-version-1",
            age=27,
            occupation="Designer",
            presenting_concerns=["anxiety", "avoidance"],
            initial_disclosure="در موقعیت‌های اجتماعی مضطرب می‌شوم.",
            created_at="2026-11-16T12:00:00Z",
        )

        with manager.transaction("restricted") as connection:
            RestrictedCaseRepository(connection).create_profile(
                restricted_profile_id="e2e-profile-1",
                case_id="e2e-case-1",
                case_version_id="e2e-version-1",
                clinical_formulation={"synthetic": True},
                created_at="2026-11-16T12:00:00Z",
            )

        # 2. Create and start the run through the real API.
        response = client.post(
            "/api/v1/simulation-runs",
            json={
                "case_id": "e2e-case-1",
                "modality": "ACT",
                "language": "fa",
            },
        )

        assert response.status_code == 201, response.text

        run_data = response.json()["data"]
        run_id = run_data["run_id"]

        assert run_data["status"] == "initialized"
        assert run_data["case_version_id"] == "e2e-version-1"

        response = client.post(
            f"/api/v1/simulation-runs/{run_id}/start"
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "active"

        # 3. Exercise sequential sessions with a variable run length.
        completed_sessions = []

        for number in range(1, session_count + 1):
            response = client.post(
                f"/api/v1/simulation-runs/{run_id}/sessions",
                json={},
            )

            assert response.status_code == 201, response.text

            session_data = response.json()["data"]
            session_id = session_data["session_id"]

            assert session_data["session_number"] == number
            assert session_data["status"] == "active"

            # A second session must not open before completion.
            if number == 1:
                premature = client.post(
                    f"/api/v1/simulation-runs/{run_id}/sessions",
                    json={},
                )

                assert premature.status_code == 409
                assert premature.json()["detail"] == (
                    "session_order_violation"
                )

            # Persist two real database transcript records.
            messages = [
                {
                    "message_id": f"{session_id}-therapist",
                    "sequence_number": 1,
                    "role": "therapist",
                    "content": f"پیام درمانگر در جلسه {number}",
                    "created_at": f"2026-11-16T12:0{number}:00Z",
                },
                {
                    "message_id": f"{session_id}-patient",
                    "sequence_number": 2,
                    "role": "patient",
                    "content": f"پاسخ مراجع در جلسه {number}",
                    "created_at": f"2026-11-16T12:0{number}:30Z",
                },
            ]

            with manager.transaction("operational") as connection:
                repository = MessageRepository(connection)

                for message in messages:
                    repository.create_message(
                        message_id=message["message_id"],
                        session_id=session_id,
                        sequence_number=message["sequence_number"],
                        role=message["role"],
                        content=message["content"],
                        created_at=message["created_at"],
                    )

            # Verify therapist-visible transcript pagination.
            response = client.get(
                f"/api/v1/sessions/{session_id}/messages?limit=1&offset=0"
            )

            assert response.status_code == 200, response.text

            page = response.json()

            assert len(page["data"]) == 1
            assert page["data"][0]["role"] == "therapist"
            assert page["pagination"]["total"] == 2

            response = client.get(
                f"/api/v1/sessions/{session_id}/messages?limit=1&offset=1"
            )

            assert response.status_code == 200
            assert response.json()["data"][0]["role"] == "patient"

            # Complete the session.
            response = client.post(
                f"/api/v1/sessions/{session_id}/complete",
                json={"completion_reason": "normal"},
            )

            assert response.status_code == 200, response.text

            completion = response.json()["data"]

            assert completion["status"] == "completed"
            assert completion["session_id"] == session_id
            assert completion["ended_at"]

            original_end_time = completion["ended_at"]

            # Repeated completion must preserve the original result.
            repeated = client.post(
                f"/api/v1/sessions/{session_id}/complete",
                json={"completion_reason": "trainee_ended"},
            )

            assert repeated.status_code == 200, repeated.text
            assert (
                repeated.json()["data"]["ended_at"]
                == original_end_time
            )

            expected_hash = calculate_expected_hash(messages)

            with manager.connection("operational") as connection:
                stored = connection.execute(
                    """
                    SELECT status, ended_at, transcript_hash
                    FROM sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()

                completion_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_events
                    WHERE entity_type = 'session'
                      AND entity_id = ?
                      AND operation_type = 'session_completed'
                    """,
                    (session_id,),
                ).fetchone()[0]

            assert stored["status"] == "completed"
            assert stored["ended_at"] == original_end_time
            assert stored["transcript_hash"] == expected_hash
            assert completion_count == 1

            # Completed transcripts must reject new messages.
            with pytest.raises(sqlite3.IntegrityError):
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
                            f"{session_id}-forbidden",
                            session_id,
                            3,
                            "patient",
                            "این پیام نباید ذخیره شود.",
                            "2026-11-16T12:59:00Z",
                        ),
                    )

            completed_sessions.append(session_id)

        # 4. Verify the complete run session listing.
        response = client.get(
            f"/api/v1/simulation-runs/{run_id}/sessions"
        )

        assert response.status_code == 200

        listed_sessions = response.json()["data"]

        assert len(listed_sessions) == session_count
        assert [
            item["session_id"] for item in listed_sessions
        ] == completed_sessions

        assert all(
            item["status"] == "completed"
            for item in listed_sessions
        )

        # 5. Complete the run through its existing application service.
        response = client.post(
            f"/api/v1/simulation-runs/{run_id}/complete"
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "completed"
        assert response.json()["data"]["completed_at"]

        response = client.get(
            f"/api/v1/simulation-runs/{run_id}"
        )

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "completed"
        assert response.json()["data"]["session_count"] == session_count
