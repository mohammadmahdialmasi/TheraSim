import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "0.3.1"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_json_version(path: str) -> bool:
    data = json.loads(read(path))
    return data.get("version") == EXPECTED


def check_text(path: str, pattern: str) -> bool:
    match = re.search(pattern, read(path), re.MULTILINE)
    return match is not None and match.group(1) == EXPECTED


checks = [
    ("frontend/package.json", check_json_version("frontend/package.json")),
    (
        "frontend/package-lock.json",
        check_json_version("frontend/package-lock.json"),
    ),
    (
        "backend/app/core/config.py",
        check_text(
            "backend/app/core/config.py",
            r'app_version="([^"]+)"',
        ),
    ),
    (
        "frontend/src/App.tsx",
        "TheraSim · 0.3.1" in read("frontend/src/App.tsx"),
    ),
    (
        "build script",
        "TheraSim-v0.3.1-Windows-x64-Portable.zip"
        in read("scripts/build-windows.ps1"),
    ),
    (
        "Windows workflow",
        "TheraSim-v0.3.1-Windows-x64-Portable"
        in read(".github/workflows/windows-package.yml"),
    ),
]

failed = [name for name, passed in checks if not passed]
if failed:
    print(
        "Version consistency FAIL:",
        ", ".join(failed),
        file=sys.stderr,
    )
    sys.exit(1)

print(f"PASS: release version metadata is consistently {EXPECTED}")
