ALTER TABLE sessions
ADD COLUMN transcript_hash TEXT;

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
 AND NEW.transcript_hash IS NOT OLD.transcript_hash
BEGIN
    SELECT RAISE(ABORT, 'completed_transcript_hash_is_immutable');
END;
