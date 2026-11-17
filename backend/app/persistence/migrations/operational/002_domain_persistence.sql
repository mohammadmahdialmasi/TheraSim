CREATE UNIQUE INDEX ux_simulation_runs_identity
    ON simulation_runs(run_id, case_id, case_version_id);

CREATE UNIQUE INDEX ux_sessions_identity
    ON sessions(session_id, run_id);

CREATE TABLE case_fact_disclosures (
    disclosure_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    case_version_id TEXT NOT NULL,
    case_fact_id TEXT NOT NULL,
    disclosure_status TEXT NOT NULL CHECK (
        disclosure_status IN (
            'not_disclosed',
            'candidate_disclosed',
            'confirmed_disclosed',
            'requires_review'
        )
    ),
    source_message_id TEXT,
    evidence_start_offset INTEGER,
    evidence_end_offset INTEGER,
    validation_method TEXT NOT NULL CHECK (length(validation_method) > 0),
    validation_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    UNIQUE (run_id, case_fact_id),

    FOREIGN KEY (run_id, case_id, case_version_id)
        REFERENCES simulation_runs(run_id, case_id, case_version_id),

    FOREIGN KEY (source_message_id)
        REFERENCES messages(message_id),

    CHECK (
        (evidence_start_offset IS NULL AND evidence_end_offset IS NULL)
        OR
        (
            evidence_start_offset IS NOT NULL
            AND evidence_end_offset IS NOT NULL
            AND evidence_start_offset >= 0
            AND evidence_end_offset >= evidence_start_offset
        )
    ),

    CHECK (
        disclosure_status <> 'confirmed_disclosed'
        OR source_message_id IS NOT NULL
    )
);

CREATE TABLE case_fact_disclosure_history (
    history_id TEXT PRIMARY KEY,
    disclosure_id TEXT NOT NULL,
    previous_status TEXT,
    new_status TEXT NOT NULL CHECK (
        new_status IN (
            'not_disclosed',
            'candidate_disclosed',
            'confirmed_disclosed',
            'requires_review'
        )
    ),
    source_message_id TEXT,
    evidence_description TEXT,
    operation_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,

    FOREIGN KEY (disclosure_id)
        REFERENCES case_fact_disclosures(disclosure_id),

    FOREIGN KEY (source_message_id)
        REFERENCES messages(message_id),

    CHECK (
        previous_status IS NULL
        OR previous_status IN (
            'not_disclosed',
            'candidate_disclosed',
            'confirmed_disclosed',
            'requires_review'
        )
    )
);

CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT,
    sequence_number INTEGER NOT NULL CHECK (sequence_number >= 1),
    event_type TEXT NOT NULL CHECK (length(event_type) > 0),
    actor TEXT NOT NULL CHECK (length(actor) > 0),
    payload TEXT NOT NULL DEFAULT '{}',
    extraction_method TEXT NOT NULL CHECK (
        extraction_method IN ('application_rule', 'model_assisted', 'manual')
    ),
    extractor_version TEXT,
    event_status TEXT NOT NULL CHECK (
        event_status IN ('candidate', 'accepted', 'rejected', 'requires_review')
    ),
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) > 0),
    created_at TEXT NOT NULL,
    validated_at TEXT,

    UNIQUE (run_id, sequence_number),
    UNIQUE (run_id, idempotency_key),
    UNIQUE (event_id, run_id),

    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),

    FOREIGN KEY (session_id, run_id)
        REFERENCES sessions(session_id, run_id)
);

CREATE TABLE event_evidence (
    event_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL CHECK (length(evidence_type) > 0),
    start_offset INTEGER,
    end_offset INTEGER,
    annotation TEXT,

    PRIMARY KEY (event_id, message_id, evidence_type),

    FOREIGN KEY (event_id)
        REFERENCES events(event_id),

    FOREIGN KEY (message_id)
        REFERENCES messages(message_id),

    CHECK (
        (start_offset IS NULL AND end_offset IS NULL)
        OR
        (
            start_offset IS NOT NULL
            AND end_offset IS NOT NULL
            AND start_offset >= 0
            AND end_offset >= start_offset
        )
    )
);

CREATE TABLE state_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT,
    previous_snapshot_id TEXT,
    state_schema_version TEXT NOT NULL,
    snapshot_reason TEXT NOT NULL CHECK (length(snapshot_reason) > 0),
    created_at TEXT NOT NULL,

    UNIQUE (snapshot_id, run_id),

    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),

    FOREIGN KEY (session_id, run_id)
        REFERENCES sessions(session_id, run_id),

    FOREIGN KEY (previous_snapshot_id, run_id)
        REFERENCES state_snapshots(snapshot_id, run_id)
);

CREATE TABLE state_snapshot_values (
    snapshot_id TEXT NOT NULL,
    variable_name TEXT NOT NULL CHECK (
        variable_name IN (
            'therapeutic_alliance',
            'disclosure_readiness',
            'experiential_avoidance',
            'willingness',
            'values_clarity',
            'committed_action_readiness'
        )
    ),
    variable_value INTEGER NOT NULL CHECK (
        variable_value BETWEEN 0 AND 4
    ),

    PRIMARY KEY (snapshot_id, variable_name),

    FOREIGN KEY (snapshot_id)
        REFERENCES state_snapshots(snapshot_id)
);

CREATE TABLE state_transitions (
    transition_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_id TEXT,
    variable_name TEXT NOT NULL CHECK (
        variable_name IN (
            'therapeutic_alliance',
            'disclosure_readiness',
            'experiential_avoidance',
            'willingness',
            'values_clarity',
            'committed_action_readiness'
        )
    ),
    previous_value INTEGER NOT NULL CHECK (previous_value BETWEEN 0 AND 4),
    proposed_value INTEGER NOT NULL CHECK (proposed_value BETWEEN 0 AND 4),
    accepted_value INTEGER CHECK (
        accepted_value IS NULL OR accepted_value BETWEEN 0 AND 4
    ),
    validation_status TEXT NOT NULL CHECK (
        validation_status IN ('pending', 'accepted', 'rejected', 'requires_review')
    ),
    transition_rule_id TEXT,
    transition_rule_version TEXT,
    resulting_snapshot_id TEXT,
    confidence TEXT,
    uncertainty_notes TEXT,
    idempotency_key TEXT NOT NULL CHECK (length(idempotency_key) > 0),
    created_at TEXT NOT NULL,
    validated_at TEXT,

    UNIQUE (run_id, idempotency_key),

    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),

    FOREIGN KEY (session_id, run_id)
        REFERENCES sessions(session_id, run_id),

    FOREIGN KEY (event_id, run_id)
        REFERENCES events(event_id, run_id),

    FOREIGN KEY (resulting_snapshot_id, run_id)
        REFERENCES state_snapshots(snapshot_id, run_id),

    CHECK (
        (
            validation_status = 'accepted'
            AND accepted_value IS NOT NULL
        )
        OR
        (
            validation_status <> 'accepted'
            AND accepted_value IS NULL
        )
    )
);

CREATE TABLE transition_evidence (
    transition_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL CHECK (length(evidence_role) > 0),
    relevance_note TEXT,

    PRIMARY KEY (transition_id, message_id),

    FOREIGN KEY (transition_id)
        REFERENCES state_transitions(transition_id),

    FOREIGN KEY (message_id)
        REFERENCES messages(message_id)
);

CREATE TABLE memory_items (
    memory_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_session_id TEXT,
    memory_type TEXT NOT NULL CHECK (length(memory_type) > 0),
    information_class TEXT NOT NULL CHECK (
        information_class IN (
            'confirmed_fact',
            'explicit_disclosure',
            'therapist_hypothesis',
            'system_generated_summary',
            'reported_outcome',
            'structured_observation'
        )
    ),
    content TEXT NOT NULL,
    confidence REAL CHECK (
        confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0
    ),
    status TEXT NOT NULL CHECK (
        status IN ('active', 'superseded', 'requires_review')
    ),
    memory_version INTEGER NOT NULL CHECK (memory_version >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),

    FOREIGN KEY (source_session_id, run_id)
        REFERENCES sessions(session_id, run_id)
);

CREATE TABLE memory_evidence (
    memory_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL CHECK (length(relationship_type) > 0),

    PRIMARY KEY (memory_id, message_id),

    FOREIGN KEY (memory_id)
        REFERENCES memory_items(memory_id),

    FOREIGN KEY (message_id)
        REFERENCES messages(message_id)
);

CREATE TABLE rubric_versions (
    rubric_version_id TEXT PRIMARY KEY,
    rubric_id TEXT NOT NULL,
    version_number TEXT NOT NULL,
    modality TEXT NOT NULL,
    language TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    rubric_definition TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT,
    created_at TEXT NOT NULL,

    UNIQUE (rubric_id, version_number)
);

CREATE TABLE evaluations (
    evaluation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT,
    evaluation_scope TEXT NOT NULL CHECK (
        evaluation_scope IN ('session', 'longitudinal')
    ),
    rubric_version_id TEXT NOT NULL,
    transcript_manifest TEXT NOT NULL DEFAULT '[]',
    evaluator_model_run_id TEXT,
    overall_summary TEXT,
    report_metadata TEXT,
    evaluation_revision INTEGER NOT NULL CHECK (evaluation_revision >= 1),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'completed', 'failed', 'requires_review')
    ),
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),

    FOREIGN KEY (session_id, run_id)
        REFERENCES sessions(session_id, run_id),

    FOREIGN KEY (rubric_version_id)
        REFERENCES rubric_versions(rubric_version_id),

    FOREIGN KEY (evaluator_model_run_id)
        REFERENCES model_runs(model_run_id),

    CHECK (
        (
            evaluation_scope = 'session'
            AND session_id IS NOT NULL
        )
        OR
        (
            evaluation_scope = 'longitudinal'
            AND session_id IS NULL
        )
    )
);

CREATE TABLE evaluation_items (
    evaluation_item_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL,
    competency_id TEXT NOT NULL CHECK (length(competency_id) > 0),
    rating_code TEXT NOT NULL CHECK (
        rating_code IN ('0', '1', '2', '3', 'NE')
    ),
    justification TEXT,
    alternative_response TEXT,
    limitations TEXT,
    uncertainty_notes TEXT,

    UNIQUE (evaluation_id, competency_id),

    FOREIGN KEY (evaluation_id)
        REFERENCES evaluations(evaluation_id)
);

CREATE TABLE evaluation_evidence (
    evaluation_item_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL CHECK (length(evidence_role) > 0),
    start_offset INTEGER,
    end_offset INTEGER,
    evidence_excerpt TEXT,
    evidence_note TEXT,

    PRIMARY KEY (evaluation_item_id, message_id, evidence_role),

    FOREIGN KEY (evaluation_item_id)
        REFERENCES evaluation_items(evaluation_item_id),

    FOREIGN KEY (message_id)
        REFERENCES messages(message_id),

    CHECK (
        (start_offset IS NULL AND end_offset IS NULL)
        OR
        (
            start_offset IS NOT NULL
            AND end_offset IS NOT NULL
            AND start_offset >= 0
            AND end_offset >= start_offset
        )
    )
);

CREATE INDEX idx_disclosures_run_case_fact
    ON case_fact_disclosures(run_id, case_fact_id);

CREATE INDEX idx_disclosure_history_disclosure
    ON case_fact_disclosure_history(disclosure_id);

CREATE INDEX idx_disclosure_history_source_message
    ON case_fact_disclosure_history(source_message_id);

CREATE INDEX idx_events_run
    ON events(run_id);

CREATE INDEX idx_events_session
    ON events(session_id);

CREATE INDEX idx_events_type
    ON events(event_type);

CREATE INDEX idx_event_evidence_message
    ON event_evidence(message_id);

CREATE INDEX idx_state_snapshots_run
    ON state_snapshots(run_id);

CREATE INDEX idx_state_transitions_run
    ON state_transitions(run_id);

CREATE INDEX idx_state_transitions_session
    ON state_transitions(session_id);

CREATE INDEX idx_transition_evidence_message
    ON transition_evidence(message_id);

CREATE INDEX idx_memory_items_run
    ON memory_items(run_id);

CREATE INDEX idx_memory_evidence_message
    ON memory_evidence(message_id);

CREATE INDEX idx_rubric_versions_rubric
    ON rubric_versions(rubric_id);

CREATE INDEX idx_evaluations_run
    ON evaluations(run_id);

CREATE INDEX idx_evaluations_session
    ON evaluations(session_id);

CREATE INDEX idx_evaluation_evidence_message
    ON evaluation_evidence(message_id);
