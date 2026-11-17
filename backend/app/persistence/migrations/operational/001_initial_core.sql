CREATE TABLE cases (
    case_id TEXT PRIMARY KEY,
    case_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE case_versions (
    case_version_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    version_number TEXT NOT NULL,
    modality TEXT NOT NULL,
    language TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, version_number),
    UNIQUE (case_id, case_version_id),
    FOREIGN KEY (case_id) REFERENCES cases(case_id)
);

CREATE TABLE public_case_profiles (
    case_version_id TEXT PRIMARY KEY,
    age INTEGER,
    occupation TEXT,
    presenting_concerns TEXT NOT NULL DEFAULT '[]',
    initial_disclosure TEXT,
    profile_metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (case_version_id)
        REFERENCES case_versions(case_version_id),
    CHECK (age IS NULL OR age > 0)
);

CREATE TABLE simulation_runs (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    case_version_id TEXT NOT NULL,
    modality TEXT NOT NULL,
    language TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('initialized', 'active', 'completed', 'interrupted', 'failed')
    ),
    configuration_version TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id),
    FOREIGN KEY (case_id, case_version_id)
        REFERENCES case_versions(case_id, case_version_id)
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_number INTEGER NOT NULL CHECK (session_number BETWEEN 1 AND 3),
    status TEXT NOT NULL CHECK (
        status IN ('initialized', 'active', 'completed', 'interrupted', 'failed')
    ),
    transcript_version INTEGER NOT NULL DEFAULT 1
        CHECK (transcript_version >= 1),
    started_at TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (run_id, session_number),
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id)
);

CREATE TABLE model_runs (
    model_run_id TEXT PRIMARY KEY,
    run_id TEXT,
    session_id TEXT,
    component TEXT NOT NULL CHECK (
        component IN ('patient_agent', 'evaluator_agent')
    ),
    provider TEXT NOT NULL,
    model_identifier TEXT NOT NULL,
    model_version TEXT,
    model_artifact_digest TEXT,
    prompt_id TEXT,
    prompt_version TEXT,
    input_schema_version TEXT,
    output_schema_version TEXT,
    generation_parameters TEXT NOT NULL DEFAULT '{}',
    input_hash TEXT,
    output_hash TEXT,
    random_seed INTEGER,
    execution_status TEXT NOT NULL CHECK (
        execution_status IN ('in_progress', 'completed', 'failed')
    ),
    output_validation_status TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (run_id) REFERENCES simulation_runs(run_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number >= 1),
    role TEXT NOT NULL CHECK (role IN ('therapist', 'patient')),
    content TEXT NOT NULL CHECK (length(content) > 0),
    model_run_id TEXT,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (session_id, sequence_number),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (model_run_id) REFERENCES model_runs(model_run_id)
);

CREATE TABLE interaction_requests (
    request_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    therapist_message_id TEXT,
    patient_message_id TEXT,
    processing_status TEXT NOT NULL CHECK (
        processing_status IN ('in_progress', 'completed', 'failed')
    ),
    error_code TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE (session_id, idempotency_key),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (therapist_message_id) REFERENCES messages(message_id),
    FOREIGN KEY (patient_message_id) REFERENCES messages(message_id)
);

CREATE TABLE audit_events (
    audit_event_id TEXT PRIMARY KEY,
    component TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    run_id TEXT,
    session_id TEXT,
    operation_status TEXT NOT NULL,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_case_versions_case
    ON case_versions(case_id);

CREATE INDEX idx_simulation_runs_case
    ON simulation_runs(case_id);

CREATE INDEX idx_sessions_run
    ON sessions(run_id, session_number);

CREATE INDEX idx_model_runs_session
    ON model_runs(session_id);

CREATE INDEX idx_messages_session_sequence
    ON messages(session_id, sequence_number);

CREATE INDEX idx_interaction_requests_session
    ON interaction_requests(session_id);

CREATE INDEX idx_audit_events_entity
    ON audit_events(entity_type, entity_id);
