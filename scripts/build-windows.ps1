[CmdletBinding()]
param(
    [string]$PythonExe = (Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"),
    [string]$OutputZip = (Join-Path $PSScriptRoot "..\dist\TheraSim-v0.2.1-windows-x64.zip")
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = (Resolve-Path $PythonExe).Path
$pythonVersion = (& $python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
if ($pythonVersion -ne "3.13") {
    throw "The reproducible Windows build requires Python 3.13; found $pythonVersion."
}
$is64BitPython = (& $python -c "import struct; print(struct.calcsize('P') == 8)").Trim()
if ($is64BitPython -ne "True") {
    throw "A 64-bit Python interpreter is required for the Windows x64 package."
}
$node = Get-Command node.exe -ErrorAction SilentlyContinue
if (-not $node) {
    $candidate = Join-Path $env:ProgramFiles "nodejs\node.exe"
    if (Test-Path $candidate) {
        $nodePath = Split-Path $candidate
        $env:Path = "$nodePath;$env:Path"
    } else {
        throw "Node.js 22 or newer is required to build the frontend."
    }
}

$nodeVersion = (& node.exe --version).Trim().TrimStart("v")
if ([version]$nodeVersion -lt [version]"22.0") {
    throw "Node.js 22 or newer is required; found $nodeVersion."
}

$output = [System.IO.Path]::GetFullPath($OutputZip)
if (Test-Path $output) {
    throw "Refusing to overwrite an existing package: $output"
}
New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
$staging = Join-Path ([System.IO.Path]::GetTempPath()) "TheraSim-build-$PID"
if (Test-Path $staging) {
    throw "Temporary build directory already exists: $staging"
}
New-Item -ItemType Directory -Path $staging | Out-Null

try {
    Push-Location (Join-Path $root "frontend")
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed." }
        & npm.cmd run lint
        if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
        & npm.cmd run build -- --outDir (Join-Path $staging "frontend") --emptyOutDir
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }

    & $python -m pip install --requirement (Join-Path $root "backend\requirements-lock.txt")
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
    & $python -m pip install --requirement (Join-Path $root "packaging\windows\requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "Packaging dependency installation failed." }

    $env:THERASIM_FRONTEND_DIST = Join-Path $staging "frontend"
    Push-Location $root
    try {
        & $python -m PyInstaller `
            --noconfirm `
            --clean `
            --distpath (Join-Path $staging "dist") `
            --workpath (Join-Path $staging "work") `
            "packaging\windows\TheraSim.spec"
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
    } finally {
        Pop-Location
        Remove-Item Env:\THERASIM_FRONTEND_DIST -ErrorAction SilentlyContinue
    }

    $packageDir = Join-Path $staging "dist\TheraSim"
    if (-not (Test-Path (Join-Path $packageDir "TheraSim.exe"))) {
        throw "The build did not produce TheraSim.exe."
    }
    if (-not (Test-Path (Join-Path $packageDir "_internal\frontend\index.html"))) {
        throw "The built frontend was not included in the Windows package."
    }
    Compress-Archive -Path $packageDir -DestinationPath $output -CompressionLevel Optimal
    $hash = (Get-FileHash -Algorithm SHA256 $output).Hash.ToLowerInvariant()
    Set-Content -Path "$output.sha256" -Value "$hash  $(Split-Path $output -Leaf)" -Encoding ascii
    Write-Output "Package: $output"
    Write-Output "SHA-256: $hash"
} finally {
    if (Test-Path $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force
    }
}
