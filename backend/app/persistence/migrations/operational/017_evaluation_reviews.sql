CREATE TABLE evaluation_reviews (
    review_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL,
    review_number INTEGER NOT NULL CHECK (review_number >= 1),
    reviewer_user_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (
        decision IN ('accepted', 'revision_requested')
    ),
    feedback TEXT NOT NULL CHECK (
        length(trim(feedback)) BETWEEN 1 AND 4000
    ),
    created_at TEXT NOT NULL,

    UNIQUE (evaluation_id, review_number),

    FOREIGN KEY (evaluation_id)
        REFERENCES evaluations(evaluation_id),

    FOREIGN KEY (reviewer_user_id)
        REFERENCES local_auth_users(user_id)
);

CREATE INDEX idx_evaluation_reviews_evaluation
    ON evaluation_reviews(evaluation_id, review_number);

CREATE TRIGGER evaluation_reviews_no_update
BEFORE UPDATE ON evaluation_reviews
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'evaluation_reviews_are_immutable');
END;

CREATE TRIGGER evaluation_reviews_no_delete
BEFORE DELETE ON evaluation_reviews
FOR EACH ROW
BEGIN
    SELECT RAISE(ABORT, 'evaluation_reviews_are_immutable');
END;
