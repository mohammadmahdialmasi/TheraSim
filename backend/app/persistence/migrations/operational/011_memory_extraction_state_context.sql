ALTER TABLE memory_extraction_jobs
ADD COLUMN character_state_snapshot_id TEXT
REFERENCES character_state_snapshots(snapshot_id);

CREATE INDEX idx_memory_extraction_jobs_character_state
    ON memory_extraction_jobs(character_state_snapshot_id);
