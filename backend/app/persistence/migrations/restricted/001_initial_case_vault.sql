CREATE TABLE restricted_case_profiles (
    restricted_profile_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    case_version_id TEXT NOT NULL UNIQUE,
    clinical_formulation TEXT NOT NULL DEFAULT '{}',
    relevant_personal_history TEXT NOT NULL DEFAULT '{}',
    maintaining_factors TEXT NOT NULL DEFAULT '[]',
    avoidance_patterns TEXT NOT NULL DEFAULT '[]',
    hypothesized_functions TEXT NOT NULL DEFAULT '{}',
    initial_safety_baseline TEXT NOT NULL DEFAULT '{}',
    patient_simulation_instructions TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, case_version_id)
);

CREATE TABLE case_facts (
    case_id TEXT NOT NULL,
    case_version_id TEXT NOT NULL,
    case_fact_id TEXT NOT NULL,
    fact_category TEXT NOT NULL,
    information_class TEXT NOT NULL CHECK (
        information_class IN (
            'established_fact',
            'case_hypothesis',
            'unspecified_information'
        )
    ),
    content TEXT NOT NULL,
    disclosure_policy TEXT NOT NULL CHECK (
        disclosure_policy IN (
            'initial_disclosure',
            'contextually_disclosable',
            'restricted',
            'not_applicable'
        )
    ),
    relevance_metadata TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (case_id, case_version_id, case_fact_id),
    FOREIGN KEY (case_id, case_version_id)
        REFERENCES restricted_case_profiles(case_id, case_version_id)
);

CREATE INDEX idx_case_facts_version
    ON case_facts(case_id, case_version_id);
