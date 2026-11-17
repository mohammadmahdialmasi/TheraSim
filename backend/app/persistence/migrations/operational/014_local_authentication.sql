CREATE TABLE local_auth_users (
    user_id TEXT PRIMARY KEY CHECK (user_id = 'local-reviewer'),
    reviewer_name TEXT NOT NULL CHECK (length(trim(reviewer_name)) BETWEEN 1 AND 80),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE local_auth_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY (user_id)
        REFERENCES local_auth_users(user_id)
);

CREATE INDEX idx_local_auth_sessions_user_expiry
    ON local_auth_sessions(user_id, expires_at);
