ALTER TABLE interaction_requests
ADD COLUMN attempt_token TEXT;

ALTER TABLE interaction_requests
ADD COLUMN lease_expires_at TEXT;

ALTER TABLE interaction_requests
ADD COLUMN attempt_number INTEGER NOT NULL DEFAULT 0
CHECK (attempt_number >= 0);

ALTER TABLE interaction_requests
ADD COLUMN last_model_run_id TEXT
REFERENCES model_runs(model_run_id);

UPDATE interaction_requests
SET processing_status = 'completed',
    error_code = NULL,
    completed_at = COALESCE(completed_at, created_at)
WHERE processing_status = 'in_progress'
  AND patient_message_id IS NOT NULL;

UPDATE interaction_requests
SET processing_status = 'failed',
    error_code = 'recovery_required',
    completed_at = NULL
WHERE processing_status = 'in_progress'
  AND patient_message_id IS NULL;

CREATE INDEX idx_interaction_requests_recovery
ON interaction_requests(
    session_id,
    processing_status,
    lease_expires_at
);
