import json
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.api.routes import support as support_routes
from app.core.config import PROVIDER_NAMES
from app.main import app


client = TestClient(app)


def test_support_export_requires_explicit_confirmation():
    response = client.post(
        "/api/v1/support/export",
        json={"confirmed": False},
    )

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Explicit confirmation")


def test_support_export_contains_only_allowlisted_sanitized_diagnostics(
    monkeypatch,
):
    secret = "synthetic-api-secret-MUST-NOT-EXPORT"
    monkeypatch.setattr(
        support_routes,
        "settings",
        SimpleNamespace(
            app_name="TheraSim API",
            app_version="0.3.0",
            llm_provider="custom",
            providers={
                name: SimpleNamespace(
                    base_url="https://synthetic-private.example.test/path",
                    model="synthetic-private-model",
                    api_key=secret,
                )
                for name in PROVIDER_NAMES
            },
        ),
    )
    response = client.post(
        "/api/v1/support/export",
        json={"confirmed": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    assert "TheraSim-support-diagnostics.zip" in response.headers[
        "content-disposition"
    ]

    with ZipFile(BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"diagnostics.json", "README.txt"}
        diagnostics = archive.read("diagnostics.json").decode("utf-8")
        report = json.loads(diagnostics)
        readme = archive.read("README.txt").decode("utf-8")

    assert report["application"]["version"]
    assert report["runtime"]["operating_system"]
    assert report["privacy"] == {
        "user_records_included": False,
        "transcripts_included": False,
        "case_content_included": False,
        "logs_included": False,
        "credentials_included": False,
        "personal_information_included": False,
        "provider_endpoints_included": False,
    }
    archive_text = diagnostics + readme
    for forbidden in (
        secret,
        "synthetic-private.example.test",
        "synthetic-private-model",
        "private reviewer name",
        "fictional transcript body",
    ):
        assert forbidden.casefold() not in archive_text.casefold()


def test_support_export_is_never_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("THERASIM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/v1/support/export",
        json={"confirmed": True},
    )

    assert response.status_code == 200
    assert list(tmp_path.rglob("TheraSim-support-diagnostics.zip")) == []


def test_support_preview_and_persian_export_are_language_aware():
    preview = client.get("/api/v1/support/preview", params={"language": "fa"})
    assert preview.status_code == 200
    assert preview.json()["language"] == "fa"

    response = client.post(
        "/api/v1/support/export",
        json={"confirmed": True, "language": "fa"},
    )
    assert response.status_code == 200
    assert "TheraSim-support-diagnostics-fa.zip" in response.headers[
        "content-disposition"
    ]

    with ZipFile(BytesIO(response.content)) as archive:
        readme = archive.read("README.txt").decode("utf-8")
    assert "اطلاعات عیب‌یابی" in readme
