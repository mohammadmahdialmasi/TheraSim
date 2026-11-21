"""Manual, read-only release metadata and safe source-checkout reporting."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


RELEASES_LATEST_URL = (
    "https://api.github.com/repos/mohammadmahdialmasi/TheraSim/releases/latest"
)
REPOSITORY_RELEASE_PREFIX = (
    "https://github.com/mohammadmahdialmasi/TheraSim/releases/"
)
_VERSION_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_SHA256_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
_WINDOWS_PACKAGE_RE = re.compile(
    r"^TheraSim-v\d+\.\d+\.\d+(?:-windows-x64\.zip|-Windows-x64-Portable\.zip)$"
)


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.fullmatch(value)
    return tuple(int(part) for part in match.groups()) if match else None


def _checked_release(payload: Any, current_version: str) -> dict[str, object]:
    if (
        not isinstance(payload, dict)
        or payload.get("draft") is not False
        or payload.get("prerelease") is not False
    ):
        raise ValueError("No stable release metadata was returned.")

    tag = payload.get("tag_name")
    release_version = _version_tuple(tag) if isinstance(tag, str) else None
    current = _version_tuple(current_version)
    release_url = payload.get("html_url")
    published_at = payload.get("published_at")
    body = payload.get("body")
    if (
        release_version is None
        or current is None
        or not isinstance(release_url, str)
        or not release_url.startswith(REPOSITORY_RELEASE_PREFIX)
        or not isinstance(published_at, str)
        or not isinstance(body, str)
    ):
        raise ValueError("Release metadata did not match the expected format.")

    assets_payload = payload.get("assets", [])
    assets: list[dict[str, object]] = []
    if isinstance(assets_payload, list):
        for item in assets_payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            browser_url = item.get("browser_download_url")
            digest = item.get("digest")
            size = item.get("size")
            if (
                not isinstance(name, str)
                or not _WINDOWS_PACKAGE_RE.fullmatch(name)
                or not isinstance(browser_url, str)
                or not browser_url.startswith(
                    "https://github.com/mohammadmahdialmasi/TheraSim/releases/download/"
                )
                or not isinstance(digest, str)
            ):
                continue
            checksum_match = _SHA256_RE.fullmatch(digest)
            if checksum_match is None:
                continue
            assets.append(
                {
                    "name": name,
                    "download_url": browser_url,
                    "sha256": checksum_match.group(1).lower(),
                    "size_bytes": size if isinstance(size, int) and size >= 0 else None,
                    "checksum_source": "GitHub release asset digest",
                }
            )

    return {
        "version": tag,
        "published_at": published_at,
        "notes": body[:12000],
        "release_url": release_url,
        "update_available": release_version > current,
        "assets": assets,
    }


def get_latest_release_metadata(
    current_version: str,
    *,
    timeout_seconds: float = 5.0,
) -> dict[str, object]:
    """Fetch stable release metadata only when explicitly requested."""

    request = Request(
        RELEASES_LATEST_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "TheraSim-manual-update-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if getattr(response, "status", 200) != 200:
                raise URLError("Unexpected release metadata status.")
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Release metadata response was too large.")
        return {
            "status": "available",
            **_checked_release(json.loads(raw), current_version),
        }
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {
            "status": "unavailable",
            "message": (
                "Release metadata is unavailable. Check your connection or "
                "visit the release page later."
            ),
        }


def get_source_checkout_status(
    repository_root: Path,
    *,
    timeout_seconds: float = 2.0,
) -> dict[str, object] | None:
    """Read branch, commit and dirty status without exposing changed paths."""

    root = repository_root.resolve()
    if not (root / ".git").exists():
        return None

    def run_git(*arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if result.returncode != 0:
            raise OSError("Git metadata could not be read.")
        return result.stdout.strip()

    try:
        branch = run_git("branch", "--show-current") or "detached"
        commit = run_git("rev-parse", "--verify", "HEAD")
        status = run_git("status", "--porcelain", "--untracked-files=normal")
    except (OSError, subprocess.SubprocessError):
        return {
            "available": False,
            "message": "Source checkout status could not be read.",
        }

    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
        return {
            "available": False,
            "message": "Source checkout status could not be read.",
        }
    return {
        "available": True,
        "branch": branch[:120],
        "commit": commit[:12].lower(),
        "dirty": bool(status),
    }
