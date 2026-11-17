# PyInstaller one-folder package. The model weights are deliberately excluded.
from pathlib import Path
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPECPATH).resolve().parents[1]
FRONTEND_DIST = Path(
    os.environ.get(
        "THERASIM_FRONTEND_DIST",
        str(ROOT / "frontend" / "dist"),
    )
).resolve()
if not (FRONTEND_DIST / "index.html").is_file():
    raise SystemExit(
        "Built frontend not found. Run the Windows build script first."
    )

datas = [(str(FRONTEND_DIST), "frontend")]
datas.append((str(ROOT / "rubrics"), "rubrics"))
migrations_root = ROOT / "backend" / "app" / "persistence" / "migrations"
for migration_area in ("operational", "restricted"):
    migration_directory = migrations_root / migration_area
    if not migration_directory.is_dir():
        raise SystemExit(
            f"Required migration directory is missing: {migration_directory}"
        )
    migration_files = sorted(migration_directory.glob("*.sql"))
    if not migration_files:
        raise SystemExit(
            f"No SQL migrations were found in {migration_directory}"
        )
    datas.extend(
        (
            str(migration_file),
            f"app/persistence/migrations/{migration_area}",
        )
        for migration_file in migration_files
        if migration_file.is_file()
    )
binaries = []
hiddenimports = collect_submodules("app")
for package in ("cryptography", "fastapi", "pydantic", "starlette", "uvicorn"):
    package_datas, package_binaries, package_hiddenimports = collect_all(
        package
    )
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    [str(ROOT / "backend" / "app" / "desktop.py")],
    pathex=[str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TheraSim",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TheraSim",
)
