CREATE TABLE event_reviews (
    review_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    run_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('accepted', 'rejected')),
    reviewer_id TEXT NOT NULL CHECK (length(reviewer_id) > 0),
    rationale TEXT NOT NULL CHECK (length(rationale) > 0),
    reviewed_at TEXT NOT NULL,

    FOREIGN KEY (event_id, run_id)
        REFERENCES events(event_id, run_id)
);

CREATE INDEX idx_event_reviews_run_time
    ON event_reviews(run_id, reviewed_at);

CREATE TRIGGER event_reviews_no_update
BEFORE UPDATE ON event_reviews
BEGIN
    SELECT RAISE(ABORT, 'event_review_immutable');
END;

CREATE TRIGGER event_reviews_no_delete
BEFORE DELETE ON event_reviews
BEGIN
    SELECT RAISE(ABORT, 'event_review_immutable');
END;

CREATE TRIGGER event_status_review_required
BEFORE UPDATE OF event_status ON events
WHEN NEW.event_status <> OLD.event_status
 AND NOT EXISTS (
    SELECT 1
    FROM event_reviews
    WHERE event_id = NEW.event_id
      AND run_id = NEW.run_id
      AND decision = NEW.event_status
 )
BEGIN
    SELECT RAISE(ABORT, 'event_status_requires_review_record');
END;
