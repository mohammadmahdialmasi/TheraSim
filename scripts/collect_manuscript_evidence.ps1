param(
    [switch]$SkipBenchmarks,
    [switch]$SkipReleaseDownload,
    [switch]$SkipReleaseVerifier
)

$ErrorActionPreference = "Continue"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputRoot = Join-Path $repoRoot "artifacts\manuscript-evidence-$timestamp"
if (Test-Path -LiteralPath $outputRoot) {
    throw "Evidence directory already exists: $outputRoot"
}
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

$commandLog = Join-Path $outputRoot "commands.log"
$failures = [System.Collections.Generic.List[string]]::new()
$skipped = [System.Collections.Generic.List[string]]::new()
$completed = [System.Collections.Generic.List[string]]::new()
$tempWorktree = $null

function Protect-EvidenceText {
    param([AllowNull()][string]$Text)
    if ($null -eq $Text) { return "" }
    $redacted = [string]$Text
    $redacted = $redacted.Replace($repoRoot, "[REPOSITORY_ROOT]")
    $redacted = [regex]::Replace(
        $redacted,
        '(?i)C:\\Users\\[^\\\s]+',
        '[REDACTED_HOME]'
    )
    $redacted = [regex]::Replace(
        $redacted,
        '(?i)C:\\Users\\[^\\]+\\AppData\\Local\\Temp\\[^ \t\r\n""'']+',
        '[REDACTED_TEMP]'
    )
    $redacted = [regex]::Replace(
        $redacted,
        '(?i)[A-Z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}',
        '[REDACTED_EMAIL]'
    )
    $redacted = [regex]::Replace(
        $redacted,
        '(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|secret|client[_-]?secret)\b(\s*[=:]\s*)([^\s,;]+)',
        '${1}${2}[REDACTED_SECRET]'
    )
    return $redacted
}

function Write-Log {
    param([string]$Text)
    $line = "[{0}] {1}" -f (Get-Date -Format "o"), (Protect-EvidenceText $Text)
    Add-Content -LiteralPath $commandLog -Value $line -Encoding UTF8
}

function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $repoRoot,
        [switch]$Capture
    )
    $stdout = Join-Path $outputRoot ("{0}.stdout.txt" -f $Name)
    $stderr = Join-Path $outputRoot ("{0}.stderr.txt" -f $Name)
    $exitFile = Join-Path $outputRoot ("{0}.exitcode.txt" -f $Name)
    Write-Log ("COMMAND {0}: {1} {2}" -f $Name, $FilePath, ($ArgumentList -join " "))
    $oldLocation = Get-Location
    try {
        Set-Location $WorkingDirectory
        $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
            -WorkingDirectory $WorkingDirectory -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $exitCode = $process.ExitCode
    } catch {
        $exitCode = -1
        $message = $_.Exception.Message
        Set-Content -LiteralPath $stderr -Value $message -Encoding UTF8
    } finally {
        Set-Location $oldLocation
    }
    Set-Content -LiteralPath $exitFile -Value $exitCode -Encoding UTF8
    Write-Log ("COMMAND {0}: exit={1}" -f $Name, $exitCode)
    if ($exitCode -ne 0) {
        $failures.Add("$Name exit $exitCode")
    } else {
        $completed.Add($Name)
    }
    return @{ ExitCode = $exitCode; Stdout = $stdout; Stderr = $stderr }
}

function Get-TextDigest {
    param([string]$Text)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash = [System.Security.Cryptography.SHA256]::HashData($bytes)
    ([Convert]::ToHexString($hash)).ToLowerInvariant()
}

Write-Log "Evidence collection started"
Write-Log ("Repository: {0}" -f $repoRoot)

# Git provenance
$gitItems = [ordered]@{}
$gitItems.repository_root = "[REPOSITORY_ROOT]"
$gitItems.current_branch = (& git symbolic-ref --short HEAD 2>$null | Out-String).Trim()
$gitItems.head_sha = (& git rev-parse HEAD 2>$null | Out-String).Trim()
$gitItems.commit_message = (& git --no-pager log -1 --format=%s 2>$null | Out-String).Trim()
$gitItems.commit_date = (& git --no-pager log -1 --format=%cI 2>$null | Out-String).Trim()
$gitItems.git_version = (& git --version 2>$null | Out-String).Trim()
$gitItems.tag_commit = (& git rev-parse "v0.3.1^{commit}" 2>$null | Out-String).Trim()
$gitItems.tag_object = (& git rev-parse "v0.3.1" 2>$null | Out-String).Trim()
$gitItems.tag_type = (& git cat-file -t "v0.3.1" 2>$null | Out-String).Trim()
$gitItems.release_tree_sha = (& git rev-parse "v0.3.1^{tree}" 2>$null | Out-String).Trim()
$gitItems.parent_commit_sha = (& git rev-parse "v0.3.1^" 2>$null | Out-String).Trim()
$statusText = (& git --no-pager status --porcelain=v1 2>$null | Out-String)
$gitItems.working_tree_status = $statusText.Trim()
$gitItems.working_tree_clean = [string]::IsNullOrWhiteSpace($statusText)
$gitItems.expected_tag_commit = "e2b9a880e61cfaaefc69caca22212fc117739247"
$gitItems.tag_commit_verified = $gitItems.tag_commit -eq $gitItems.expected_tag_commit
$gitItems.tag_signed = $false
$tagVerify = (& git verify-tag v0.3.1 2>&1 | Out-String)
$gitItems.tag_signature_check = $tagVerify.Trim()
$gitItems.tag_signed = $tagVerify -match "Good signature|Signature made"
$gitItems.latest_release_commit_metadata = Protect-EvidenceText (
    (& git --no-pager show -s --format="%H%n%P%n%cI%n%an%n%ae%n%s" v0.3.1 2>$null | Out-String).Trim()
)
$gitItems | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot "git_provenance.json") -Encoding UTF8
Write-Log "Collected Git provenance"

$benchmarkDiff = Join-Path $outputRoot "git_diff_benchmark_to_release.txt"
$changedFiles = [System.Collections.Generic.List[object]]::new()
$diffFiles = @(
    "scripts/benchmark_agent_workflows.py",
    "backend/app/llm/patient_agent.py",
    "backend/app/llm/evaluator_agent.py",
    "backend/app/llm/client.py",
    "backend/app/services/evaluations.py",
    "config/model-compatibility.json",
    "rubrics/act/ACT_RUBRIC_V0.md",
    "rubrics/act/ACT_RUBRIC_V0.json"
)
$diffText = "Benchmark commit: d10339402fabe67622a6e5499d76dfb5ba797f07`nRelease commit: e2b9a880e61cfaaefc69caca22212fc117739247`n`n"
foreach ($file in $diffFiles) {
    $oldBlob = (& git rev-parse "d10339402fabe67622a6e5499d76dfb5ba797f07:$file" 2>$null | Out-String).Trim()
    $newBlob = (& git rev-parse "e2b9a880e61cfaaefc69caca22212fc117739247:$file" 2>$null | Out-String).Trim()
    $changed = ($oldBlob -ne $newBlob) -or [string]::IsNullOrWhiteSpace($oldBlob) -or [string]::IsNullOrWhiteSpace($newBlob)
    $changedFiles.Add([ordered]@{ file=$file; benchmark_blob=$oldBlob; release_blob=$newBlob; changed=$changed })
    $diffText += "FILE $file`nOld blob: $oldBlob`nNew blob: $newBlob`nChanged: $changed`n"
    $diffText += (& git --no-pager diff --stat d10339402fabe67622a6e5499d76dfb5ba797f07 e2b9a880e61cfaaefc69caca22212fc117739247 -- $file 2>$null | Out-String)
    $diffText += (& git --no-pager diff d10339402fabe67622a6e5499d76dfb5ba797f07 e2b9a880e61cfaaefc69caca22212fc117739247 -- $file 2>$null | Out-String)
    $diffText += "`n"
}
$diffText | Set-Content -LiteralPath $benchmarkDiff -Encoding UTF8
$changedFiles | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $outputRoot "benchmark_file_comparison.json") -Encoding UTF8

# Hardware and software environment
$envJson = [ordered]@{}
$envJson.windows = [ordered]@{
    caption = (& cmd /c wmic os get Caption /value 2>$null | Out-String).Trim()
    version = (& cmd /c wmic os get Version /value 2>$null | Out-String).Trim()
    build = (& cmd /c wmic os get BuildNumber /value 2>$null | Out-String).Trim()
    architecture = (& cmd /c wmic os get OSArchitecture /value 2>$null | Out-String).Trim()
}
$cpu = (& cmd /c wmic cpu get Name,NumberOfCores,NumberOfLogicalProcessors /value 2>$null | Out-String).Trim()
$ram = (& cmd /c wmic ComputerSystem get TotalPhysicalMemory /value 2>$null | Out-String).Trim()
$gpu = (& cmd /c wmic path win32_VideoController get Name,AdapterRAM /value 2>$null | Out-String).Trim()
$envJson.cpu = $cpu
$envJson.ram = $ram
$envJson.gpu = $gpu
$nvidiaSmi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
$envJson.nvidia_smi = if ($nvidiaSmi) { (& nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>$null | Out-String).Trim() } else { "Unavailable" }
$cudaExecutable = Get-Command nvcc -ErrorAction SilentlyContinue
$envJson.cuda = if ($cudaExecutable) { (& nvcc --version 2>$null | Out-String).Trim() } else { "Unavailable" }
$envJson.python_venv = (& .\.venv\Scripts\python.exe --version 2>$null | Out-String).Trim()
$envJson.git_version = $gitItems.git_version
$envJson.ollama_version = (& ollama --version 2>$null | Out-String).Trim()
$envJson.ollama_tags = (& ollama list 2>$null | Out-String).Trim()
$envJson.release_tag = "v0.3.1"
$envJson.release_commit = $gitItems.tag_commit
$benchmarkScript = Join-Path $repoRoot "scripts\benchmark_agent_workflows.py"
$envJson.benchmark_script_sha256 = (Get-FileHash -LiteralPath $benchmarkScript -Algorithm SHA256).Hash.ToLowerInvariant()
try {
    $packageVersions = (& .\.venv\Scripts\python.exe -c "import importlib.metadata as m; names=['fastapi','httpx','openai','pydantic','numpy','pandas']; print('\n'.join(f'{n}={m.version(n)}' for n in names if True))" 2>$null | Out-String).Trim()
} catch { $packageVersions = "Unavailable" }
$envJson.relevant_packages = $packageVersions
$envJson | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot "environment.json") -Encoding UTF8
$envMd = "# Environment`n`n" + ($envJson | ConvertTo-Json -Depth 8)
$envMd | Set-Content -LiteralPath (Join-Path $outputRoot "environment.md") -Encoding UTF8

# Ollama inventory
$modelInventory = [System.Collections.Generic.List[object]]::new()
$ollamaTagsText = (& ollama list 2>$null | Out-String)
$ollamaApi = $null
try { $ollamaApi = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 10 } catch { $ollamaApi = $null }
foreach ($tag in @("qwen2.5:3b","gemma-4-E2B:latest","Qwen3.5:9b")) {
    $show = (& ollama show $tag 2>&1 | Out-String)
    $showModelfile = (& ollama show $tag --modelfile 2>&1 | Out-String)
    $showParameters = (& ollama show $tag --parameters 2>&1 | Out-String)
    $showLicense = (& ollama show $tag --license 2>&1 | Out-String)
    $apiModel = $null
    if ($ollamaApi -and $ollamaApi.models) {
        $apiModel = $ollamaApi.models | Where-Object { $_.name -eq $tag } | Select-Object -First 1
    }
    $digests = [regex]::Matches($show, "(?i)\b[0-9a-f]{12,64}\b") | ForEach-Object { $_.Value }
    $modelInventory.Add([ordered]@{
        exact_local_tag=$tag
        installed=$showLicense -notmatch "not found|does not exist"
        ollama_show=$show.Trim()
        modelfile=$showModelfile.Trim()
        parameters=$showParameters.Trim()
        license_text=$showLicense.Trim()
        api_record=if ($apiModel) { $apiModel } else { $null }
    })
}
$modelInventory | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $outputRoot "model_inventory.json") -Encoding UTF8

# License evidence
$licenseReport = @"
# Model license verification

No legal advice. Official evidence follows. Local identity matching is exact only when a local digest can be established.

"@
foreach ($model in @(
    [ordered]@{Name="Qwen2.5";Tag="qwen2.5:3b";Url="https://ollama.com/library/qwen2.5:3b";Official="https://ollama.com/library/qwen2.5:3b"},
    [ordered]@{Name="Qwen3.5";Tag="Qwen3.5:9b";Url="https://ollama.com/library/qwen3.5:9b";Official="https://ollama.com/library/qwen3.5:9b"},
    [ordered]@{Name="Gemma 4";Tag="gemma-4-E2B:latest";Url="https://ollama.com/library/gemma4:e2b";Official="https://ollama.com/library/gemma4:e2b"}
)) {
    $licenseText = "Official source could not be retrieved."
    try {
        $response = Invoke-WebRequest -Uri $model.Url -UseBasicParsing -TimeoutSec 30
        $licenseText = $response.Content
        $licenseText = $licenseText -replace "<[^>]+>", " "
        $licenseText = ($licenseText -replace "\s+", " ").Trim()
        if ($licenseText.Length -gt 12000) { $licenseText = $licenseText.Substring(0,12000) }
    } catch {
        $failures.Add("License fetch $($model.Name): $($_.Exception.Message)")
    }
    $licenseReport += "## $($model.Name)`n`n"
    $licenseReport += "- Exact local tag: ``$($model.Tag)```n"
    $licenseReport += "- Official registry URL: $($model.Official)`n"
    $licenseReport += "- Locally exposed license text: inspect model inventory and `ollama show ... --license`.`n"
    $licenseReport += "- Identity match: reported for comparison only; see local digest inventory.`n"
    $licenseReport += "- Official page evidence (normalized excerpt):`n`n$licenseText`n`n"
}
$licenseReport | Set-Content -LiteralPath (Join-Path $outputRoot "model_licenses.md") -Encoding UTF8

# Detached worktree and benchmarks
$benchmarksDir = Join-Path $outputRoot "benchmarks"
New-Item -ItemType Directory -Path $benchmarksDir -Force | Out-Null
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$worktreeParent = Join-Path ([System.IO.Path]::GetTempPath()) ("TheraSim-evidence-" + [guid]::NewGuid().ToString("N"))
if (-not $SkipBenchmarks) {
    try {
        New-Item -ItemType Directory -Path $worktreeParent -Force | Out-Null
        Remove-Item -LiteralPath $worktreeParent -Force
        $add = Invoke-Logged -Name "git_worktree_add_v0.3.1" -FilePath "git.exe" -ArgumentList @("worktree","add","--detach",$worktreeParent,"v0.3.1")
        if ($add.ExitCode -eq 0) { $tempWorktree = $worktreeParent } else { $skipped.Add("benchmark worktree") }
    } catch {
        $failures.Add("worktree creation: $($_.Exception.Message)")
        $skipped.Add("benchmark worktree")
    }
}
if ($tempWorktree) {
    $modelRuns = @(
        @{ Tag="qwen2.5:3b"; File="qwen2.5-3b"; Repeats=3 },
        @{ Tag="gemma-4-E2B:latest"; File="gemma-4-E2B-latest"; Repeats=3 },
        @{ Tag="Qwen3.5:9b"; File="qwen3.5-9b"; Repeats=1 }
    )
    foreach ($run in $modelRuns) {
        $list = (& ollama list 2>$null | Out-String)
        if ($list -notmatch [regex]::Escape($run.Tag)) {
            $skipped.Add("benchmark $($run.Tag): exact tag unavailable")
            continue
        }
        $before = (& ollama show $run.Tag 2>&1 | Out-String)
        $jsonOut = Join-Path $benchmarksDir ($run.File + ".json")
        $logOut = Join-Path $benchmarksDir ($run.File + ".log")
        $args = @(
            "scripts\benchmark_agent_workflows.py",
            "--model",$run.Tag,
            "--base-url","http://127.0.0.1:11434/v1",
            "--repeats",$run.Repeats.ToString(),
            "--timeout","600",
            "--output",$jsonOut
        )
        $cmdLine = ".venv\Scripts\python.exe " + (($args | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join " ")
        Set-Content -LiteralPath $logOut -Value ("Git commit: {0}`nModel before:`n{1}`nCommand: {2}`n" -f $gitItems.tag_commit,$before.Trim(),$cmdLine) -Encoding UTF8
        $result = Invoke-Logged -Name ("benchmark_" + $run.File) -FilePath $venvPython `
            -ArgumentList $args -WorkingDirectory $tempWorktree
        $after = (& ollama show $run.Tag 2>&1 | Out-String)
        Add-Content -LiteralPath $logOut -Value ("Model after:`n{0}`nExit code: {1}`n" -f $after.Trim(),$result.ExitCode) -Encoding UTF8
        Get-Content -LiteralPath $result.Stdout -ErrorAction SilentlyContinue | Add-Content -LiteralPath $logOut -Encoding UTF8
        Get-Content -LiteralPath $result.Stderr -ErrorAction SilentlyContinue | Add-Content -LiteralPath $logOut -Encoding UTF8
    }
}

# Release asset
$releaseJson = [ordered]@{
    release_api_url="https://api.github.com/repos/mohammadmahdialmasi/TheraSim/releases/tags/v0.3.1"
}
$assetZip = Join-Path $outputRoot "release_asset.zip"
if (-not $SkipReleaseDownload) {
    try {
        $release = Invoke-RestMethod -Uri $releaseJson.release_api_url -TimeoutSec 30
        $releaseJson.tag_name = $release.tag_name
        $releaseJson.target_commitish = $release.target_commitish
        $asset = $release.assets | Where-Object { $_.name -eq "TheraSim-v0.3.1-Windows-x64-Portable.zip" } | Select-Object -First 1
        if ($asset) {
            $releaseJson.asset_id = $asset.id
            $releaseJson.asset_url = $asset.url
            $releaseJson.browser_download_url = $asset.browser_download_url
            $releaseJson.declared_size = $asset.size
            $releaseJson.declared_digest = $asset.digest
            $releaseJson.created_at = $asset.created_at
            $releaseJson.updated_at = $asset.updated_at
            Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $assetZip -Headers @{Accept="application/octet-stream"} -TimeoutSec 120
            $releaseJson.local_sha256 = (Get-FileHash -LiteralPath $assetZip -Algorithm SHA256).Hash.ToLowerInvariant()
            $releaseJson.local_size = (Get-Item -LiteralPath $assetZip).Length
            $releaseJson.documented_audit_sha256 = "df1be242f0040b67b9b15ad7e7d7f52e136ed260f690f79370716200d9715319"
            $releaseJson.documented_audit_size = 26345293
            $releaseJson.matches_declared_digest = $releaseJson.local_sha256 -eq (($asset.digest -replace "^sha256:",""))
            $releaseJson.matches_documented_audit = $releaseJson.local_sha256 -eq $releaseJson.documented_audit_sha256
        } else {
            $releaseJson.error = "Expected asset was not found"
            $failures.Add("Release asset not found")
        }
    } catch {
        $releaseJson.error = $_.Exception.Message
        $failures.Add("Release download: $($_.Exception.Message)")
    }
}

if (Test-Path -LiteralPath $assetZip) {
    $entries = [System.Collections.Generic.List[object]]::new()
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($assetZip)
    try {
        foreach ($entry in $zip.Entries) {
            $entries.Add([ordered]@{
                name=$entry.FullName
                length=$entry.Length
                parent_traversal=(($entry.FullName -match "\.\.(?:/|\\)") -or ($entry.FullName -match "^[A-Za-z]:"))
            })
        }
        $names = $entries | ForEach-Object { $_.name }
        $releaseJson.archive = [ordered]@{
            entry_count=$entries.Count
            top_level_directories=@($names | ForEach-Object { ($_ -split "[/\\]")[0] } | Sort-Object -Unique)
            sql_migrations=@($names | Where-Object { $_ -match "(?i)\.sql$" })
            databases=@($names | Where-Object { $_ -match "(?i)\.(db|sqlite|sqlite3)$" })
            backups=@($names | Where-Object { $_ -match "(?i)\.(bak|backup|old)$" })
            env_files=@($names | Where-Object { ($_ -match "(?i)(^|/)\.env($|\.)") })
            provider_settings=@($names | Where-Object { $_ -match "(?i)(provider|settings|config)" })
            model_weights=@($names | Where-Object { $_ -match "(?i)\.(gguf|safetensors|bin|pt|pth|onnx)$" })
            absolute_or_parent_traversal=@($entries | Where-Object { $_.parent_traversal } | ForEach-Object { $_.name })
            unexpected_api_or_credentials=@($names | Where-Object { $_ -match "(?i)(api[_-]?key|credential|secret|token)" })
        }
    } finally { $zip.Dispose() }
}
$releaseJson | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $outputRoot "release_asset_verification.json") -Encoding UTF8
$releaseMd = "# Release asset verification`n`n" + ($releaseJson | ConvertTo-Json -Depth 12)
$releaseMd | Set-Content -LiteralPath (Join-Path $outputRoot "release_asset_verification.md") -Encoding UTF8

# Normal package verifier
$verifierJson = [ordered]@{ ollama_synthetic_chat_included=$false; verdict="not_run" }
if (-not $SkipReleaseVerifier -and (Test-Path -LiteralPath $assetZip)) {
    $verifierLog = Join-Path $outputRoot "release_verifier.log"
    $verifyArgs = @("-NoProfile","-ExecutionPolicy","Bypass","-File",(Join-Path $repoRoot "scripts\verify-windows-package.ps1"),"-PackageZip",$assetZip)
    $verifier = Invoke-Logged -Name "verify_windows_package" -FilePath "powershell.exe" -ArgumentList $verifyArgs
    if (Test-Path $verifier.Stdout) { Copy-Item $verifier.Stdout $verifierLog -Force }
    if (Test-Path $verifier.Stderr) { Add-Content -LiteralPath $verifierLog -Value ("`nSTDERR:`n" + (Get-Content $verifier.Stderr -Raw)) }
    $verifierJson.exit_code = $verifier.ExitCode
    $verifierJson.verdict = if ($verifier.ExitCode -eq 0) { "passed" } else { "failed" }
} else {
    $skipped.Add("release package verifier")
}
$releaseAssetJson = Get-Content -LiteralPath (Join-Path $outputRoot "release_asset_verification.json") -Raw | ConvertFrom-Json
$releaseAssetJson | Add-Member -NotePropertyName verifier -NotePropertyValue $verifierJson -Force
$releaseAssetJson | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $outputRoot "release_asset_verification.json") -Encoding UTF8

# Claim audit and report skeleton
$claimText = @"
# Manuscript claim audit

This audit requires direct comparison of the collected evidence with the listed v0.3.1 documents.

## Files reviewed

- docs/REPOSITORY_AUDIT.md
- docs/SECURITY_AUDIT.md
- docs/LOCAL_AI_MODEL_EVALUATION.md
- docs/V0.3.0_FINAL_INTEGRATION_AUDIT.md
- config/model-compatibility.json
- rubrics/act/ACT_RUBRIC_V0.md
- LICENSE.md
- README.md

## Determination rules

- Claims remain correct only where supported by collected evidence.
- Claims tied to historical builds or prior package digests require qualification.
- Exact model-digest changes must be checked before retaining a recommendation.
- A successful downloaded-package test is reported only from the normal verifier result.

See MANUSCRIPT_EVIDENCE_REPORT.md for the evidence summary.
"@
$claimText | Set-Content -LiteralPath (Join-Path $outputRoot "manuscript_claim_audit.md") -Encoding UTF8

$report = @"
# TheraSim Manuscript Evidence Report

Generated: $timestamp
Repository: $repoRoot

## 1. Git provenance and exact commit

See git_provenance.json. The resolved tag commit must equal e2b9a880e61cfaaefc69caca22212fc117739247.

## 2. Benchmark source versus release commit

See git_diff_benchmark_to_release.txt and benchmark_file_comparison.json.

## 3. Hardware and software environment

See environment.json and environment.md.

## 4. Exact model tags and digests

See model_inventory.json and model_licenses.md.

## 5. Model license findings

See model_licenses.md. Official evidence requires manual confirmation before publication.

## 6. Repeated PatientAgent benchmark results

See benchmarks/*.json and benchmarks/*.log.

## 7. Repeated EvaluatorAgent benchmark results

See benchmarks/*.json and benchmarks/*.log.

## 8. Validation failure categories

The raw benchmark JSON contains error_type and application validation errors.

## 9-12. Published and documented package digests

See release_asset_verification.json and release_asset_verification.md.

## 13. Security and privacy limitations

No real patient data was used. Raw patient/client responses and repository databases are excluded. Package inspection is limited to the downloaded archive and normal verifier behavior.

## 14. Manuscript claims

See manuscript_claim_audit.md.

## 15. Missing evidence preventing a strong reproducibility claim

Missing or unresolved items are listed below rather than inferred.

## 16. Proposed concise Methods paragraph

Evidence for this section must be populated only from recorded environment, Git, benchmark, and package outputs.

## 17. Proposed concise Results paragraph

Evidence for this section must be populated only from recorded benchmark and package outputs.

## 18. Author manual confirmations

- Confirm official model-card/license terms and exact upstream identity.
- Confirm package digest and verifier result.
- Confirm whether historical manuscript claims refer to the exact benchmark and package builds.

## Evidence limitations and unresolved questions

- The exact upstream license match is uncertain unless the local digest is explicitly tied to official model-card identity.
- Benchmark runs are limited to this workstation and synthetic cases.
- Release package provenance and contents require the downloaded asset's API and verifier evidence.
"@
$report | Set-Content -LiteralPath (Join-Path $outputRoot "MANUSCRIPT_EVIDENCE_REPORT.md") -Encoding UTF8

# Remove the temporary worktree only if this script created it
if ($tempWorktree) {
    $remove = Invoke-Logged -Name "git_worktree_remove_v0.3.1" -FilePath "git.exe" -ArgumentList @("worktree","remove","--force",$tempWorktree)
    try { if (Test-Path $tempWorktree) { Remove-Item -LiteralPath $tempWorktree -Recurse -Force } } catch {}
}

# Package all evidence
$readme = @"
# Evidence package contents

- MANUSCRIPT_EVIDENCE_REPORT.md: author-facing evidence summary.
- environment.json / environment.md: hardware and software inventory.
- git_provenance.json: exact Git and tag provenance.
- git_diff_benchmark_to_release.txt: file-level benchmark-to-release comparison.
- benchmark_file_comparison.json: blob-level file comparison.
- model_inventory.json: local Ollama model inventory.
- model_licenses.md: official-license evidence and uncertainties.
- manuscript_claim_audit.md: claim review template and determinations.
- release_asset_verification.json / release_asset_verification.md: official ZIP evidence.
- benchmarks/: raw benchmark JSON and command logs.
- *.stdout.txt, *.stderr.txt, *.exitcode.txt, commands.log: command evidence.
- release_asset.zip: downloaded official release asset, if successful.
"@
$readme | Set-Content -LiteralPath (Join-Path $outputRoot "README.md") -Encoding UTF8

$sanitizedRoot = $outputRoot + "-sanitized"
$privacyAudit = Invoke-Logged -Name "create_sanitized_evidence_export" `
    -FilePath $venvPython `
    -ArgumentList @(
        (Join-Path $repoRoot "scripts\evidence_redaction.py"),
        "--raw-directory",$outputRoot,
        "--sanitized-directory",$sanitizedRoot,
        "--repository-root",$repoRoot
    )

$packageName = "TheraSim_Manuscript_Evidence_$timestamp.zip"
$packagePath = Join-Path $repoRoot "artifacts\$packageName"
Compress-Archive -Path (Join-Path $sanitizedRoot "*") -DestinationPath $packagePath -CompressionLevel Optimal
$packageHash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
$packageSize = (Get-Item -LiteralPath $packagePath).Length

$summary = [ordered]@{
    zip_full_path=$packagePath
    zip_size_bytes=$packageSize
    zip_sha256=$packageHash
    report_full_path=(Join-Path $outputRoot "MANUSCRIPT_EVIDENCE_REPORT.md")
    completed=@($completed)
    skipped=@($skipped)
    failures=@($failures)
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot "collection_summary.json") -Encoding UTF8

Write-Log ("Evidence package: {0}" -f $packagePath)
Write-Output ""
Write-Output ("Full path to the ZIP: {0}" -f $packagePath)
Write-Output ("ZIP file size: {0} bytes" -f $packageSize)
Write-Output ("ZIP SHA-256: {0}" -f $packageHash)
Write-Output ("Full path to MANUSCRIPT_EVIDENCE_REPORT.md: {0}" -f (Join-Path $outputRoot "MANUSCRIPT_EVIDENCE_REPORT.md"))
Write-Output ("Summary of completed operations: {0}" -f ($completed -join "; "))
Write-Output ("Summary of skipped operations: {0}" -f ($skipped -join "; "))
Write-Output ("Failures/blockers: {0}" -f ($failures -join "; "))
