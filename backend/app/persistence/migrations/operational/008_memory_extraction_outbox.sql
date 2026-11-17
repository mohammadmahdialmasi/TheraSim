CREATE TABLE memory_extraction_jobs (
    job_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    interaction_request_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'processing', 'completed', 'failed')
    ),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    candidate_count INTEGER NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    available_at TEXT NOT NULL,
    lease_owner TEXT,
    lease_expires_at TEXT,
    proposal_payload TEXT,
    output_hash TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),
    FOREIGN KEY (session_id, run_id)
        REFERENCES sessions(session_id, run_id),
    FOREIGN KEY (interaction_request_id)
        REFERENCES interaction_requests(request_id),
    CHECK (
        (status = 'processing'
            AND lease_owner IS NOT NULL
            AND lease_expires_at IS NOT NULL)
        OR
        (status <> 'processing'
            AND lease_owner IS NULL
            AND lease_expires_at IS NULL)
    ),
    CHECK (
        (status = 'completed' AND completed_at IS NOT NULL)
        OR
        (status <> 'completed' AND completed_at IS NULL)
    ),
    CHECK (
        (proposal_payload IS NULL AND output_hash IS NULL)
        OR
        (proposal_payload IS NOT NULL AND output_hash IS NOT NULL)
    ),
    CHECK (
        status <> 'completed'
        OR (proposal_payload IS NOT NULL AND output_hash IS NOT NULL)
    )
);

CREATE INDEX idx_memory_extraction_jobs_ready
    ON memory_extraction_jobs(status, available_at, created_at);

CREATE INDEX idx_memory_extraction_jobs_run
    ON memory_extraction_jobs(run_id, created_at);
