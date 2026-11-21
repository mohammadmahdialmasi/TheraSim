"""Best-effort hardware inventory for explicit user-requested assessment."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform
import shutil
import subprocess
from urllib.parse import urlsplit

import httpx


def _memory_bytes() -> tuple[int | None, int | None]:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong),
                ("avail_phys", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("avail_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.total_phys), int(status.avail_phys)
        return None, None

    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_pages = os.sysconf("SC_PHYS_PAGES")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return None, None
    return int(page_size * total_pages), int(page_size * available_pages)


def _cpu_name() -> str | None:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if isinstance(value, str) and value.strip():
                return value.strip()
        except OSError:
            pass
    return (
        os.environ.get("PROCESSOR_IDENTIFIER")
        or platform.processor()
        or None
    )


def _detect_nvidia_gpus() -> tuple[list[dict[str, object]], str]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return [], "nvidia_smi_unavailable; other GPU vendors not queried"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=False,
            creationflags=flags,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return [], "nvidia_smi_query_failed"
    if result.returncode != 0:
        return [], "nvidia_smi_query_failed"

    gpus: list[dict[str, object]] = []
    for line in result.stdout.splitlines():
        fields = [field.strip() for field in line.split(",", maxsplit=2)]
        if len(fields) != 3 or not fields[0]:
            continue
        try:
            total_mib = int(fields[1])
            free_mib = int(fields[2])
        except ValueError:
            continue
        gpus.append(
            {
                "vendor": "NVIDIA",
                "name": fields[0],
                "total_vram_bytes": total_mib * 1024 * 1024,
                "available_vram_bytes": free_mib * 1024 * 1024,
            }
        )
    return (
        gpus,
        "detected"
        if gpus
        else "nvidia_gpu_not_detected; other GPU vendors not queried",
    )


def _resource_tier(value: int | None, boundaries: tuple[int, ...]) -> str:
    if value is None:
        return "unknown"
    for boundary, label in zip(
        boundaries,
        ("under_8_gib", "8_to_16_gib", "16_to_32_gib"),
    ):
        if value < boundary:
            return label
    return "32_gib_or_more"


def _vram_tier(value: int | None) -> str:
    if value is None:
        return "unknown"
    gib = 1024**3
    if value < 6 * gib:
        return "under_6_gib"
    if value < 8 * gib:
        return "6_to_8_gib"
    if value < 12 * gib:
        return "8_to_12_gib"
    if value < 16 * gib:
        return "12_to_16_gib"
    return "16_gib_or_more"


def _probe_ollama(base_url: str) -> dict[str, object]:
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        port = None
        parsed = urlsplit("")
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or port is None
    ):
        return {
            "server_available": None,
            "server_version": None,
            "server_status": "not_probed_non_loopback_or_invalid_endpoint",
        }

    origin = f"{parsed.scheme}://{parsed.netloc}"
    try:
        response = httpx.get(f"{origin}/api/version", timeout=0.75)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        return {
            "server_available": False,
            "server_version": None,
            "server_status": "unavailable",
        }
    version = body.get("version") if isinstance(body, dict) else None
    return {
        "server_available": True,
        "server_version": version if isinstance(version, str) else None,
        "server_status": "available",
    }


def assess_hardware(
    *,
    data_directory: Path | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
) -> dict[str, object]:
    """Return best-effort system facts; never downloads or contacts remote hosts."""

    memory_total, memory_available = _memory_bytes()
    data_path = data_directory or Path.home()
    try:
        disk = shutil.disk_usage(data_path)
        disk_info: dict[str, object] = {
            "scope": "application data volume",
            "total_bytes": disk.total,
            "free_bytes": disk.free,
        }
    except OSError:
        disk_info = {
            "scope": "application data volume",
            "total_bytes": None,
            "free_bytes": None,
        }

    gpus, gpu_status = _detect_nvidia_gpus()
    gib = 1024**3
    ollama_info: dict[str, object] = {
        "cli_available": shutil.which("ollama") is not None,
        **_probe_ollama(ollama_base_url),
    }
    return {
        "operating_system": {
            "name": platform.system(),
            "version": platform.version(),
            "architecture": platform.machine(),
        },
        "cpu": {
            "name": _cpu_name(),
            "logical_processors": os.cpu_count(),
        },
        "memory": {
            "total_bytes": memory_total,
            "available_bytes": memory_available,
        },
        "gpus": gpus,
        "gpu_detection": gpu_status,
        "resource_profile": {
            "system_ram_tier": _resource_tier(
                memory_total,
                (8 * gib, 16 * gib, 32 * gib),
            ),
            "detected_nvidia_gpu_vram_tiers": [
                _vram_tier(
                    gpu.get("total_vram_bytes")
                    if isinstance(gpu.get("total_vram_bytes"), int)
                    else None
                )
                for gpu in gpus
            ],
            "profile_is_a_compatibility_estimate": True,
            "recommendation": (
                "No model is selected or guaranteed to fit. Compare the "
                "exact installed model, quantization, context, and currently "
                "available memory, then run the synthetic agent benchmark."
            ),
        },
        "disk": disk_info,
        "ollama": ollama_info,
        "recommendation_status": (
            "resource inventory only; model compatibility must be verified "
            "for the exact provider, model tag, quantization, and context"
        ),
    }