-- therasim: requires_foreign_keys_off
CREATE TABLE model_runs_rebuilt (
    model_run_id TEXT PRIMARY KEY,
    run_id TEXT,
    session_id TEXT,
    component TEXT NOT NULL CHECK (
        component IN (
            'patient_agent',
            'evaluator_agent',
            'memory_extraction_agent'
        )
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

INSERT INTO model_runs_rebuilt (
    model_run_id, run_id, session_id, component, provider,
    model_identifier, model_version, model_artifact_digest, prompt_id,
    prompt_version, input_schema_version, output_schema_version,
    generation_parameters, input_hash, output_hash, random_seed,
    execution_status, output_validation_status, started_at, completed_at
)
SELECT
    model_run_id, run_id, session_id, component, provider,
    model_identifier, model_version, model_artifact_digest, prompt_id,
    prompt_version, input_schema_version, output_schema_version,
    generation_parameters, input_hash, output_hash, random_seed,
    execution_status, output_validation_status, started_at, completed_at
FROM model_runs;

DROP TABLE model_runs;
ALTER TABLE model_runs_rebuilt RENAME TO model_runs;

CREATE INDEX idx_model_runs_session
    ON model_runs(session_id);

ALTER TABLE memory_extraction_jobs
ADD COLUMN model_run_id TEXT
REFERENCES model_runs(model_run_id);

CREATE INDEX idx_memory_extraction_jobs_model_run
    ON memory_extraction_jobs(model_run_id);
