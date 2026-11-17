"""Persistence operations for the single local reviewer account."""

import sqlite3


class LocalAuthRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_user(self) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT user_id, reviewer_name, password_hash, created_at
            FROM local_auth_users
            WHERE user_id = 'local-reviewer'
            """
        ).fetchone()

    def create_user(
        self,
        *,
        reviewer_name: str,
        password_hash: str,
        created_at: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO local_auth_users(
                user_id, reviewer_name, password_hash, created_at
            )
            VALUES ('local-reviewer', ?, ?, ?)
            """,
            (reviewer_name, password_hash, created_at),
        )

    def create_session(
        self,
        *,
        session_id: str,
        token_sha256: str,
        created_at: str,
        expires_at: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO local_auth_sessions(
                session_id, user_id, token_sha256, created_at, expires_at
            )
            VALUES (?, 'local-reviewer', ?, ?, ?)
            """,
            (session_id, token_sha256, created_at, expires_at),
        )

    def get_user_for_token(
        self,
        *,
        token_sha256: str,
        now: str,
    ) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT users.user_id, users.reviewer_name
            FROM local_auth_sessions AS sessions
            JOIN local_auth_users AS users
              ON users.user_id = sessions.user_id
            WHERE sessions.token_sha256 = ?
              AND sessions.revoked_at IS NULL
              AND sessions.expires_at > ?
            """,
            (token_sha256, now),
        ).fetchone()

    def revoke_session(
        self,
        *,
        token_sha256: str,
        revoked_at: str,
    ) -> None:
        self._connection.execute(
            """
            UPDATE local_auth_sessions
            SET revoked_at = ?
            WHERE token_sha256 = ? AND revoked_at IS NULL
            """,
            (revoked_at, token_sha256),
        )

    def delete_expired_sessions(self, *, now: str) -> None:
        self._connection.execute(
            """
            DELETE FROM local_auth_sessions
            WHERE expires_at <= ? OR revoked_at IS NOT NULL
            """,
            (now,),
        )

    def prune_login_attempts(self, *, before: str) -> None:
        self._connection.execute(
            "DELETE FROM local_auth_login_attempts WHERE attempted_at <= ?",
            (before,),
        )

    def count_login_attempts(
        self,
        *,
        client_sha256: str,
        since: str,
    ) -> int:
        return self._connection.execute(
            """
            SELECT COUNT(*)
            FROM local_auth_login_attempts
            WHERE client_sha256 = ? AND attempted_at > ?
            """,
            (client_sha256, since),
        ).fetchone()[0]

    def oldest_login_attempt(
        self,
        *,
        client_sha256: str,
        since: str,
    ) -> sqlite3.Row | None:
        return self._connection.execute(
            """
            SELECT attempted_at
            FROM local_auth_login_attempts
            WHERE client_sha256 = ? AND attempted_at > ?
            ORDER BY attempted_at
            LIMIT 1
            """,
            (client_sha256, since),
        ).fetchone()

    def record_login_attempt(
        self,
        *,
        attempt_id: str,
        client_sha256: str,
        attempted_at: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT INTO local_auth_login_attempts(
                attempt_id, client_sha256, attempted_at
            )
            VALUES (?, ?, ?)
            """,
            (attempt_id, client_sha256, attempted_at),
        )

    def clear_login_attempts(self, *, client_sha256: str) -> None:
        self._connection.execute(
            "DELETE FROM local_auth_login_attempts WHERE client_sha256 = ?",
            (client_sha256,),
        )
