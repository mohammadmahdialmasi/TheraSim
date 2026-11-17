import asyncio

from app.main import app
from app.services.cases import CaseService
from app.services.runs import RunService
from app.services.memory import MemoryService
from app.services.sessions import SessionService


def test_application_startup_initializes_both_databases(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "automatic-data"
    monkeypatch.setenv("THERASIM_DATA_DIR", str(data_dir))

    async def exercise_lifespan():
        async with app.router.lifespan_context(app):
            manager = app.state.database_manager

            assert isinstance(app.state.case_service, CaseService)
            assert isinstance(app.state.run_service, RunService)
            assert isinstance(app.state.session_service, SessionService)
            assert isinstance(app.state.memory_service, MemoryService)

            assert manager.path_for("operational").is_file()
            assert manager.path_for("restricted").is_file()

            assert app.state.database_migrations == {
                "operational": ["001_initial_core", "002_domain_persistence", "003_interaction_recovery", "004_session_transcript_integrity", "005_character_runtime", "006_unbounded_session_numbers", "007_memory_review_lifecycle", "008_memory_extraction_outbox", "009_memory_extraction_model_component", "010_versioned_run_protocols"],
                "restricted": ["001_initial_case_vault", "002_character_personality_profiles"],
            }

            for database in ("operational", "restricted"):
                with manager.connection(database) as connection:
                    assert connection.execute(
                        "PRAGMA foreign_keys"
                    ).fetchone()[0] == 1

    asyncio.run(exercise_lifespan())


def test_application_startup_preserves_existing_database_data(
    tmp_path,
    monkeypatch,
):
    data_dir = tmp_path / "persistent-data"
    monkeypatch.setenv("THERASIM_DATA_DIR", str(data_dir))

    async def first_start():
        async with app.router.lifespan_context(app):
            manager = app.state.database_manager

            with manager.transaction("operational") as connection:
                connection.execute(
                    """
                    INSERT INTO cases
                    (case_id, case_code, display_name, status,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "persistence-check",
                        "PERSISTENCE-CHECK",
                        "Persistence Check",
                        "draft",
                        "2026-11-16T00:00:00Z",
                        "2026-11-16T00:00:00Z",
                    ),
                )

    async def second_start():
        async with app.router.lifespan_context(app):
            manager = app.state.database_manager

            assert app.state.database_migrations == {
                "operational": ["001_initial_core", "002_domain_persistence", "003_interaction_recovery", "004_session_transcript_integrity", "005_character_runtime", "006_unbounded_session_numbers", "007_memory_review_lifecycle", "008_memory_extraction_outbox", "009_memory_extraction_model_component", "010_versioned_run_protocols"],
                "restricted": ["001_initial_case_vault", "002_character_personality_profiles"],
            }

            with manager.connection("operational") as connection:
                count = connection.execute(
                    """
                    SELECT COUNT(*) FROM cases
                    WHERE case_id = ?
                    """,
                    ("persistence-check",),
                ).fetchone()[0]

                migration_count = connection.execute(
                    "SELECT COUNT(*) FROM schema_migrations"
                ).fetchone()[0]

            assert count == 1
            assert migration_count == 10

    asyncio.run(first_start())
    asyncio.run(second_start())

def test_application_startup_wires_patient_agent_when_model_is_configured(
    tmp_path,
    monkeypatch,
):
    from dataclasses import replace

    import app.main as main_module
    from app.core.config import ProviderConfig
    from app.services.interactions import InteractionService

    data_dir = tmp_path / "configured-model-data"
    monkeypatch.setenv("THERASIM_DATA_DIR", str(data_dir))

    configured_settings = replace(
        main_module.settings,
        llm_provider="ollama",
        ollama_model="local-test-model",
    )
    monkeypatch.setattr(main_module, "settings", configured_settings)

    created_clients = []

    class FakeOpenAICompatibleClient:
        def __init__(self, *, config, timeout):
            assert isinstance(config, ProviderConfig)
            self.config = config
            self.timeout = timeout
            created_clients.append(self)

        def chat(self, model, messages, temperature=None, max_tokens=None):
            raise AssertionError("Startup must not call the model provider.")

    monkeypatch.setattr(
        main_module,
        "OpenAICompatibleClient",
        FakeOpenAICompatibleClient,
    )

    async def exercise_lifespan():
        async with app.router.lifespan_context(app):
            assert app.state.patient_agent is not None
            assert isinstance(
                app.state.interaction_service,
                InteractionService,
            )
            from app.services.memory_extraction import (
                MemoryExtractionStatusService,
                MemoryExtractionWorker,
            )

            assert isinstance(
                app.state.memory_extraction_status_service,
                MemoryExtractionStatusService,
            )
            assert isinstance(
                app.state.memory_extraction_worker,
                MemoryExtractionWorker,
            )
            assert len(created_clients) == 1
            assert created_clients[0].config.model == "local-test-model"
            assert created_clients[0].timeout == configured_settings.request_timeout_seconds

    asyncio.run(exercise_lifespan())
    assert app.state.memory_extraction_worker is None
