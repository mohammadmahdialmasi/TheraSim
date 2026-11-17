from dataclasses import replace

import pytest

from app.services.modalities import (
    ACT_MODALITY,
    DEFAULT_MODALITY_REGISTRY,
    ModalityRegistry,
)


def test_default_registry_exposes_only_the_current_act_module():
    definitions = DEFAULT_MODALITY_REGISTRY.list()

    assert len(definitions) == 1
    assert definitions[0].modality_id == "ACT"
    assert definitions[0].implementation_status == "partial"
    assert definitions[0].is_runnable
    assert definitions[0].validation_status == "experimental_not_clinically_validated"
    assert definitions[0].treatment_planning_capabilities == ()
    assert definitions[0].supported_interventions == ()


def test_registry_accepts_a_second_registered_extension_without_claiming_support():
    registry = ModalityRegistry((ACT_MODALITY,))
    extension_point = replace(
        ACT_MODALITY,
        modality_id="TEST-ONLY",
        display_name="Test registry extension",
        implementation_status="registered",
    )

    registry.register(extension_point)

    assert registry.get("test-only") == extension_point
    assert registry.get_runnable("test-only") is None
    assert {item.modality_id for item in registry.list()} == {"ACT", "TEST-ONLY"}


def test_registry_rejects_duplicate_modality_identity():
    registry = ModalityRegistry((ACT_MODALITY,))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(replace(ACT_MODALITY, modality_id="act"))
