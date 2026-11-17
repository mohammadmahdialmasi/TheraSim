[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageZip,
    [int]$Port = 18765
)

$ErrorActionPreference = "Stop"
$archive = (Resolve-Path $PackageZip).Path
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$migrationRoot = Join-Path $projectRoot "backend\app\persistence\migrations"
$expectedMigrationEntries = @(
    foreach ($area in @("operational", "restricted")) {
        $sourceDirectory = Join-Path $migrationRoot $area
        if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
            throw "Required migration directory is missing: $area"
        }
        Get-ChildItem -LiteralPath $sourceDirectory -Filter "*.sql" -File |
            ForEach-Object {
                "TheraSim/_internal/app/persistence/migrations/$area/$($_.Name)"
            }
    }
) | Sort-Object

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
try {
    $migrationPrefix = "TheraSim/_internal/app/persistence/migrations/"
    $migrationEntries = @(
        $zip.Entries | Where-Object {
            $_.FullName.StartsWith($migrationPrefix) -and
            -not [string]::IsNullOrEmpty($_.Name)
        }
    )
    if ($migrationEntries.Count -eq 0) {
        throw "The package does not contain application SQL migrations."
    }
    if ($migrationEntries | Where-Object { $_.FullName -notmatch "\.sql$" }) {
        throw "The package contains a non-SQL file in its migration resources."
    }
    if ($zip.Entries | Where-Object { $_.FullName -match "(?i)\.bak$" }) {
        throw "The package contains an unintended backup file."
    }

    $actualMigrationEntries = @(
        $migrationEntries | ForEach-Object { $_.FullName } | Sort-Object
    )
    $migrationDifferences = @(
        Compare-Object `
            -ReferenceObject $expectedMigrationEntries `
            -DifferenceObject $actualMigrationEntries
    )
    if ($migrationDifferences.Count -gt 0) {
        throw "The package migration files do not match the source SQL whitelist."
    }
} finally {
    $zip.Dispose()
}

$scratch = Join-Path ([System.IO.Path]::GetTempPath()) "TheraSim-smoke-$PID"
New-Item -ItemType Directory -Path $scratch | Out-Null
$oldLocalAppData = $env:LOCALAPPDATA
$oldPort = $env:THERASIM_PORT
$process = $null

try {
    Expand-Archive -LiteralPath $archive -DestinationPath $scratch
    $exe = Join-Path $scratch "TheraSim\TheraSim.exe"
    if (-not (Test-Path $exe)) {
        throw "The archive does not contain TheraSim\TheraSim.exe."
    }

    $env:LOCALAPPDATA = Join-Path $scratch "synthetic-user"
    $env:THERASIM_PORT = "$Port"
    $process = Start-Process -FilePath $exe -PassThru
    $base = "http://127.0.0.1:$Port"
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($process.HasExited) {
            throw "The packaged application exited during startup."
        }
        try {
            $health = Invoke-RestMethod -Uri "$base/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        throw "The packaged health endpoint did not become ready."
    }

    $page = Invoke-WebRequest -Uri "$base/" -TimeoutSec 5
    if ($page.StatusCode -ne 200 -or $page.Content -notmatch "TheraSim") {
        throw "The packaged frontend did not load."
    }

    # Create one synthetic local account to exercise isolated persistence.
    $syntheticPassword = "Synthetic-" + [guid]::NewGuid().ToString("N") + "-Aa9!"
    $payload = @{
        reviewer_name = "Synthetic Release Smoke Test"
        password = $syntheticPassword
    } | ConvertTo-Json
    $created = Invoke-RestMethod `
        -Uri "$base/api/v1/auth/initialize" `
        -Method Post `
        -ContentType "application/json" `
        -Body $payload `
        -TimeoutSec 5
    if (-not $created.data.access_token) {
        throw "Synthetic account initialization did not return a local session."
    }

    $dataPath = Join-Path $env:LOCALAPPDATA "TheraSim\data"
    if (-not (Test-Path (Join-Path $dataPath "therasim.db"))) {
        throw "The application did not create its isolated local database."
    }
    Write-Output "PASS: package starts, serves its UI, and persists only to the temporary synthetic data directory."
    Write-Output "No patient data or existing local SQLite content was read."
} finally {
    if ($process -and -not $process.HasExited) {
        # Stop only the process started by this smoke test.
        Stop-Process -Id $process.Id -Force
        Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
    if ($null -eq $oldLocalAppData) {
        Remove-Item Env:\LOCALAPPDATA -ErrorAction SilentlyContinue
    } else {
        $env:LOCALAPPDATA = $oldLocalAppData
    }
    if ($null -eq $oldPort) {
        Remove-Item Env:\THERASIM_PORT -ErrorAction SilentlyContinue
    } else {
        $env:THERASIM_PORT = $oldPort
    }
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
