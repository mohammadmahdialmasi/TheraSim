"""Privacy helpers for manuscript evidence exports."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Iterable


EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
WINDOWS_PATH_RE = re.compile(
    r"(?i)(?:[A-Z]:\\(?:Users\\[^\\\s]+|Temp|Windows)[^ \t\r\n\"']*)"
)
WINDOWS_USER_RE = re.compile(
    r"(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/\\r\\n\\t ]+"
)
TEMP_PATH_RE = re.compile(r"(?i)[A-Z]:\\(?:Users\\[^\\]+\\)?AppData\\Local\\Temp\\[^ \t\r\n\"']+")
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|secret|client[_-]?secret)\b(\s*[=:]\s*)([^\s,;]+)",
)
HOME_PLACEHOLDER_RE = re.compile(r"\[(?:REDACTED_HOME|REPOSITORY_ROOT|REDACTED_TEMP)\]")


def redact_text(text: str, repository_root: str | None = None) -> tuple[str, list[str]]:
    """Return redacted text and a list of pattern categories resolved."""
    resolved: list[str] = []

    if HOME_PLACEHOLDER_RE.search(text):
        resolved.append("already_redacted")

    if repository_root:
        normalized_root = str(Path(repository_root)).replace("/", "\\")
        if normalized_root in text:
            text = text.replace(normalized_root, "[REPOSITORY_ROOT]")
            resolved.append("repository_absolute_path")

    if TEMP_PATH_RE.search(text):
        text = TEMP_PATH_RE.sub("[REDACTED_TEMP]", text)
        resolved.append("temporary_directory")

    if WINDOWS_USER_RE.search(text):
        text = WINDOWS_USER_RE.sub(r"\1[REDACTED_USER]", text)
        resolved.append("windows_user_profile")

    if WINDOWS_PATH_RE.search(text):
        text = WINDOWS_PATH_RE.sub("[REDACTED_LOCAL_PATH]", text)
        resolved.append("windows_filesystem_path")

    if EMAIL_RE.search(text):
        text = EMAIL_RE.sub("[REDACTED_EMAIL]", text)
        resolved.append("email_address")

    if SECRET_ASSIGNMENT_RE.search(text):
        text = SECRET_ASSIGNMENT_RE.sub(r"\1\2[REDACTED_SECRET]", text)
        resolved.append("secret_assignment")

    return text, list(dict.fromkeys(resolved))


def scan_sensitive_patterns(text: str) -> list[str]:
    found: list[str] = []
    text = text.replace("[REDACTED_USER]", "").replace("[REDACTED_HOME]", "")
    checks = (
        ("windows_user_profile", WINDOWS_USER_RE),
        ("temporary_directory", TEMP_PATH_RE),
        ("email_address", EMAIL_RE),
        ("secret_assignment", SECRET_ASSIGNMENT_RE),
    )
    for name, pattern in checks:
        if pattern.search(text):
            found.append(name)
    return found


def create_sanitized_export(
    raw_directory: Path,
    sanitized_directory: Path,
    repository_root: str,
) -> dict[str, object]:
    if sanitized_directory.exists():
        shutil.rmtree(sanitized_directory)
    sanitized_directory.mkdir(parents=True)

    prohibited_suffixes = {".db", ".sqlite", ".sqlite3", ".gguf", ".safetensors", ".bin", ".pth", ".pt", ".onnx"}
    detected: list[str] = []
    excluded: list[str] = []

    for source in raw_directory.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(raw_directory)
        if source.suffix.lower() in prohibited_suffixes or source.name.lower() in {".env"}:
            excluded.append(relative.as_posix())
            continue

        try:
            original = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            excluded.append(relative.as_posix())
            continue

        redacted, categories = redact_text(original, repository_root)
        remaining = scan_sensitive_patterns(redacted)
        if remaining:
            detected.extend(remaining)
        target = sanitized_directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(redacted, encoding="utf-8")

    audit = {
        "sanitized_directory": sanitized_directory.as_posix(),
        "excluded_files": excluded,
        "remaining_sensitive_patterns": sorted(set(detected)),
        "resolved_file_count": sum(1 for path in sanitized_directory.rglob("*") if path.is_file()),
    }
    (sanitized_directory / "privacy_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-directory", required=True)
    parser.add_argument("--sanitized-directory", required=True)
    parser.add_argument("--repository-root", required=True)
    args = parser.parse_args()
    audit = create_sanitized_export(
        Path(args.raw_directory),
        Path(args.sanitized_directory),
        args.repository_root,
    )
    print(json.dumps(audit, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
