CREATE TABLE memory_consolidation_sources (
    consolidated_memory_id TEXT NOT NULL,
    source_memory_id TEXT NOT NULL,
    source_memory_version INTEGER NOT NULL CHECK (source_memory_version >= 1),
    source_session_id TEXT NOT NULL,
    source_content TEXT NOT NULL CHECK (length(source_content) > 0),
    relationship_type TEXT NOT NULL CHECK (
        relationship_type IN (
            'related',
            'repeated',
            'potential_contradiction'
        )
    ),
    created_at TEXT NOT NULL,
    PRIMARY KEY (consolidated_memory_id, source_memory_id),
    CHECK (consolidated_memory_id <> source_memory_id),
    FOREIGN KEY (consolidated_memory_id)
        REFERENCES memory_items(memory_id),
    FOREIGN KEY (source_memory_id)
        REFERENCES memory_items(memory_id)
);

CREATE INDEX idx_memory_consolidation_sources_source
    ON memory_consolidation_sources(source_memory_id);

CREATE TRIGGER memory_consolidation_sources_no_update
BEFORE UPDATE ON memory_consolidation_sources
BEGIN
    SELECT RAISE(ABORT, 'memory_consolidation_sources_are_immutable');
END;

CREATE TRIGGER memory_consolidation_sources_no_delete
BEFORE DELETE ON memory_consolidation_sources
BEGIN
    SELECT RAISE(ABORT, 'memory_consolidation_sources_are_immutable');
END;
