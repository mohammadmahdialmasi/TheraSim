"""Windows desktop launcher for the local TheraSim application."""

from __future__ import annotations

import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import socket
import sys
import webbrowser


CONFIG_KEYS = frozenset(
    {
        "THERASIM_LLM_PROVIDER",
        "THERASIM_LLM_TIMEOUT",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_API_KEY",
        "LM_STUDIO_BASE_URL",
        "LM_STUDIO_MODEL",
        "LM_STUDIO_API_KEY",
    }
)
DEFAULT_PORT = 8765


def user_data_dir(environ: dict[str, str] | None = None) -> Path:
    """Return a per-user data directory without touching repository data."""

    env = os.environ if environ is None else environ
    local_app_data = env.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).expanduser() / "TheraSim"
    return Path.home() / "AppData" / "Local" / "TheraSim"


def load_local_config(
    config_path: Path,
    environ: dict[str, str] | None = None,
) -> None:
    """Load allow-listed KEY=value settings without shell evaluation."""

    env = os.environ if environ is None else environ
    if not config_path.exists():
        return
    if not config_path.is_file():
        raise ValueError("TheraSim config path must be a regular file.")

    for line_number, raw_line in enumerate(
        config_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(
                f"Invalid TheraSim config entry on line {line_number}."
            )
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in CONFIG_KEYS:
            raise ValueError(
                f"Unsupported TheraSim config setting on line {line_number}."
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ValueError(
                f"Invalid TheraSim config value on line {line_number}."
            )
        # Explicit process environment values take precedence over the file.
        env.setdefault(key, value)


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def _configure_logging(data_dir: Path) -> None:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = RotatingFileHandler(
        log_dir / "therasim.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[log_file, logging.StreamHandler()],
        force=True,
    )


def _check_port_available(port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", port))
    except OSError as exc:
        raise RuntimeError(
            f"TheraSim could not use local port {port}. "
            "Close the other local application using that port and try again."
        ) from exc


def _port_from_environment() -> int:
    raw_port = os.environ.get("THERASIM_PORT", str(DEFAULT_PORT))
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("THERASIM_PORT must be a valid port number.") from exc
    if not 1024 <= port <= 65535:
        raise ValueError("THERASIM_PORT must be between 1024 and 65535.")
    return port


async def _serve(port: int) -> None:
    # Import after applying the per-user runtime configuration so Settings and
    # the optional frontend mount are initialized from the intended paths.
    from app.main import app
    import uvicorn

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_config=None,
        access_log=False,
        lifespan="on",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve(), name="therasim-api")

    while not server.started and not server_task.done():
        await asyncio.sleep(0.1)

    if server_task.done():
        error = server_task.exception()
        if error is not None:
            raise RuntimeError(
                "TheraSim could not start its local web service. "
                "Check the log for details."
            ) from error
        raise RuntimeError(
            "TheraSim stopped before its local web service was ready. "
            "Check the log for details."
        )

    url = f"http://127.0.0.1:{port}/"
    logging.getLogger(__name__).info("TheraSim is ready at %s", url)
    try:
        webbrowser.open(url)
    except Exception:
        logging.getLogger(__name__).exception(
            "Could not open a browser automatically; use %s", url
        )

    await server_task


def run() -> int:
    """Start the application and return a process exit code."""

    data_dir = user_data_dir()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        _configure_logging(data_dir)
        load_local_config(data_dir / "config.env")

        runtime_root = _runtime_root()
        frontend_dir = runtime_root / "frontend"
        if not (frontend_dir / "index.html").is_file():
            raise RuntimeError(
                "The TheraSim web interface is missing. "
                "Rebuild the Windows package."
            )

        os.environ["THERASIM_DATA_DIR"] = str(data_dir / "data")
        os.environ["THERASIM_STATIC_DIR"] = str(frontend_dir)
        port = _port_from_environment()
        _check_port_available(port)
        asyncio.run(_serve(port))
        return 0
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("TheraSim is shutting down.")
        return 0
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.exception("TheraSim could not start.")
        print(f"TheraSim could not start: {exc}", file=sys.stderr)
        if getattr(sys, "frozen", False):
            try:
                input("Press Enter to close this window...")
            except EOFError:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
