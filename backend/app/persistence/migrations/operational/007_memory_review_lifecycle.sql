-- therasim: requires_foreign_keys_off
CREATE TABLE memory_items_rebuilt (
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
        status IN ('active', 'superseded', 'requires_review', 'rejected')
    ),
    memory_version INTEGER NOT NULL CHECK (memory_version >= 1),
    memory_scope TEXT NOT NULL DEFAULT 'legacy_unclassified'
        CHECK (
            memory_scope IN (
                'legacy_unclassified',
                'episodic',
                'semantic',
                'therapeutic'
            )
        ),
    supersedes_memory_id TEXT,
    origin_interaction_request_id TEXT,
    proposal_index INTEGER CHECK (
        proposal_index IS NULL OR proposal_index >= 0
    ),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id),
    FOREIGN KEY (source_session_id, run_id)
        REFERENCES sessions(session_id, run_id),
    FOREIGN KEY (supersedes_memory_id)
        REFERENCES memory_items(memory_id),
    FOREIGN KEY (origin_interaction_request_id)
        REFERENCES interaction_requests(request_id)
);

INSERT INTO memory_items_rebuilt (
    memory_id, run_id, source_session_id, memory_type, information_class,
    content, confidence, status, memory_version, memory_scope,
    supersedes_memory_id, origin_interaction_request_id, proposal_index,
    created_at, updated_at
)
SELECT
    memory_id, run_id, source_session_id, memory_type, information_class,
    content, confidence, status, memory_version, memory_scope,
    NULL, NULL, NULL, created_at, updated_at
FROM memory_items;

DROP TABLE memory_items;
ALTER TABLE memory_items_rebuilt RENAME TO memory_items;

CREATE INDEX idx_memory_items_run
    ON memory_items(run_id);

CREATE INDEX idx_memory_items_run_scope
    ON memory_items(run_id, memory_scope, status);

CREATE INDEX idx_memory_items_supersedes
    ON memory_items(supersedes_memory_id);

CREATE UNIQUE INDEX idx_memory_items_origin_proposal
    ON memory_items(origin_interaction_request_id, proposal_index)
    WHERE origin_interaction_request_id IS NOT NULL
      AND proposal_index IS NOT NULL;

ALTER TABLE memory_evidence
ADD COLUMN start_offset INTEGER CHECK (
    start_offset IS NULL OR start_offset >= 0
);

ALTER TABLE memory_evidence
ADD COLUMN end_offset INTEGER CHECK (
    end_offset IS NULL OR end_offset >= 0
);

CREATE TABLE memory_reviews (
    review_id TEXT PRIMARY KEY,
    memory_id TEXT NOT NULL UNIQUE,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reviewer_id TEXT NOT NULL CHECK (length(reviewer_id) > 0),
    rationale TEXT NOT NULL CHECK (length(rationale) > 0),
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (memory_id)
        REFERENCES memory_items(memory_id)
);

CREATE TRIGGER memory_reviews_no_update
BEFORE UPDATE ON memory_reviews
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'memory_reviews_are_immutable');
END;

CREATE TRIGGER memory_reviews_no_delete
BEFORE DELETE ON memory_reviews
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'memory_reviews_are_immutable');
END;
