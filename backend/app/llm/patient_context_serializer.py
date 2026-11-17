"""Explicit, least-privilege serialization boundary for Patient Agent context."""

from app.services.patient_context import (
    PatientCaseFact,
    PatientContext,
    PatientTranscriptMessage,
)


PATIENT_AGENT_CONTEXT_SCHEMA_VERSION = "2.0"


def _serialize_transcript_message(
    message: PatientTranscriptMessage,
) -> dict[str, str]:
    return {
        "role": message.role,
        "content": message.content,
    }


def _is_authorized_case_disclosure(fact: PatientCaseFact) -> bool:
    if fact.information_class != "established_fact":
        return False

    if fact.disclosure_policy == "initial_disclosure":
        return True

    return (
        fact.disclosure_policy == "contextually_disclosable"
        and fact.disclosure_status == "confirmed_disclosed"
    )


def patient_context_to_payload(
    context: PatientContext,
) -> dict[str, object]:
    """Build the minimal context that the Patient Agent is permitted to see.

    Internal case formulation, undisclosed facts, model-generated memory
    summaries, process state, and character-state metadata stay outside the
    model request. Contextual facts cross this boundary only after disclosure
    has been explicitly confirmed.
    """

    if not isinstance(context, PatientContext):
        raise TypeError("context must be a PatientContext instance.")

    identity = context.public_identity

    return {
        "context_schema_version": PATIENT_AGENT_CONTEXT_SCHEMA_VERSION,
        "language": context.language,
        "modality": context.modality,
        "public_identity": {
            "display_name": identity.display_name,
            "age": identity.age,
            "occupation": identity.occupation,
            "presenting_concerns": list(identity.presenting_concerns),
            "initial_disclosure": identity.initial_disclosure,
        },
        "disclosed_case_facts": [
            {
                "fact_category": fact.fact_category,
                "content": fact.content,
            }
            for fact in context.relevant_case_facts
            if _is_authorized_case_disclosure(fact)
        ],
        "longitudinal_disclosures": [
            {"content": memory.content}
            for memory in context.longitudinal_memory
            if memory.information_class == "explicit_disclosure"
        ],
        "recent_transcript": [
            _serialize_transcript_message(message)
            for message in context.recent_transcript
        ],
        "therapist_message": _serialize_transcript_message(
            context.therapist_message
        ),
    }
