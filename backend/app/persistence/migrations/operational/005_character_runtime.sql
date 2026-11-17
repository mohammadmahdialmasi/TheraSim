CREATE TABLE run_character_profiles (
    snapshot_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    case_id TEXT NOT NULL,
    case_version_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    personality_profile_id TEXT,
    profile_version INTEGER,
    personality_schema_version TEXT NOT NULL,
    theory_bundle_version TEXT,
    source_content_hash TEXT,
    profile_status TEXT NOT NULL CHECK (
        profile_status IN ('unconfigured', 'active')
    ),
    captured_at TEXT NOT NULL,

    UNIQUE (snapshot_id, run_id),

    FOREIGN KEY (run_id, case_id, case_version_id)
        REFERENCES simulation_runs(run_id, case_id, case_version_id),

    CHECK (
        (
            profile_status = 'unconfigured'
            AND personality_profile_id IS NULL
            AND profile_version IS NULL
            AND theory_bundle_version IS NULL
            AND source_content_hash IS NULL
        )
        OR
        (
            profile_status = 'active'
            AND personality_profile_id IS NOT NULL
            AND profile_version IS NOT NULL
            AND profile_version >= 1
            AND theory_bundle_version IS NOT NULL
            AND source_content_hash IS NOT NULL
        )
    )
);

CREATE INDEX idx_run_character_profiles_case
    ON run_character_profiles(case_id, case_version_id);

CREATE TRIGGER run_character_profiles_no_update
BEFORE UPDATE ON run_character_profiles
BEGIN
    SELECT RAISE(ABORT, 'run_character_profile_snapshot_immutable');
END;

CREATE TRIGGER run_character_profiles_no_delete
BEFORE DELETE ON run_character_profiles
BEGIN
    SELECT RAISE(ABORT, 'run_character_profile_snapshot_immutable');
END;

CREATE TABLE character_state_snapshots (
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
        REFERENCES character_state_snapshots(snapshot_id, run_id)
);

CREATE TABLE character_state_snapshot_values (
    snapshot_id TEXT NOT NULL,
    variable_name TEXT NOT NULL CHECK (
        variable_name IN (
            'affect_valence',
            'arousal',
            'perceived_safety',
            'social_evaluative_threat',
            'engagement',
            'interpersonal_withdrawal'
        )
    ),
    variable_value INTEGER NOT NULL,

    PRIMARY KEY (snapshot_id, variable_name),

    FOREIGN KEY (snapshot_id)
        REFERENCES character_state_snapshots(snapshot_id),

    CHECK (
        (variable_name = 'affect_valence'
            AND variable_value BETWEEN -2 AND 2)
        OR
        (variable_name <> 'affect_valence'
            AND variable_value BETWEEN 0 AND 4)
    )
);

CREATE TRIGGER character_state_snapshots_no_update
BEFORE UPDATE ON character_state_snapshots
BEGIN
    SELECT RAISE(ABORT, 'character_state_snapshot_immutable');
END;

CREATE TRIGGER character_state_snapshots_no_delete
BEFORE DELETE ON character_state_snapshots
BEGIN
    SELECT RAISE(ABORT, 'character_state_snapshot_immutable');
END;

CREATE TRIGGER character_state_snapshot_values_no_update
BEFORE UPDATE ON character_state_snapshot_values
BEGIN
    SELECT RAISE(ABORT, 'character_state_snapshot_values_immutable');
END;

CREATE TRIGGER character_state_snapshot_values_no_delete
BEFORE DELETE ON character_state_snapshot_values
BEGIN
    SELECT RAISE(ABORT, 'character_state_snapshot_values_immutable');
END;

CREATE TABLE character_state_transitions (
    transition_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_id TEXT,
    variable_name TEXT NOT NULL CHECK (
        variable_name IN (
            'affect_valence',
            'arousal',
            'perceived_safety',
            'social_evaluative_threat',
            'engagement',
            'interpersonal_withdrawal'
        )
    ),
    previous_value INTEGER NOT NULL,
    proposed_value INTEGER NOT NULL,
    accepted_value INTEGER,
    validation_status TEXT NOT NULL CHECK (
        validation_status IN (
            'pending',
            'accepted',
            'rejected',
            'requires_review'
        )
    ),
    confidence REAL CHECK (
        confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0
    ),
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

    CHECK (
        (
            variable_name = 'affect_valence'
            AND previous_value BETWEEN -2 AND 2
            AND proposed_value BETWEEN -2 AND 2
            AND (accepted_value IS NULL OR accepted_value BETWEEN -2 AND 2)
        )
        OR
        (
            variable_name <> 'affect_valence'
            AND previous_value BETWEEN 0 AND 4
            AND proposed_value BETWEEN 0 AND 4
            AND (accepted_value IS NULL OR accepted_value BETWEEN 0 AND 4)
        )
    ),

    CHECK (
        (validation_status = 'accepted' AND accepted_value IS NOT NULL)
        OR
        (validation_status <> 'accepted' AND accepted_value IS NULL)
    )
);

CREATE TABLE character_state_transition_evidence (
    transition_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    evidence_role TEXT NOT NULL CHECK (length(evidence_role) > 0),
    relevance_note TEXT,

    PRIMARY KEY (transition_id, message_id),

    FOREIGN KEY (transition_id)
        REFERENCES character_state_transitions(transition_id),

    FOREIGN KEY (message_id)
        REFERENCES messages(message_id)
);

CREATE INDEX idx_character_state_snapshots_run
    ON character_state_snapshots(run_id);

CREATE INDEX idx_character_state_transitions_run
    ON character_state_transitions(run_id);

CREATE INDEX idx_character_state_transitions_session
    ON character_state_transitions(session_id);

CREATE INDEX idx_character_state_transition_evidence_message
    ON character_state_transition_evidence(message_id);

ALTER TABLE memory_items
ADD COLUMN memory_scope TEXT NOT NULL DEFAULT 'legacy_unclassified'
CHECK (
    memory_scope IN (
        'legacy_unclassified',
        'episodic',
        'semantic',
        'therapeutic'
    )
);

CREATE INDEX idx_memory_items_run_scope
    ON memory_items(run_id, memory_scope, status);
