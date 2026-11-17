CREATE TABLE character_personality_profiles (
    personality_profile_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL CHECK (length(character_id) > 0),
    case_id TEXT NOT NULL,
    case_version_id TEXT NOT NULL,
    profile_version INTEGER NOT NULL CHECK (profile_version >= 1),
    personality_schema_version TEXT NOT NULL,
    theory_bundle_version TEXT NOT NULL,
    authoring_status TEXT NOT NULL CHECK (
        authoring_status IN ('draft', 'reviewed', 'active', 'retired')
    ),
    profile_json TEXT NOT NULL CHECK (length(profile_json) > 1),
    content_hash TEXT NOT NULL CHECK (length(content_hash) = 64),
    created_at TEXT NOT NULL,

    UNIQUE (case_id, case_version_id, profile_version),
    UNIQUE (personality_profile_id, case_id, case_version_id),

    FOREIGN KEY (case_id, case_version_id)
        REFERENCES restricted_case_profiles(case_id, case_version_id)
);

CREATE UNIQUE INDEX ux_character_personality_active
    ON character_personality_profiles(case_id, case_version_id)
    WHERE authoring_status = 'active';

CREATE INDEX idx_character_personality_character
    ON character_personality_profiles(character_id, profile_version);

CREATE TRIGGER character_personality_profile_content_immutable
BEFORE UPDATE OF
    personality_profile_id,
    character_id,
    case_id,
    case_version_id,
    profile_version,
    personality_schema_version,
    theory_bundle_version,
    profile_json,
    content_hash,
    created_at
ON character_personality_profiles
BEGIN
    SELECT RAISE(ABORT, 'character_personality_profile_content_immutable');
END;

CREATE TRIGGER character_personality_profiles_no_delete
BEFORE DELETE ON character_personality_profiles
BEGIN
    SELECT RAISE(ABORT, 'character_personality_profile_immutable');
END;
