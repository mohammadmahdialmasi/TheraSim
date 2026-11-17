CREATE TABLE local_auth_login_attempts (
    attempt_id TEXT PRIMARY KEY,
    client_sha256 TEXT NOT NULL CHECK (length(client_sha256) = 64),
    attempted_at TEXT NOT NULL
);

CREATE INDEX idx_local_auth_login_attempts_client_time
    ON local_auth_login_attempts(client_sha256, attempted_at);
