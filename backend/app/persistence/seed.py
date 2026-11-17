"""Seed the default AVA-001 case into a fresh TheraSim data directory."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import TYPE_CHECKING, Any

from app.persistence.repositories.cases import CaseRepository
from app.persistence.repositories.character_personality import (
    CharacterPersonalityRepository,
)
from app.persistence.repositories.restricted_cases import (
    RestrictedCaseRepository,
)

if TYPE_CHECKING:
    from app.persistence.database import DatabaseManager


CASE_ID = "case-ava-001"
CASE_CODE = "AVA-001"
CASE_VERSION_ID = "case-ava-001-v1"
CASE_VERSION_NUMBER = "1.0"
CASE_DISPLAY_NAME = "Ava (AVA-001)"
RESTRICTED_PROFILE_ID = "ava-001-restricted-profile-1"
PERSONALITY_PROFILE_ID = "ava-001-personality-profile-1"


class SeedConflictError(RuntimeError):
    """Raised when a conflicting case catalog or content hash is present."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _version_content_hash() -> str:
    payload = {
        "case_id": CASE_ID,
        "case_code": CASE_CODE,
        "case_version_id": CASE_VERSION_ID,
        "version_number": CASE_VERSION_NUMBER,
        "modality": "ACT",
        "language": "fa",
        "schema_version": "0.2",
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _public_profile_payload() -> dict[str, Any]:
    return {
        "age": 29,
        "occupation": "UX Designer",
        "presenting_concerns": [
            "difficulty expressing opinions in professional meetings",
            "excessive preparation before presenting",
            "avoiding speaking when evaluation feels likely",
        ],
        "initial_disclosure": (
            "Ava worries that making mistakes in professional settings will cause "
            "others to judge her competence, and she sometimes avoids speaking as a result."
        ),
        "profile_metadata": {
            "source": "scenarios/act/CASE_001.md",
            "case_version": "0.2",
            "language": "fa",
            "synthetic": True,
        },
    }


def _restricted_profile_payload() -> dict[str, Any]:
    return {
        "clinical_formulation": {
            "primary_theme": "fear of professional evaluation and perceived incompetence",
            "functional_summary": (
                "Ava experiences anticipatory anxiety in meetings and tends to avoid "
                "participation through preparation or silence."
            ),
            "risk_profile": "not_acutely_unsafe",
            "language": "fa",
        },
        "relevant_personal_history": {
            "employment": "UX Designer",
            "team_context": "product design team",
            "timeline": "Approximately eighteen months ago, a senior colleague publicly corrected several parts of her work during a presentation.",
        },
        "maintaining_factors": [
            "excessive preparation",
            "avoidance of spontaneous speaking",
            "repeated revision of slides before presenting",
        ],
        "avoidance_patterns": [
            "remaining silent in meetings",
            "delaying opportunities to speak",
            "seeking reassurance before presenting",
        ],
        "hypothesized_functions": {
            "avoidance": "temporary anxiety reduction with long-term participation costs",
            "preparation": "attempt to reduce uncertainty and perceived evaluation risk",
        },
        "initial_safety_baseline": {
            "suicide_risk": "not_reported",
            "self_harm_history": "not_reported",
            "current_crisis": "not_identified",
        },
        "patient_simulation_instructions": (
            "Simulate a thoughtful, polite, reflective client who does not automatically agree with the therapist. "
            "She is cautious about evaluation, can become silent when threatened, and may intellectualize emotion before directly naming it."
        ),
    }


def _case_facts() -> list[dict[str, Any]]:
    return [
        {
            "case_fact_id": "AVA-FACT-001",
            "fact_category": "presenting_concern",
            "information_class": "established_fact",
            "content": (
                "Ava worries about making mistakes during professional meetings and avoids expressing her opinions because she fears negative judgments about her competence."
            ),
            "disclosure_policy": "initial_disclosure",
            "relevance_metadata": {"disclosure_level": 1, "source": "scenarios/act/CASE_001.md"},
        },
        {
            "case_fact_id": "AVA-FACT-002",
            "fact_category": "functional_cycle",
            "information_class": "established_fact",
            "content": (
                "Ava prepares excessively, remains quiet in meetings, feels temporary relief after avoiding participation, and later regrets not contributing."
            ),
            "disclosure_policy": "contextually_disclosable",
            "relevance_metadata": {"disclosure_level": 2, "source": "scenarios/act/CASE_001.md"},
        },
        {
            "case_fact_id": "AVA-FACT-003",
            "fact_category": "professional_history",
            "information_class": "established_fact",
            "content": (
                "Approximately eighteen months ago, a senior colleague interrupted Ava during a presentation and publicly corrected several parts of her work. Ava experienced embarrassment and became increasingly cautious about presenting afterwards."
            ),
            "disclosure_policy": "contextually_disclosable",
            "relevance_metadata": {"disclosure_level": 3, "source": "scenarios/act/CASE_001.md"},
        },
        {
            "case_fact_id": "AVA-FACT-004",
            "fact_category": "deeper_conflict",
            "information_class": "established_fact",
            "content": (
                "Ava genuinely wants to contribute ideas and participate creatively, but believes she must first remove uncertainty and anxiety."
            ),
            "disclosure_policy": "contextually_disclosable",
            "relevance_metadata": {"disclosure_level": 4, "source": "scenarios/act/CASE_001.md"},
        },
    ]


def _personality_profile_payload() -> dict[str, Any]:
    return {
        "personality_profile_id": PERSONALITY_PROFILE_ID,
        "character_id": "AVA-001",
        "case_id": CASE_ID,
        "case_version_id": CASE_VERSION_ID,
        "personality_schema_version": "0.1",
        "theory_bundle_version": "ava-001-authoring-v1",
        "profile_version": 1,
        "authoring_status": "active",
        "big_five": {
            "openness": {
                "level": "high",
                "confidence": "moderate",
                "context_scope": "creative professional work",
                "rationale": "The scenario describes Ava as creative and reflective, with an interest in contribution and learning.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            "conscientiousness": {
                "level": "high",
                "confidence": "moderate",
                "context_scope": "work preparation and delivery",
                "rationale": "She prepares extensively and carefully, which suggests strong conscientiousness in task execution.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            "extraversion": {
                "level": "unknown",
                "confidence": "low",
                "context_scope": "meeting participation",
                "rationale": "Silence in meetings and cautious participation are context-specific behaviors, not definitive evidence of low extraversion.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            "agreeableness": {
                "level": "mid",
                "confidence": "moderate",
                "context_scope": "professional communication",
                "rationale": "The scenario describes a generally polite, thoughtful communication style.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            "neuroticism": {
                "level": "mid_high",
                "confidence": "moderate",
                "context_scope": "evaluation and performance situations",
                "rationale": "Ava reports anxiety, shame, and anticipatory worry when facing evaluation or perceived mistakes.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
        },
        "attachment": {
            "anxiety": {
                "level": "unknown",
                "confidence": "low",
                "context_scope": "general attachment style",
                "rationale": "The scenario does not provide sufficient evidence to infer attachment anxiety.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            "avoidance": {
                "level": "unknown",
                "confidence": "low",
                "context_scope": "general attachment style",
                "rationale": "The scenario does not provide sufficient evidence to infer attachment avoidance.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
        },
        "interpersonal": {
            "agency": {
                "level": "mid",
                "confidence": "moderate",
                "context_scope": "professional voice and participation",
                "rationale": "Ava wants to contribute but becomes hesitant when evaluation threats rise.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            "communion": {
                "level": "mid_high",
                "confidence": "moderate",
                "context_scope": "collaborative goals",
                "rationale": "She values collaboration, contribution, and learning within a team environment.",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
        },
        "schema_themes": [
            {
                "theme_id": "performance-evaluation-threat",
                "description": "Mistakes are interpreted as evidence of incompetence.",
                "belief_content": "If I make a mistake, others will assume I am not competent.",
                "status": "character_endorsed",
                "confidence": "moderate",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            {
                "theme_id": "certainty-before-contribution",
                "description": "She believes she must eliminate uncertainty before contributing meaningfully.",
                "belief_content": "I should be completely prepared before speaking, otherwise I risk embarrassment.",
                "status": "character_endorsed",
                "confidence": "moderate",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
        ],
        "emotion_regulation_patterns": [
            {
                "pattern_id": "excessive-preparation",
                "description": "Ava over-prepares as a means of managing evaluation fear.",
                "relevant_contexts": ["presentations", "professional meetings"],
                "short_term_function": "reduces uncertainty and perceived threat in the moment",
                "possible_long_term_costs": ["reduced participation", "missed opportunities"],
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            {
                "pattern_id": "meeting-silence",
                "description": "She may remain silent when threat is high.",
                "relevant_contexts": ["team meetings", "unexpected questions"],
                "short_term_function": "reduces immediate exposure to evaluation",
                "possible_long_term_costs": ["limited contribution", "lowered professional growth"],
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
        ],
        "value_hypotheses": [
            {
                "domain": "professional contribution",
                "personal_meaning": "Ava values contributing useful ideas and participating creatively with the team.",
                "status": "candidate",
                "confidence": "moderate",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
            {
                "domain": "learning and growth",
                "personal_meaning": "Ava values learning and professional growth, even when it requires discomfort.",
                "status": "candidate",
                "confidence": "moderate",
                "source_refs": ["scenarios/act/CASE_001.md"],
            },
        ],
        "initial_state": {
            "affect_valence": 0,
            "arousal": 2,
            "perceived_safety": 2,
            "social_evaluative_threat": 3,
            "engagement": 2,
            "interpersonal_withdrawal": 2,
        },
        "communication_style": [
            "thoughtful",
            "polite",
            "reflective",
            "cautious",
        ],
        "authoring_notes": [
            "This profile intentionally avoids assigning unsupported attachment dimensions or unverified core beliefs."
        ],
    }


def _assert_expected_case(case_row: sqlite3.Row | None) -> None:
    if case_row is None:
        raise SeedConflictError("The default AVA-001 case is missing from the operational database.")
    if case_row["case_id"] != CASE_ID:
        raise SeedConflictError("The default AVA-001 case identifier is inconsistent.")
    if case_row["case_code"] != CASE_CODE:
        raise SeedConflictError("The default AVA-001 case code is inconsistent.")
    if case_row["display_name"] != CASE_DISPLAY_NAME:
        raise SeedConflictError("The default AVA-001 display name has changed.")
    if case_row["status"] != "active":
        raise SeedConflictError("The default AVA-001 case must remain active.")


def _assert_expected_version(version_row: sqlite3.Row | None) -> None:
    if version_row is None:
        raise SeedConflictError("The default AVA-001 case version is missing.")
    if version_row["case_version_id"] != CASE_VERSION_ID:
        raise SeedConflictError("The default AVA-001 version identifier is inconsistent.")
    if version_row["version_number"] != CASE_VERSION_NUMBER:
        raise SeedConflictError("The default AVA-001 version number is inconsistent.")
    if version_row["modality"] != "ACT":
        raise SeedConflictError("The default AVA-001 modality is inconsistent.")
    if version_row["language"] != "fa":
        raise SeedConflictError("The default AVA-001 language is inconsistent.")
    if version_row["content_hash"] != _version_content_hash():
        raise SeedConflictError("The default AVA-001 case version hash does not match its expected content.")


def _assert_expected_public_profile(profile_row: sqlite3.Row | None) -> None:
    if profile_row is None:
        raise SeedConflictError("The default AVA-001 public profile is missing.")
    payload = json.loads(profile_row["profile_metadata"] or "{}") if profile_row["profile_metadata"] else {}
    if profile_row["age"] != 29:
        raise SeedConflictError("The default AVA-001 public profile age does not match the scenario.")
    if profile_row["occupation"] != "UX Designer":
        raise SeedConflictError("The default AVA-001 occupation is inconsistent.")
    if payload.get("source") != "scenarios/act/CASE_001.md":
        raise SeedConflictError("The default AVA-001 public profile metadata is inconsistent.")


def _assert_expected_restricted_profile(profile_row: sqlite3.Row | None) -> None:
    if profile_row is None:
        raise SeedConflictError("The default AVA-001 restricted profile is missing.")
    if profile_row["restricted_profile_id"] != RESTRICTED_PROFILE_ID:
        raise SeedConflictError("The default AVA-001 restricted profile identifier is inconsistent.")
    payload = json.loads(profile_row["clinical_formulation"])
    if payload.get("primary_theme") != "fear of professional evaluation and perceived incompetence":
        raise SeedConflictError("The default AVA-001 restricted profile has unexpected formulation content.")


def _assert_expected_personality_profile(profile_row: sqlite3.Row | None) -> None:
    if profile_row is None:
        raise SeedConflictError("The default AVA-001 personality profile is missing.")
    if profile_row["personality_profile_id"] != PERSONALITY_PROFILE_ID:
        raise SeedConflictError("The default AVA-001 personality profile identifier is inconsistent.")
    payload = json.loads(profile_row["profile_json"])
    if payload.get("character_id") != "AVA-001":
        raise SeedConflictError("The default AVA-001 personality profile character ID is inconsistent.")
    if payload.get("profile_version") != 1:
        raise SeedConflictError("The default AVA-001 personality profile version is inconsistent.")
    expected_hash = hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()
    if payload.get("authoring_status") != "active":
        raise SeedConflictError("The default AVA-001 personality profile must be active.")
    if profile_row["content_hash"] != expected_hash:
        raise SeedConflictError("The default AVA-001 personality profile hash does not match its canonical JSON.")


def _ensure_schema(database_manager: DatabaseManager) -> None:
    from app.persistence.migrations import apply_migrations

    with database_manager.connection("operational") as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='cases'"
        ).fetchone()

    with database_manager.connection("restricted") as connection:
        tables_restricted = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='restricted_case_profiles'"
        ).fetchone()

    if tables is None:
        apply_migrations(database_manager, "operational")
    if tables_restricted is None:
        apply_migrations(database_manager, "restricted")


def seed_default_case(database_manager: DatabaseManager, *, created_at: str | None = None) -> dict[str, str]:
    """Seed the canonical AVA-001 case if the data directory is still empty."""

    _ensure_schema(database_manager)
    effective_created_at = created_at or _utc_now()

    try:
        with database_manager.transaction("operational") as connection:
            repository = CaseRepository(connection)
            existing_case = repository.get_case_by_code(CASE_CODE)

            if existing_case is None:
                if repository.list_cases(limit=1, offset=0):
                    raise SeedConflictError(
                        "A case catalog already exists; the default AVA-001 seed cannot be applied."
                    )
                repository.create_case(
                    case_id=CASE_ID,
                    case_code=CASE_CODE,
                    display_name=CASE_DISPLAY_NAME,
                    status="active",
                    created_at=effective_created_at,
                    updated_at=effective_created_at,
                )
                repository.create_case_version(
                    case_version_id=CASE_VERSION_ID,
                    case_id=CASE_ID,
                    version_number=CASE_VERSION_NUMBER,
                    modality="ACT",
                    language="fa",
                    schema_version="0.2",
                    created_at=effective_created_at,
                    content_hash=_version_content_hash(),
                )
                repository.create_public_profile(
                    case_version_id=CASE_VERSION_ID,
                    created_at=effective_created_at,
                    **_public_profile_payload(),
                )
            else:
                _assert_expected_case(existing_case)
                existing_version = repository.get_case_version_for_case(CASE_ID, CASE_VERSION_ID)
                _assert_expected_version(existing_version)
                existing_profile = repository.get_public_profile(CASE_VERSION_ID)
                _assert_expected_public_profile(existing_profile)

        with database_manager.transaction("restricted") as connection:
            repository = RestrictedCaseRepository(connection)
            existing_profile = repository.get_profile(CASE_ID, CASE_VERSION_ID)
            if existing_profile is None:
                repository.create_profile(
                    restricted_profile_id=RESTRICTED_PROFILE_ID,
                    case_id=CASE_ID,
                    case_version_id=CASE_VERSION_ID,
                    created_at=effective_created_at,
                    **_restricted_profile_payload(),
                )
                for fact in _case_facts():
                    repository.create_fact(
                        case_id=CASE_ID,
                        case_version_id=CASE_VERSION_ID,
                        created_at=effective_created_at,
                        **fact,
                    )
            else:
                _assert_expected_restricted_profile(existing_profile)

        with database_manager.transaction("restricted") as connection:
            repository = CharacterPersonalityRepository(connection)
            active_profile = repository.get_active_profile(CASE_ID, CASE_VERSION_ID)
            if active_profile is None:
                profile_json = _canonical_json(_personality_profile_payload())
                profile_hash = hashlib.sha256(profile_json.encode("utf-8")).hexdigest()
                repository.create_profile(
                    personality_profile_id=PERSONALITY_PROFILE_ID,
                    character_id="AVA-001",
                    case_id=CASE_ID,
                    case_version_id=CASE_VERSION_ID,
                    profile_version=1,
                    personality_schema_version="0.1",
                    theory_bundle_version="ava-001-authoring-v1",
                    profile_json=profile_json,
                    content_hash=profile_hash,
                    created_at=effective_created_at,
                )
                repository.set_authoring_status(PERSONALITY_PROFILE_ID, "reviewed")
                repository.set_authoring_status(PERSONALITY_PROFILE_ID, "active")
            else:
                _assert_expected_personality_profile(active_profile)

    except sqlite3.IntegrityError as exc:
        raise SeedConflictError(
            "The default AVA-001 seed conflicts with an existing record identity."
        ) from exc

    return {
        "case_id": CASE_ID,
        "case_code": CASE_CODE,
        "case_version_id": CASE_VERSION_ID,
    }
