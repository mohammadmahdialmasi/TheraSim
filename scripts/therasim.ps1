param(
    [ValidateSet("Start", "Stop", "Check")]
    [string]$Action = "Start"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$stateDirectory = Join-Path $env:LOCALAPPDATA "TheraSim\runtime"
$logDirectory = Join-Path $env:LOCALAPPDATA "TheraSim\logs"
$statePath = Join-Path $stateDirectory "development-processes.json"
$backendUrl = "http://127.0.0.1:8000/health"
$frontendUrl = "http://127.0.0.1:5173"

function Resolve-Executable([string[]]$Names, [string[]]$Fallbacks) {
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            return $command.Source
        }
    }
    foreach ($fallback in $Fallbacks) {
        if (Test-Path -LiteralPath $fallback -PathType Leaf) {
            return $fallback
        }
    }
    return $null
}

function Read-State {
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        return @{}
    }
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $state = @{}
    foreach ($property in $saved.PSObject.Properties) {
        $state[$property.Name] = $property.Value
    }
    return $state
}

function Save-State($State) {
    if (-not (Test-Path -LiteralPath $stateDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
    }
    $temporaryPath = "$statePath.tmp"
    $State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $statePath -Force
}

function Get-OwnedProcess($Entry) {
    if ($null -eq $Entry -or $null -eq $Entry.process_id) {
        return $null
    }
    $process = Get-Process -Id ([int]$Entry.process_id) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $null
    }
    try {
        if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$Entry.start_ticks) {
            return $null
        }
        $command = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction Stop
        if ([string]::Compare(
                [IO.Path]::GetFullPath($process.Path),
                [IO.Path]::GetFullPath([string]$Entry.executable),
                $true
            ) -ne 0 -or
            $command.CommandLine.IndexOf(
                [string]$Entry.marker,
                [StringComparison]::OrdinalIgnoreCase
            ) -lt 0) {
            return $null
        }
        return $process
    }
    catch {
        return $null
    }
}

function Stop-OwnedProcess($Entry, [string]$Name) {
    if ($null -eq $Entry -or $null -eq $Entry.process_id) {
        Write-Host "$Name is not running under this launcher."
        return $true
    }
    $process = Get-OwnedProcess $Entry
    if ($null -eq $process) {
        $processWithSameId = Get-Process -Id ([int]$Entry.process_id) -ErrorAction SilentlyContinue
        if ($null -ne $processWithSameId) {
            Write-Host "$Name PID $($Entry.process_id) no longer matches the saved process identity; it was left untouched."
            return $false
        }
        Write-Host "$Name process has already exited."
        return $true
    }
    Stop-Process -Id $process.Id -ErrorAction Stop
    Write-Host "Stopped launcher-owned $Name process (PID $($process.Id))."
    return $true
}

function Confirm-Install([string]$Message) {
    $answer = Read-Host "$Message [y/N]"
    return $answer -match "^(y|yes)$"
}

function Assert-ProjectFiles {
    $requiredFiles = @(
        (Join-Path $backend "app\main.py"),
        (Join-Path $backend "app\persistence\cli.py"),
        (Join-Path $backend "requirements.txt"),
        (Join-Path $backend "requirements-lock.txt"),
        (Join-Path $frontend "package.json"),
        (Join-Path $frontend "package-lock.json"),
        (Join-Path $frontend "vite.config.ts")
    )
    $missing = @($requiredFiles | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count -gt 0) {
        throw "Required project files are missing:`n$($missing -join "`n")"
    }
}

function Resolve-ProjectTools {
    $script:pythonLauncher = Resolve-Executable @("py.exe", "py") @()
    $script:systemPython = Resolve-Executable @("python.exe", "python") @()
    $script:nodeExecutable = Resolve-Executable @("node.exe", "node") @(
        (Join-Path $env:ProgramFiles "nodejs\node.exe")
    )
    $script:npmExecutable = Resolve-Executable @("npm.cmd", "npm") @(
        (Join-Path $env:ProgramFiles "nodejs\npm.cmd")
    )

    $venvCandidates = @(
        (Join-Path $backend ".venv\Scripts\python.exe"),
        (Join-Path $root ".venv\Scripts\python.exe")
    )
    $script:pythonExecutable = $venvCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

function Ensure-PythonEnvironment {
    if (-not $script:pythonExecutable) {
        if (-not $script:systemPython -and -not $script:pythonLauncher) {
            throw "Python 3 is required. Install Python 3.11 or newer, then run START_THERASIM.bat again."
        }
        if (-not (Confirm-Install "Create a project virtual environment and install backend dependencies now? This may need internet access.")) {
            throw "Backend environment setup was declined. No project data was changed."
        }
        $venvPath = Join-Path $root ".venv"
        if ($script:systemPython) {
            & $script:systemPython -m venv $venvPath
        }
        else {
            & $script:pythonLauncher -3 -m venv $venvPath
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Python could not create the virtual environment."
        }
        $script:pythonExecutable = Join-Path $venvPath "Scripts\python.exe"
    }

    $dependenciesReady = $false
    & $script:pythonExecutable -c "import fastapi, uvicorn"
    $dependenciesReady = ($LASTEXITCODE -eq 0)
    if (-not $dependenciesReady) {
        if (-not (Confirm-Install "Backend dependencies are missing. Install the pinned packages from requirements-lock.txt?")) {
            throw "Backend dependencies are missing. No project data was changed."
        }
        & $script:pythonExecutable -m pip install -r (Join-Path $backend "requirements-lock.txt")
        if ($LASTEXITCODE -ne 0) {
            throw "Backend dependency installation failed. Check internet access and the Python package log."
        }
    }
}

function Ensure-FrontendDependencies {
    if (-not $script:nodeExecutable) {
        throw "Node.js is required. Install the current Node.js LTS release, then run START_THERASIM.bat again."
    }
    if (-not $script:npmExecutable) {
        throw "npm was not found. Repair the Node.js installation or add its installation directory to PATH."
    }
    $viteEntry = Join-Path $frontend "node_modules\vite\bin\vite.js"
    if (-not (Test-Path -LiteralPath $viteEntry -PathType Leaf)) {
        if (-not (Confirm-Install "Frontend dependencies are missing. Run npm ci in the frontend directory now?")) {
            throw "Frontend dependencies are missing. No project data was changed."
        }
        $nodeDirectory = Split-Path -Parent $script:nodeExecutable
        $env:PATH = "$nodeDirectory;$env:PATH"
        Push-Location $frontend
        try {
            & $script:npmExecutable ci
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dependency installation failed. Check internet access and the npm output."
            }
        }
        finally {
            Pop-Location
        }
    }
    return $viteEntry
}

function Test-Url([string]$Url) {
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Start-TrackedProcess(
    [string]$Name,
    [string]$Executable,
    [string[]]$Arguments,
    [string]$WorkingDirectory,
    [string]$Marker,
    $State
) {
    $existing = Get-OwnedProcess $State[$Name]
    if ($null -ne $existing) {
        Write-Host "$Name is already running under this launcher (PID $($existing.Id))."
        return
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdout = Join-Path $logDirectory "$Name-$timestamp.out.log"
    $stderr = Join-Path $logDirectory "$Name-$timestamp.err.log"
    $process = Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    Start-Sleep -Milliseconds 500
    $process.Refresh()
    if ($process.HasExited) {
        throw "$Name exited during startup. Review its logs in $logDirectory."
    }

    $State[$Name] = @{
        process_id = $process.Id
        start_ticks = $process.StartTime.ToUniversalTime().Ticks
        executable = [IO.Path]::GetFullPath($Executable)
        marker = $Marker
        stdout = $stdout
        stderr = $stderr
    }
    Save-State $State
}

function Start-TheraSim {
    Assert-ProjectFiles
    Resolve-ProjectTools
    if (-not $script:nodeExecutable -or -not $script:npmExecutable) {
        Ensure-FrontendDependencies
    }

    $state = Read-State
    $ownedBackend = Get-OwnedProcess $state["backend"]
    $ownedFrontend = Get-OwnedProcess $state["frontend"]
    if ($null -ne $ownedBackend -and $null -ne $ownedFrontend) {
        Write-Host "TheraSim is already running."
        if ($env:THERASIM_NO_BROWSER -ne "1") {
            Start-Process $frontendUrl
        }
        return
    }

    if ($null -eq $ownedBackend -and (Test-Url $backendUrl)) {
        throw "An API already responds at 127.0.0.1:8000 but is not owned by this launcher. It was left untouched."
    }
    if ($null -eq $ownedFrontend -and (Test-Url $frontendUrl)) {
        throw "A web server already responds at 127.0.0.1:5173 but is not owned by this launcher. It was left untouched."
    }

    Ensure-PythonEnvironment
    $viteEntry = Ensure-FrontendDependencies

    if (-not (Test-Path -LiteralPath $logDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
    }

    if ($null -eq $ownedBackend) {
        Write-Host "Applying safe database migrations and seeding the default fictional case..."
        Push-Location $backend
        try {
            & $script:pythonExecutable -m app.persistence.cli
            if ($LASTEXITCODE -ne 0) {
                throw "Database initialization failed. Existing data was not reset; inspect the error above."
            }
        }
        finally {
            Pop-Location
        }
        Start-TrackedProcess `
            "backend" `
            $script:pythonExecutable `
            @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
            $backend `
            "app.main:app" `
            $state
    }

    if ($null -eq $ownedFrontend) {
        $viteArguments = @(
            "`"$viteEntry`"",
            "--host", "127.0.0.1",
            "--port", "5173",
            "--strictPort"
        )
        Start-TrackedProcess `
            "frontend" `
            $script:nodeExecutable `
            $viteArguments `
            $frontend `
            $viteEntry `
            $state
    }

    $backendReady = $false
    $frontendReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $backendProcess = Get-OwnedProcess $state["backend"]
        $frontendProcess = Get-OwnedProcess $state["frontend"]
        $backendReady = ($null -ne $backendProcess) -and (Test-Url $backendUrl)
        $frontendReady = ($null -ne $frontendProcess) -and (Test-Url $frontendUrl)
        if ($backendReady -and $frontendReady) {
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $backendReady -or -not $frontendReady) {
        Stop-OwnedProcess $state["frontend"] "Frontend"
        Stop-OwnedProcess $state["backend"] "Backend"
        throw "TheraSim did not become ready. Review backend/frontend logs in $logDirectory."
    }

    Write-Host "TheraSim is ready."
    Write-Host "Frontend: $frontendUrl"
    Write-Host "Backend API: http://127.0.0.1:8000/docs"
    Write-Host "Logs: $logDirectory"
    Write-Host "Run STOP_THERASIM.bat to stop only processes started by this launcher."
    if ($env:THERASIM_NO_BROWSER -ne "1") {
        Start-Process $frontendUrl
    }
}

function Stop-TheraSim {
    $state = Read-State
    $frontendStopped = Stop-OwnedProcess $state["frontend"] "Frontend"
    $backendStopped = Stop-OwnedProcess $state["backend"] "Backend"
    if ($frontendStopped -and $backendStopped -and
        (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        Remove-Item -LiteralPath $statePath -Force
    }
    elseif (-not $frontendStopped -or -not $backendStopped) {
        throw "One or more processes were not stopped because their identity could not be verified. The ownership record was preserved."
    }
}

function Check-TheraSim {
    Assert-ProjectFiles
    Resolve-ProjectTools
    $checks = @(
        @{ Name = "Python"; Ready = [bool]($script:pythonExecutable -or $script:systemPython -or $script:pythonLauncher); Detail = $script:pythonExecutable },
        @{ Name = "Node.js"; Ready = [bool]$script:nodeExecutable; Detail = $script:nodeExecutable },
        @{ Name = "npm"; Ready = [bool]$script:npmExecutable; Detail = $script:npmExecutable },
        @{ Name = "Backend environment"; Ready = [bool]$script:pythonExecutable; Detail = $script:pythonExecutable },
        @{ Name = "Frontend packages"; Ready = [bool](Test-Path -LiteralPath (Join-Path $frontend "node_modules\vite\bin\vite.js") -PathType Leaf); Detail = (Join-Path $frontend "node_modules\vite\bin\vite.js") }
    )
    $failed = $false
    foreach ($check in $checks) {
        $label = if ($check.Ready) { "OK" } else { "MISSING" }
        Write-Host ("{0,-20} {1} {2}" -f $check.Name, $label, $check.Detail)
        if (-not $check.Ready) {
            $failed = $true
        }
    }
    if ($failed) {
        throw "Some prerequisites or dependencies are missing. START_THERASIM.bat can offer safe project setup."
    }
    Write-Host "Project files and local development prerequisites are available."
}

try {
    switch ($Action) {
        "Start" { Start-TheraSim }
        "Stop" { Stop-TheraSim }
        "Check" { Check-TheraSim }
    }
}
catch {
    Write-Host "TheraSim $Action failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
