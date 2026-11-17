"""Single-user local authentication with expiring bearer sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import math
import secrets
import uuid

from app.persistence.database import DatabaseManager
from app.persistence.repositories.local_auth import LocalAuthRepository


PASSWORD_SCRYPT_N = 1 << 15
PASSWORD_SCRYPT_R = 8
PASSWORD_SCRYPT_P = 1
PASSWORD_DERIVED_KEY_LENGTH = 32
PASSWORD_SALT_LENGTH = 16
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 1024
SESSION_LIFETIME = timedelta(hours=8)
LOGIN_ATTEMPT_WINDOW = timedelta(minutes=15)
LOGIN_ATTEMPT_LIMIT = 5
LOCAL_REVIEWER_ID = "local-reviewer"


class LocalAuthError(RuntimeError):
    """Base error for local authentication failures."""


class LocalAuthAlreadyInitializedError(LocalAuthError):
    pass


class LocalAuthInvalidCredentialsError(LocalAuthError):
    pass


class LocalAuthInvalidPasswordError(LocalAuthError):
    pass


class LocalAuthInvalidReviewerNameError(LocalAuthError):
    pass


class LocalAuthTokenError(LocalAuthError):
    pass


class LocalAuthRateLimitedError(LocalAuthError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many local login attempts.")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    reviewer_name: str


@dataclass(frozen=True)
class AuthSession:
    token: str
    expires_at: str
    user: AuthenticatedUser


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(PASSWORD_SALT_LENGTH)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_DERIVED_KEY_LENGTH,
        maxmem=128 * 1024 * 1024,
    )
    return (
        f"scrypt${PASSWORD_SCRYPT_N}${PASSWORD_SCRYPT_R}$"
        f"{PASSWORD_SCRYPT_P}${_encode(salt)}${_encode(derived_key)}"
    )


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, key_value = stored_hash.split("$")
        if (
            algorithm != "scrypt"
            or int(n) != PASSWORD_SCRYPT_N
            or int(r) != PASSWORD_SCRYPT_R
            or int(p) != PASSWORD_SCRYPT_P
        ):
            return False
        salt = _decode(salt_value)
        expected_key = _decode(key_value)
    except (ValueError, TypeError):
        return False

    if (
        len(salt) != PASSWORD_SALT_LENGTH
        or len(expected_key) != PASSWORD_DERIVED_KEY_LENGTH
    ):
        return False

    actual_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=PASSWORD_SCRYPT_N,
        r=PASSWORD_SCRYPT_R,
        p=PASSWORD_SCRYPT_P,
        dklen=PASSWORD_DERIVED_KEY_LENGTH,
        maxmem=128 * 1024 * 1024,
    )
    return hmac.compare_digest(actual_key, expected_key)


class LocalAuthService:
    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    def is_initialized(self) -> bool:
        with self._database_manager.connection("operational") as connection:
            return LocalAuthRepository(connection).get_user() is not None

    def initialize(
        self,
        *,
        reviewer_name: str,
        password: str,
    ) -> AuthSession:
        normalized_name = reviewer_name.strip()
        if not 1 <= len(normalized_name) <= 80:
            raise LocalAuthInvalidReviewerNameError(
                "Reviewer name must be between 1 and 80 characters."
            )
        self._validate_password(password)
        password_hash = _hash_password(password)
        return self._create_first_session(
            reviewer_name=normalized_name,
            password_hash=password_hash,
        )

    def login(
        self,
        *,
        password: str,
        client_key: str = "local-client",
    ) -> AuthSession:
        if not isinstance(client_key, str) or not client_key.strip():
            raise ValueError("client_key must be non-empty text.")
        client_sha256 = hashlib.sha256(
            client_key.strip().encode("utf-8")
        ).hexdigest()
        now = _utc_now()
        now_text = _format_timestamp(now)
        cutoff = _format_timestamp(now - LOGIN_ATTEMPT_WINDOW)
        with self._database_manager.transaction("operational") as connection:
            repository = LocalAuthRepository(connection)
            repository.prune_login_attempts(before=cutoff)
            attempt_count = repository.count_login_attempts(
                client_sha256=client_sha256,
                since=cutoff,
            )
            if attempt_count >= LOGIN_ATTEMPT_LIMIT:
                oldest = repository.oldest_login_attempt(
                    client_sha256=client_sha256,
                    since=cutoff,
                )
                if oldest is None:
                    raise LocalAuthError(
                        "Login throttle state could not be retrieved."
                    )
                oldest_at = datetime.fromisoformat(
                    oldest["attempted_at"].replace("Z", "+00:00")
                )
                retry_after = max(
                    1,
                    math.ceil(
                        (
                            oldest_at + LOGIN_ATTEMPT_WINDOW - now
                        ).total_seconds()
                    ),
                )
                raise LocalAuthRateLimitedError(retry_after)
            repository.record_login_attempt(
                attempt_id="login-attempt-" + uuid.uuid4().hex,
                client_sha256=client_sha256,
                attempted_at=now_text,
            )
            user = repository.get_user()

        if (
            not password
            or len(password) > PASSWORD_MAX_LENGTH
            or user is None
            or not _verify_password(password, user["password_hash"])
        ):
            raise LocalAuthInvalidCredentialsError("Invalid credentials.")

        token = secrets.token_urlsafe(32)
        expires_at = _format_timestamp(now + SESSION_LIFETIME)
        with self._database_manager.transaction("operational") as connection:
            repository = LocalAuthRepository(connection)
            repository.clear_login_attempts(client_sha256=client_sha256)
            repository.delete_expired_sessions(now=_format_timestamp(now))
            repository.create_session(
                session_id="auth-session-" + uuid.uuid4().hex,
                token_sha256=self._token_hash(token),
                created_at=_format_timestamp(now),
                expires_at=expires_at,
            )
        return AuthSession(
            token=token,
            expires_at=expires_at,
            user=AuthenticatedUser(
                user_id=user["user_id"],
                reviewer_name=user["reviewer_name"],
            ),
        )

    def authenticate(self, token: str) -> AuthenticatedUser:
        if not token or len(token) > 256:
            raise LocalAuthTokenError("Authentication is required.")
        now = _format_timestamp(_utc_now())
        with self._database_manager.connection("operational") as connection:
            row = LocalAuthRepository(connection).get_user_for_token(
                token_sha256=self._token_hash(token),
                now=now,
            )
        if row is None:
            raise LocalAuthTokenError("Authentication is required.")
        return AuthenticatedUser(
            user_id=row["user_id"],
            reviewer_name=row["reviewer_name"],
        )

    def logout(self, token: str) -> None:
        if not token or len(token) > 256:
            return
        with self._database_manager.transaction("operational") as connection:
            LocalAuthRepository(connection).revoke_session(
                token_sha256=self._token_hash(token),
                revoked_at=_format_timestamp(_utc_now()),
            )

    def _create_first_session(
        self,
        *,
        reviewer_name: str,
        password_hash: str,
    ) -> AuthSession:
        now = _utc_now()
        token = secrets.token_urlsafe(32)
        expires_at = _format_timestamp(now + SESSION_LIFETIME)
        with self._database_manager.transaction("operational") as connection:
            repository = LocalAuthRepository(connection)
            if repository.get_user() is not None:
                raise LocalAuthAlreadyInitializedError(
                    "The local reviewer account is already initialized."
                )
            repository.create_user(
                reviewer_name=reviewer_name,
                password_hash=password_hash,
                created_at=_format_timestamp(now),
            )
            repository.create_session(
                session_id="auth-session-" + uuid.uuid4().hex,
                token_sha256=self._token_hash(token),
                created_at=_format_timestamp(now),
                expires_at=expires_at,
            )
        return AuthSession(
            token=token,
            expires_at=expires_at,
            user=AuthenticatedUser(
                user_id=LOCAL_REVIEWER_ID,
                reviewer_name=reviewer_name,
            ),
        )

    @staticmethod
    def _validate_password(password: str) -> None:
        if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
            raise LocalAuthInvalidPasswordError(
                "Password must be between 12 and 1024 characters."
            )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()
