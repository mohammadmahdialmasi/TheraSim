"""Resolve the source tree or frozen package resource root."""

from pathlib import Path
import sys


def project_root() -> Path:
    """Return the directory containing bundled/source resources."""

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[3]
