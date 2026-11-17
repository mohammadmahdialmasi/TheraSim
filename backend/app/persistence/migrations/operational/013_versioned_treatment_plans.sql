CREATE TABLE treatment_plan_revisions (
    revision_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL CHECK (revision_number >= 1),
    based_on_revision_number INTEGER CHECK (
        based_on_revision_number IS NULL OR based_on_revision_number >= 1
    ),
    modality TEXT NOT NULL CHECK (length(modality) > 0),
    protocol_id TEXT NOT NULL CHECK (length(protocol_id) > 0),
    protocol_version TEXT NOT NULL CHECK (length(protocol_version) > 0),
    plan_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('active', 'requires_review', 'superseded', 'rejected')
    ),
    created_at TEXT NOT NULL,

    UNIQUE (run_id, revision_number),
    UNIQUE (plan_id, revision_number),
    UNIQUE (revision_id, run_id),
    FOREIGN KEY (run_id)
        REFERENCES simulation_runs(run_id)
);

CREATE UNIQUE INDEX idx_treatment_plan_one_active_per_run
    ON treatment_plan_revisions(run_id)
    WHERE status = 'active';

CREATE UNIQUE INDEX idx_treatment_plan_one_pending_per_run
    ON treatment_plan_revisions(run_id)
    WHERE status = 'requires_review';

CREATE TABLE treatment_plan_reviews (
    review_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reviewer_id TEXT NOT NULL CHECK (length(reviewer_id) > 0),
    rationale TEXT NOT NULL CHECK (length(rationale) > 0),
    reviewed_at TEXT NOT NULL,
    FOREIGN KEY (revision_id, run_id)
        REFERENCES treatment_plan_revisions(revision_id, run_id)
);

CREATE TRIGGER treatment_plan_revision_content_immutable
BEFORE UPDATE OF
    revision_id, plan_id, run_id, revision_number, modality, protocol_id,
    protocol_version, plan_json, created_at
ON treatment_plan_revisions
BEGIN
    SELECT RAISE(ABORT, 'treatment_plan_revision_immutable');
END;

CREATE TRIGGER treatment_plan_revision_no_delete
BEFORE DELETE ON treatment_plan_revisions
BEGIN
    SELECT RAISE(ABORT, 'treatment_plan_revision_immutable');
END;

CREATE TRIGGER treatment_plan_revision_status_requires_review
BEFORE UPDATE OF status ON treatment_plan_revisions
WHEN NEW.status <> OLD.status
 AND (
    (
        NEW.status IN ('active', 'rejected')
        AND NOT EXISTS (
            SELECT 1
            FROM treatment_plan_reviews
            WHERE revision_id = NEW.revision_id
              AND run_id = NEW.run_id
              AND decision = CASE NEW.status
                  WHEN 'active' THEN 'accepted'
                  WHEN 'rejected' THEN 'rejected'
              END
        )
    )
    OR
    (
        NEW.status = 'superseded'
        AND NOT EXISTS (
            SELECT 1
            FROM treatment_plan_revisions AS next_revision
            JOIN treatment_plan_reviews AS review
              ON review.revision_id = next_revision.revision_id
             AND review.run_id = next_revision.run_id
            WHERE next_revision.run_id = NEW.run_id
              AND next_revision.plan_id = NEW.plan_id
              AND next_revision.based_on_revision_number = NEW.revision_number
              AND review.decision = 'accepted'
        )
    )
 )
BEGIN
    SELECT RAISE(ABORT, 'treatment_plan_status_requires_review');
END;

CREATE TRIGGER treatment_plan_reviews_no_update
BEFORE UPDATE ON treatment_plan_reviews
BEGIN
    SELECT RAISE(ABORT, 'treatment_plan_review_immutable');
END;

CREATE TRIGGER treatment_plan_reviews_no_delete
BEFORE DELETE ON treatment_plan_reviews
BEGIN
    SELECT RAISE(ABORT, 'treatment_plan_review_immutable');
END;
