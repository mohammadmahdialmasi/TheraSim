"""Shared validation helpers for domain repositories."""

import json
import sqlite3
from collections.abc import Mapping, Sequence


def json_text(value, field_name):
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON serializable.") from exc


def require_mapping(value, field_name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping.")


def require_message_for_run(connection, message_id, run_id, role=None):
    row = connection.execute(
        """
        SELECT
            m.message_id, m.session_id, m.sequence_number,
            m.role, m.content, s.run_id
        FROM messages AS m
        JOIN sessions AS s ON s.session_id = m.session_id
        WHERE m.message_id = ?
        """,
        (message_id,),
    ).fetchone()

    if row is None:
        raise ValueError("Referenced message does not exist.")

    if row["run_id"] != run_id:
        raise ValueError("Referenced message belongs to another run.")

    if role is not None and row["role"] != role:
        raise ValueError(f"Referenced message must have role {role}.")

    return row


def require_session_for_run(connection, session_id, run_id):
    row = connection.execute(
        """
        SELECT session_id, run_id, session_number, status
        FROM sessions
        WHERE session_id = ? AND run_id = ?
        """,
        (session_id, run_id),
    ).fetchone()

    if row is None:
        raise ValueError("Session does not belong to the specified run.")

    return row


def require_offsets(content, start_offset, end_offset):
    if start_offset is None and end_offset is None:
        return

    if start_offset is None or end_offset is None:
        raise ValueError("Both evidence offsets must be supplied together.")

    if (
        isinstance(start_offset, bool)
        or not isinstance(start_offset, int)
        or isinstance(end_offset, bool)
        or not isinstance(end_offset, int)
    ):
        raise ValueError("Evidence offsets must be integers.")

    if start_offset < 0 or end_offset < start_offset:
        raise ValueError("Evidence offset range is invalid.")

    if end_offset > len(content):
        raise ValueError("Evidence offset exceeds message length.")


def require_text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")


def require_sequence(value, name):
    if (
        isinstance(value, (str, bytes, bytearray))
        or not isinstance(value, Sequence)
    ):
        raise ValueError(f"{name} must be a sequence.")
