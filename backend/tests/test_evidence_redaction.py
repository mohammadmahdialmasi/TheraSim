import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evidence_redaction import (  # noqa: E402
    create_sanitized_export,
    redact_text,
    scan_sensitive_patterns,
)


def test_redacts_windows_temp_user_email_and_secret() -> None:
    text = (
        r"C:\Users\Alice\AppData\Local\Temp\TheraSim-smoke-123\therasim.log "
        "owner=alice@example.com password=SuperSecret API_KEY:abc123 "
        "[REDACTED_HOME]"
    )
    redacted, resolved = redact_text(text, r"D:\Projects\TheraSim")

    assert "Alice" not in redacted
    assert "alice@example.com" not in redacted
    assert "SuperSecret" not in redacted
    assert "abc123" not in redacted
    assert "[REDACTED_TEMP]" in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_SECRET]" in redacted
    assert "already_redacted" in resolved


def test_already_redacted_text_is_stable() -> None:
    text = "Repository [REPOSITORY_ROOT], home [REDACTED_HOME], temp [REDACTED_TEMP]"
    redacted, resolved = redact_text(text, r"D:\Projects\TheraSim")
    assert redacted == text
    assert "already_redacted" in resolved
    assert scan_sensitive_patterns(redacted) == []


def test_redacts_doubled_backslashes_in_json_text() -> None:
    text = r'"FROM C:\\Users\\Alice\\.ollama\\models\\blobs\\sha256-abc"'
    redacted, resolved = redact_text(text, r"D:\Projects\TheraSim")
    assert "Alice" not in redacted
    assert "[REDACTED_USER]" in redacted
    assert "windows_user_profile" in resolved


def test_sanitized_export_excludes_private_file_types(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    sanitized = tmp_path / "sanitized"
    raw.mkdir()
    (raw / "command.log").write_text(
        r"C:\Users\Alice\AppData\Local\Temp\probe123 password=secret",
        encoding="utf-8",
    )
    (raw / "private.db").write_bytes(b"not evidence")
    (raw / ".env").write_text("API_KEY=secret", encoding="utf-8")

    audit = create_sanitized_export(raw, sanitized, r"D:\Projects\TheraSim")

    exported = (sanitized / "command.log").read_text(encoding="utf-8")
    assert "Alice" not in exported
    assert "password=[REDACTED_SECRET]" in exported
    assert not (sanitized / "private.db").exists()
    assert not (sanitized / ".env").exists()
    assert set(audit["excluded_files"]) == {"private.db", ".env"}
    assert json.loads((sanitized / "privacy_audit.json").read_text(encoding="utf-8"))["excluded_files"]


def test_windows_verifier_uses_legacy_output_syntax_and_traversal_guard() -> None:
    verifier = (REPO_ROOT / "scripts" / "verify-windows-package.ps1").read_text(
        encoding="utf-8"
    )
    assert "ProcessInformation processInformation;" in verifier
    assert "out processInformation" in verifier
    assert "out var processInformation" not in verifier
    assert "unsafe archive path" in verifier
    assert "exit 1" in verifier


def test_benchmark_constants_and_synthetic_cases_remain_documented() -> None:
    patient = (
        REPO_ROOT / "backend" / "app" / "llm" / "patient_agent.py"
    ).read_text(encoding="utf-8")
    evaluator = (
        REPO_ROOT / "backend" / "app" / "llm" / "evaluator_agent.py"
    ).read_text(encoding="utf-8")
    benchmark = (
        REPO_ROOT / "scripts" / "benchmark_agent_workflows.py"
    ).read_text(encoding="utf-8")

    assert "DEFAULT_PATIENT_AGENT_TEMPERATURE = 0.7" in patient
    assert "DEFAULT_PATIENT_AGENT_MAX_TOKENS = 1024" in patient
    assert "DEFAULT_EVALUATOR_MAX_TOKENS = 8192" in evaluator
    assert "temperature=0.0" in evaluator
    assert "english_workplace_values" in benchmark
    assert "persian_workplace_values" in benchmark
