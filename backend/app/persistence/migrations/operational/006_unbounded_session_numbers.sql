-- therasim: requires_foreign_keys_off
-- Rebuild the parent table to remove the original MVP session-number ceiling.
DROP TRIGGER messages_reject_insert_after_session_completion;
DROP TRIGGER messages_reject_update_after_session_completion;
DROP TRIGGER messages_reject_delete_after_session_completion;

CREATE TABLE sessions_unbounded (
    session_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_number INTEGER NOT NULL CHECK (session_number >= 1),
    status TEXT NOT NULL CHECK (
        status IN ('initialized', 'active', 'completed', 'interrupted', 'failed')
    ),
    transcript_version INTEGER NOT NULL DEFAULT 1
        CHECK (transcript_version >= 1),
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL,
    transcript_hash TEXT,
    UNIQUE (run_id, session_number),
    UNIQUE (session_id, run_id),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
);

INSERT INTO sessions_unbounded (
    session_id,
    run_id,
    session_number,
    status,
    transcript_version,
    started_at,
    ended_at,
    created_at,
    transcript_hash
)
SELECT
    session_id,
    run_id,
    session_number,
    status,
    transcript_version,
    started_at,
    ended_at,
    created_at,
    transcript_hash
FROM sessions;

DROP TABLE sessions;
ALTER TABLE sessions_unbounded RENAME TO sessions;

CREATE INDEX idx_sessions_run
    ON sessions(run_id, session_number);

CREATE TRIGGER completed_session_status_is_terminal
BEFORE UPDATE OF status ON sessions
FOR EACH ROW
WHEN OLD.status = 'completed'
 AND NEW.status <> 'completed'
BEGIN
    SELECT RAISE(ABORT, 'completed_session_status_is_terminal');
END;

CREATE TRIGGER completed_transcript_hash_is_immutable
BEFORE UPDATE OF transcript_hash ON sessions
FOR EACH ROW
WHEN OLD.transcript_hash IS NOT NULL
 AND OLD.transcript_hash IS NOT NEW.transcript_hash
BEGIN
    SELECT RAISE(ABORT, 'completed_transcript_hash_is_immutable');
END;

CREATE TRIGGER messages_reject_insert_after_session_completion
BEFORE INSERT ON messages
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM sessions
    WHERE session_id = NEW.session_id
      AND status = 'completed'
)
BEGIN
    SELECT RAISE(ABORT, 'completed_session_transcript_immutable');
END;

CREATE TRIGGER messages_reject_update_after_session_completion
BEFORE UPDATE ON messages
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM sessions
    WHERE session_id = OLD.session_id
      AND status = 'completed'
)
OR EXISTS (
    SELECT 1
    FROM sessions
    WHERE session_id = NEW.session_id
      AND status = 'completed'
)
BEGIN
    SELECT RAISE(ABORT, 'completed_session_transcript_immutable');
END;

CREATE TRIGGER messages_reject_delete_after_session_completion
BEFORE DELETE ON messages
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM sessions
    WHERE session_id = OLD.session_id
      AND status = 'completed'
)
BEGIN
    SELECT RAISE(ABORT, 'completed_session_transcript_immutable');
END;
