"""Explicit serialization boundary for Patient Agent context."""

from app.services.patient_context import (
    FrozenJSONValue,
    PatientContext,
    PatientTranscriptMessage,
    thaw_json,
)


def _serialize_json_value(value: FrozenJSONValue) -> object:
    """Create a fresh mutable JSON-compatible representation."""

    return thaw_json(value)


def _serialize_transcript_message(
    message: PatientTranscriptMessage,
) -> dict[str, object]:
    """Serialize only the explicitly authorized transcript fields."""

    return {
        "message_id": message.message_id,
        "session_id": message.session_id,
        "session_number": message.session_number,
        "sequence_number": message.sequence_number,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
    }


def patient_context_to_payload(
    context: PatientContext,
) -> dict[str, object]:
    """Convert an authorized PatientContext into an explicit JSON payload.

    This function deliberately avoids dataclasses.asdict() and generic
    object serialization. Only fields declared here can cross the
    Patient Agent serialization boundary.
    """

    if not isinstance(context, PatientContext):
        raise TypeError("context must be a PatientContext instance.")

    identity = context.public_identity
    profile = context.restricted_profile
    state = context.current_state

    payload = {
        "context_schema_version": context.context_schema_version,
        "case_id": context.case_id,
        "case_version_id": context.case_version_id,
        "run_id": context.run_id,
        "session_id": context.session_id,
        "session_number": context.session_number,
        "language": context.language,
        "modality": context.modality,

        "public_identity": {
            "display_name": identity.display_name,
            "age": identity.age,
            "occupation": identity.occupation,
            "presenting_concerns": list(identity.presenting_concerns),
            "initial_disclosure": identity.initial_disclosure,
        },

        "restricted_profile": {
            "clinical_formulation": _serialize_json_value(
                profile.clinical_formulation
            ),
            "relevant_personal_history": _serialize_json_value(
                profile.relevant_personal_history
            ),
            "maintaining_factors": [
                _serialize_json_value(item)
                for item in profile.maintaining_factors
            ],
            "avoidance_patterns": [
                _serialize_json_value(item)
                for item in profile.avoidance_patterns
            ],
            "hypothesized_functions": _serialize_json_value(
                profile.hypothesized_functions
            ),
            "initial_safety_baseline": _serialize_json_value(
                profile.initial_safety_baseline
            ),
            "patient_simulation_instructions": (
                profile.patient_simulation_instructions
            ),
        },

        "relevant_case_facts": [
            {
                "case_fact_id": fact.case_fact_id,
                "fact_category": fact.fact_category,
                "information_class": fact.information_class,
                "content": fact.content,
                "disclosure_policy": fact.disclosure_policy,
                "disclosure_status": fact.disclosure_status,
                "relevance_metadata": (
                    _serialize_json_value(fact.relevance_metadata)
                    if fact.relevance_metadata is not None
                    else None
                ),
            }
            for fact in context.relevant_case_facts
        ],

        "current_state": {
            "snapshot_id": state.snapshot_id,
            "state_schema_version": state.state_schema_version,
            "values": [
                {
                    "name": variable.name,
                    "value": variable.value,
                }
                for variable in state.values
            ],
        },

        "longitudinal_memory": [
            {
                "memory_id": memory.memory_id,
                "source_session_id": memory.source_session_id,
                "memory_type": memory.memory_type,
                "information_class": memory.information_class,
                "content": memory.content,
                "source_message_ids": list(memory.source_message_ids),
                "confidence": memory.confidence,
                "memory_version": memory.memory_version,
                **(
                    {"memory_scope": memory.memory_scope}
                    if memory.memory_scope != "legacy_unclassified"
                    else {}
                ),
            }
            for memory in context.longitudinal_memory
        ],

        "recent_transcript": [
            _serialize_transcript_message(message)
            for message in context.recent_transcript
        ],

        "therapist_message": _serialize_transcript_message(
            context.therapist_message
        ),
    }

    if context.character_personality is not None:
        payload["character_personality"] = {
            "configured": context.character_personality.configured,
            "profile_data": _serialize_json_value(
                context.character_personality.profile_data
            ),
        }

    if context.character_state is not None:
        payload["character_state"] = {
            "snapshot_id": context.character_state.snapshot_id,
            "state_schema_version": (
                context.character_state.state_schema_version
            ),
            "values": [
                {"name": item.name, "value": item.value}
                for item in context.character_state.values
            ],
        }

    return payload
