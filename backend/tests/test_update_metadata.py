from pathlib import Path
import subprocess

from app.services import update_metadata
from app.api.routes import updates as update_routes


class FakeResponse:
    status = 200

    def __init__(self, value: bytes) -> None:
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit: int) -> bytes:
        return self.value


def _release_payload(**overrides):
    payload = {
        "draft": False,
        "prerelease": False,
        "tag_name": "v0.4.0",
        "html_url": (
            "https://github.com/mohammadmahdialmasi/TheraSim/"
            "releases/tag/v0.4.0"
        ),
        "published_at": "2026-11-18T12:00:00Z",
        "body": "Release notes",
        "assets": [
            {
                "name": "TheraSim-v0.4.0-Windows-x64-Portable.zip",
                "browser_download_url": (
                    "https://github.com/mohammadmahdialmasi/TheraSim/"
                    "releases/download/v0.4.0/"
                    "TheraSim-v0.4.0-Windows-x64-Portable.zip"
                ),
                "digest": "sha256:" + "a" * 64,
                "size": 123,
            },
            {
                "name": "TheraSim-v0.4.0-Windows-x64-Portable.zip.sha256",
                "browser_download_url": "https://example.test/sidecar",
                "digest": None,
                "size": 99,
            },
        ],
    }
    payload.update(overrides)
    return payload


def test_update_check_returns_stable_metadata_and_sha256_asset(monkeypatch):
    import json

    monkeypatch.setattr(
        update_metadata,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            json.dumps(_release_payload()).encode()
        ),
    )

    result = update_metadata.get_latest_release_metadata("0.3.1")

    assert result["status"] == "available"
    assert result["version"] == "v0.4.0"
    assert result["update_available"] is True
    assert result["published_at"] == "2026-11-18T12:00:00Z"
    assert result["notes"] == "Release notes"
    assert len(result["assets"]) == 1
    assert result["assets"][0]["sha256"] == "a" * 64
    assert result["assets"][0]["checksum_source"] == (
        "GitHub release asset digest"
    )


def test_update_check_rejects_unstable_or_unverified_asset(monkeypatch):
    import json

    payload = _release_payload(
        prerelease=True,
        assets=[
            {
                "name": "TheraSim-v0.4.0-Windows-x64-Portable.zip",
                "browser_download_url": (
                    "https://github.com/mohammadmahdialmasi/TheraSim/"
                    "releases/download/v0.4.0/"
                    "TheraSim-v0.4.0-Windows-x64-Portable.zip"
                ),
                "digest": None,
                "size": 123,
            }
        ],
    )
    monkeypatch.setattr(
        update_metadata,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode()),
    )

    result = update_metadata.get_latest_release_metadata("0.3.1")

    assert result["status"] == "unavailable"
    assert "assets" not in result


def test_update_check_accepts_the_existing_legacy_windows_asset_name():
    assert update_metadata._WINDOWS_PACKAGE_RE.fullmatch(
        "TheraSim-v0.2.0-windows-x64.zip"
    )


def test_update_check_is_offline_safe_and_does_not_raise(monkeypatch):
    def offline(*_args, **_kwargs):
        raise OSError("network unavailable")

    monkeypatch.setattr(update_metadata, "urlopen", offline)

    result = update_metadata.get_latest_release_metadata("0.3.1")

    assert result["status"] == "unavailable"
    assert "network unavailable" not in str(result)


def test_source_checkout_reporting_omits_paths_and_runs_read_only_git(
    tmp_path: Path,
    monkeypatch,
):
    (tmp_path / ".git").mkdir()
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command[3:])
        argument = command[3:]
        if argument[:2] == ["branch", "--show-current"]:
            stdout = "release-fix\n"
        elif argument[:2] == ["rev-parse", "--verify"]:
            stdout = "a" * 40 + "\n"
        else:
            stdout = " M private-file.txt\n?? private-untracked.txt\n"
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(update_metadata.subprocess, "run", fake_run)

    status = update_metadata.get_source_checkout_status(tmp_path)

    assert status == {
        "available": True,
        "branch": "release-fix",
        "commit": "a" * 12,
        "dirty": True,
    }
    assert all(
        command[0] in {"branch", "rev-parse", "status"}
        for command in commands
    )
    assert not any(
        "reset" in command or "checkout" in command or "pull" in command
        for command in commands
    )
    assert "private-file.txt" not in str(status)
    assert "private-untracked.txt" not in str(status)


def test_non_checkout_does_not_run_git(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        update_metadata.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("git must not run outside a checkout")
        ),
    )

    assert update_metadata.get_source_checkout_status(tmp_path) is None


def test_update_route_is_manual_and_marks_auto_install_unsupported(monkeypatch):
    monkeypatch.setattr(
        update_routes,
        "get_latest_release_metadata",
        lambda version: {
            "status": "available",
            "version": "v0.2.0",
            "update_available": False,
        },
    )
    monkeypatch.setattr(
        update_routes,
        "get_source_checkout_status",
        lambda _root: {
            "available": True,
            "branch": "release-fix",
            "commit": "a" * 12,
            "dirty": True,
        },
    )

    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).get("/api/v1/updates/check")

    assert response.status_code == 200
    result = response.json()
    assert result["release"]["version"] == "v0.2.0"
    assert result["source_checkout"]["dirty"] is True
    assert result["automatic_installation"] is False
