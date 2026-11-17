"""Registry of therapy simulation modality contracts."""

from dataclasses import dataclass
from typing import Literal


ImplementationStatus = Literal[
    "implemented",
    "partial",
    "registered",
    "planned",
]


@dataclass(frozen=True, slots=True)
class RubricReference:
    rubric_id: str
    version: str
    scope: Literal["session", "longitudinal"]


@dataclass(frozen=True, slots=True)
class ModalityDefinition:
    modality_id: str
    display_name: str
    version: str
    description: str
    theoretical_foundations: tuple[str, ...]
    relevant_processes: tuple[str, ...]
    treatment_planning_capabilities: tuple[str, ...]
    session_planning_capabilities: tuple[str, ...]
    evaluation_rubrics: tuple[RubricReference, ...]
    patient_simulation_requirements: tuple[str, ...]
    supported_interventions: tuple[str, ...]
    limitations: tuple[str, ...]
    implementation_status: ImplementationStatus
    validation_status: str
    protocol_id: str
    protocol_version: str

    @property
    def session_rubric(self) -> RubricReference | None:
        return next(
            (item for item in self.evaluation_rubrics if item.scope == "session"),
            None,
        )

    @property
    def is_runnable(self) -> bool:
        return self.implementation_status in {"implemented", "partial"}


class ModalityRegistry:
    """Stores versioned modality contracts and rejects ambiguous identities."""

    def __init__(
        self,
        definitions: tuple[ModalityDefinition, ...] = (),
    ) -> None:
        self._definitions: dict[str, ModalityDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: ModalityDefinition) -> None:
        if not isinstance(definition, ModalityDefinition):
            raise TypeError("A ModalityDefinition is required.")

        identity = definition.modality_id.strip().casefold()
        if not identity or not definition.version.strip():
            raise ValueError("A modality ID and version are required.")
        if not definition.protocol_id.strip() or not definition.protocol_version.strip():
            raise ValueError("A modality protocol ID and version are required.")
        if identity in self._definitions:
            raise ValueError(f"Modality is already registered: {definition.modality_id}")

        self._definitions[identity] = definition

    def get(self, modality_id: str) -> ModalityDefinition | None:
        return self._definitions.get(modality_id.strip().casefold())

    def get_runnable(self, modality_id: str) -> ModalityDefinition | None:
        definition = self.get(modality_id)
        if definition is None or not definition.is_runnable:
            return None
        return definition

    def list(self) -> tuple[ModalityDefinition, ...]:
        return tuple(self._definitions.values())


ACT_MODALITY = ModalityDefinition(
    modality_id="ACT",
    display_name="Acceptance and Commitment Therapy",
    version="0.1",
    description=(
        "The initial educational simulation modality. Its rubrics are "
        "experimental and are not clinically or psychometrically validated."
    ),
    theoretical_foundations=("Acceptance and Commitment Therapy",),
    relevant_processes=(
        "acceptance",
        "cognitive_defusion",
        "present_moment_awareness",
        "self_as_context",
        "values",
        "committed_action",
        "psychological_flexibility",
        "experiential_avoidance",
    ),
    treatment_planning_capabilities=(),
    session_planning_capabilities=(),
    evaluation_rubrics=(
        RubricReference("ACT_RUBRIC_V0", "0.2", "session"),
        RubricReference("ACT_LONGITUDINAL_RUBRIC_V0", "0.2", "longitudinal"),
    ),
    patient_simulation_requirements=("synthetic_case_profile", "configured_local_model"),
    supported_interventions=(),
    limitations=(
        "Treatment-plan adaptation is not implemented.",
        "Therapist evaluation generation is not implemented.",
        "Psychological processes are not validated measurements.",
    ),
    implementation_status="partial",
    validation_status="experimental_not_clinically_validated",
    protocol_id="ACT_EDUCATIONAL_SIMULATION",
    protocol_version="0.1",
)


DEFAULT_MODALITY_REGISTRY = ModalityRegistry((ACT_MODALITY,))
