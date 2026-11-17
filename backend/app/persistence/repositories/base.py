"""Shared connection ownership contract for SQLite repositories."""

import sqlite3


class ConnectionBoundRepository:
    """Uses a caller-owned SQLite connection.

    Repositories do not open, commit, roll back, or close connections.
    The service/orchestrator layer owns transaction boundaries.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        if not isinstance(connection, sqlite3.Connection):
            raise TypeError("A valid sqlite3.Connection is required.")

        self._connection = connection

    @staticmethod
    def require_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")

    @staticmethod
    def require_pagination(limit: int, offset: int) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("Limit must be an integer.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError("Offset must be an integer.")

        if not 1 <= limit <= 200:
            raise ValueError("Limit must be between 1 and 200.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")
