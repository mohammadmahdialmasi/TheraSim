[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackageZip,
    [int]$Port = 18765,
    [switch]$TestOllama,
    [string]$OllamaModel = "gemma-4-E2B:latest"
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

if (-not ("TheraSimConsoleControl" -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
public static class TheraSimConsoleControl
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct StartupInfo
    {
        public int cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public int dwX;
        public int dwY;
        public int dwXSize;
        public int dwYSize;
        public int dwXCountChars;
        public int dwYCountChars;
        public int dwFillAttribute;
        public int dwFlags;
        public short wShowWindow;
        public short cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public uint dwProcessId;
        public uint dwThreadId;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CreateProcess(
        string applicationName,
        StringBuilder commandLine,
        IntPtr processAttributes,
        IntPtr threadAttributes,
        bool inheritHandles,
        uint creationFlags,
        IntPtr environment,
        string currentDirectory,
        ref StartupInfo startupInfo,
        out ProcessInformation processInformation
    );

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool FreeConsole();

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool AttachConsole(uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetConsoleCtrlHandler(IntPtr handler, bool add);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool GenerateConsoleCtrlEvent(uint eventType, uint processGroupId);

    public static int StartInNewProcessGroup(string executable)
    {
        var startupInfo = new StartupInfo
        {
            cb = Marshal.SizeOf<StartupInfo>()
        };
        var commandLine = new StringBuilder("\"" + executable + "\"");
        if (!CreateProcess(
            executable,
            commandLine,
            IntPtr.Zero,
            IntPtr.Zero,
            false,
            0x00000200,
            IntPtr.Zero,
            System.IO.Path.GetDirectoryName(executable),
            ref startupInfo,
            out var processInformation))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        CloseHandle(processInformation.hThread);
        CloseHandle(processInformation.hProcess);
        return checked((int)processInformation.dwProcessId);
    }
}
"@
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
try {
    $migrationPrefix = "TheraSim/_internal/app/persistence/migrations/"
    $migrationEntries = @(
        $zip.Entries | Where-Object {
            ($_.FullName.Replace('\', '/').StartsWith($migrationPrefix)) -and
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
        $migrationEntries | ForEach-Object { $_.FullName.Replace('\', '/') } | Sort-Object
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
$environmentNames = @(
    "LOCALAPPDATA",
    "THERASIM_PORT",
    "THERASIM_OPEN_BROWSER",
    "THERASIM_LLM_PROVIDER",
    "THERASIM_LLM_TIMEOUT",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_API_KEY",
    "LM_STUDIO_BASE_URL",
    "LM_STUDIO_MODEL",
    "LM_STUDIO_API_KEY",
    "LLAMA_CPP_BASE_URL",
    "LLAMA_CPP_MODEL",
    "LLAMA_CPP_API_KEY",
    "CUSTOM_OPENAI_BASE_URL",
    "CUSTOM_OPENAI_MODEL",
    "CUSTOM_OPENAI_API_KEY",
    "PATH",
    "PYTHONHOME",
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "NODE_PATH",
    "NODE_OPTIONS",
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV"
)
$oldEnvironment = @{}
foreach ($name in $environmentNames) {
    $oldEnvironment[$name] = [Environment]::GetEnvironmentVariable(
        $name,
        "Process"
    )
}
$process = $null
function Wait-ForPackageHealth {
    param(
        [System.Diagnostics.Process]$Process,
        [string]$BaseUrl
    )

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($Process.HasExited) {
            throw "The packaged application exited during startup."
        }
        try {
            $health = Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 2
            if ($health.status -eq "ok") {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "The packaged health endpoint did not become ready."
}

function Stop-PackageGracefully {
    param([System.Diagnostics.Process]$Process)

    try {
        if (
            -not [TheraSimConsoleControl]::SetConsoleCtrlHandler(
                [IntPtr]::Zero,
                $true
            )
        ) {
            throw "Could not protect the smoke-test controller from Ctrl+C."
        }
        if (
            -not [TheraSimConsoleControl]::GenerateConsoleCtrlEvent(
                1,
                [uint32]$Process.Id
            )
        ) {
            throw "Could not send Ctrl+Break to the packaged process group."
        }
        if (-not $Process.WaitForExit(10000)) {
            throw "The packaged process did not shut down gracefully."
        }
    } finally {
        [void][TheraSimConsoleControl]::SetConsoleCtrlHandler(
            [IntPtr]::Zero,
            $false
        )
    }
}

function Start-PackageProcess {
    param([string]$Executable)

    $processId = [TheraSimConsoleControl]::StartInNewProcessGroup($Executable)
    return [System.Diagnostics.Process]::GetProcessById($processId)
}

try {
    $initialExtraction = Join-Path $scratch "initial"
    Expand-Archive -LiteralPath $archive -DestinationPath $initialExtraction
    $exe = Join-Path $initialExtraction "TheraSim\TheraSim.exe"
    if (-not (Test-Path $exe)) {
        throw "The archive does not contain TheraSim\TheraSim.exe."
    }

    $env:LOCALAPPDATA = Join-Path $scratch "synthetic-user"
    $env:THERASIM_PORT = "$Port"
    $env:THERASIM_OPEN_BROWSER = "0"
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    foreach ($name in @(
        "THERASIM_LLM_PROVIDER",
        "THERASIM_LLM_TIMEOUT",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "OLLAMA_API_KEY",
        "LM_STUDIO_BASE_URL",
        "LM_STUDIO_MODEL",
        "LM_STUDIO_API_KEY",
        "LLAMA_CPP_BASE_URL",
        "LLAMA_CPP_MODEL",
        "LLAMA_CPP_API_KEY",
        "CUSTOM_OPENAI_BASE_URL",
        "CUSTOM_OPENAI_MODEL",
        "CUSTOM_OPENAI_API_KEY",
        "PYTHONHOME",
        "PYTHONPATH",
        "VIRTUAL_ENV",
        "NODE_PATH",
        "NODE_OPTIONS",
        "CONDA_PREFIX",
        "CONDA_DEFAULT_ENV"
    )) {
        Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
    }

    if ($TestOllama) {
        $ollamaModels = Invoke-RestMethod `
            -Uri "http://127.0.0.1:11434/api/tags" `
            -TimeoutSec 5
        if (-not ($ollamaModels.models | Where-Object { $_.name -eq $OllamaModel })) {
            throw "The requested Ollama model is not installed: $OllamaModel"
        }

        $configDir = Join-Path $env:LOCALAPPDATA "TheraSim"
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
        @(
            "THERASIM_LLM_PROVIDER=ollama"
            "OLLAMA_BASE_URL=http://127.0.0.1:11434/v1"
            "OLLAMA_MODEL=$OllamaModel"
        ) | Set-Content -LiteralPath (Join-Path $configDir "config.env") -Encoding ascii
    }

    $process = Start-PackageProcess -Executable $exe
    $base = "http://127.0.0.1:$Port"
    Wait-ForPackageHealth -Process $process -BaseUrl $base

    $page = Invoke-WebRequest -Uri "$base/" -TimeoutSec 5 -UseBasicParsing
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
    $authHeaders = @{
        Authorization = "Bearer $($created.data.access_token)"
    }

    if ($TestOllama) {
        $connection = Invoke-RestMethod `
            -Uri "$base/api/v1/llm/providers/ollama/test" `
            -Method Post `
            -Headers $authHeaders `
            -ContentType "application/json" `
            -Body (@{
                base_url = "http://127.0.0.1:11434/v1"
                model = $OllamaModel
            } | ConvertTo-Json) `
            -TimeoutSec 180
        if (-not $connection.success -or -not $connection.model_available) {
            throw "Packaged Ollama connection test failed: $($connection.status)"
        }

        $chat = Invoke-RestMethod `
            -Uri "$base/api/v1/llm/chat" `
            -Method Post `
            -Headers $authHeaders `
            -ContentType "application/json" `
            -Body (@{
                provider = "ollama"
                model = $OllamaModel
                temperature = 0
                max_tokens = 1024
                messages = @(@{
                    role = "user"
                    content = "In one short sentence, answer as a fictional person who hesitates to ask a coworker for help."
                })
            } | ConvertTo-Json -Depth 5) `
            -TimeoutSec 180
        if ([string]::IsNullOrWhiteSpace($chat.message.content)) {
            throw "The packaged synthetic Ollama chat returned no content."
        }
        Write-Output "PASS: package connected to local Ollama and completed one synthetic chat using $OllamaModel."
    }

    $dataPath = Join-Path $env:LOCALAPPDATA "TheraSim\data"
    if (-not (Test-Path (Join-Path $dataPath "therasim.db"))) {
        throw "The application did not create its isolated local database."
    }

    $firstProcessId = $process.Id
    Stop-PackageGracefully -Process $process
    $process.Refresh()
    if (-not $process.HasExited) {
        throw "The packaged process remained active after the console break signal."
    }
    $process = $null
    if (Get-Process -Id $firstProcessId -ErrorAction SilentlyContinue) {
        throw "The packaged process did not stop."
    }
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "The packaged process left a listener after it stopped."
    }

    $replacementExtraction = Join-Path $scratch "replacement"
    Expand-Archive -LiteralPath $archive -DestinationPath $replacementExtraction
    $replacementExe = Join-Path $replacementExtraction "TheraSim\TheraSim.exe"
    if (-not (Test-Path -LiteralPath $replacementExe -PathType Leaf)) {
        throw "The replacement extraction does not contain TheraSim.exe."
    }

    $process = Start-PackageProcess -Executable $replacementExe
    Wait-ForPackageHealth -Process $process -BaseUrl $base
    $authStatus = Invoke-RestMethod -Uri "$base/api/v1/auth/status" -TimeoutSec 5
    if (-not $authStatus.data.initialized) {
        throw "Synthetic account initialization did not survive application restart."
    }

    $lastProcessId = $process.Id
    Stop-PackageGracefully -Process $process
    $process.Refresh()
    if (-not $process.HasExited) {
        throw "The restarted packaged process remained active after the console break signal."
    }
    $process = $null
    if (
        (Get-Process -Id $lastProcessId -ErrorAction SilentlyContinue) -or
        (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    ) {
        throw "A packaged process or listener remained after smoke-test shutdown."
    }

    $shutdownLog = Join-Path $env:LOCALAPPDATA "TheraSim\logs\therasim.log"
    $shutdownMessages = 0
    if (Test-Path -LiteralPath $shutdownLog -PathType Leaf) {
        $logText = Get-Content -LiteralPath $shutdownLog -Raw
        $shutdownMessages = [regex]::Matches(
            $logText,
            "Application shutdown complete\."
        ).Count
    }
    if ($shutdownMessages -lt 2) {
        throw "The packaged server did not record both graceful shutdowns."
    }

    Write-Output "PASS: package starts with a system-only PATH, serves its UI, and preserves synthetic account initialization across restart and replacement-directory extraction."
    Write-Output "PASS: both package runs handled a targeted console-break signal and left no listener."
    Write-Output "No patient data or existing local SQLite content was read."
} finally {
    if ($process -and -not $process.HasExited) {
        # Stop only the process started by this smoke test.
        Stop-Process -Id $process.Id -Force
        Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable(
            $name,
            $oldEnvironment[$name],
            "Process"
        )
    }
    Remove-Item -LiteralPath $scratch -Recurse -Force -ErrorAction SilentlyContinue
}
