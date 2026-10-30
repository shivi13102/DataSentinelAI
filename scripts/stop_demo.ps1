$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$statePath = Join-Path $projectRoot '.demo-runtime\processes.json'
$expectedBackend = Join-Path $projectRoot '.venv\Scripts\python.exe'
$expectedViteScript = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$expectedFrontend = if ($nodeCommand) { $nodeCommand.Source } else { '' }

if (!(Test-Path -LiteralPath $statePath)) {
    Write-Output 'No DataSentinel processes started by start_demo.ps1 are recorded.'
    return
}

try {
    $records = @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
} catch {
    throw "The demo process-state file is unreadable: $statePath. Inspect it; no process was stopped."
}

$remaining = @()
foreach ($record in $records) {
    $processId = 0
    if (-not [int]::TryParse([string]$record.process_id, [ref]$processId) -or $processId -le 0) {
        Write-Warning "Ignoring invalid stored process ID for '$($record.role)'."
        continue
    }

    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Write-Output "[INFO] $($record.role) process $processId is already stopped."
        continue
    }

    $expectedExecutable = [System.IO.Path]::GetFullPath([string]$record.executable)
    $expectedCommand = if ($record.role -eq 'backend') {
        'uvicorn api:app'
    } elseif ($record.role -eq 'frontend') {
        'node_modules\vite\bin\vite.js'
    } else {
        ''
    }
    $expectedRoleExecutable = if ($record.role -eq 'backend') {
        $expectedBackend
    } elseif ($record.role -eq 'frontend') {
        $expectedFrontend
    } else {
        ''
    }
    if (
        !$expectedRoleExecutable -or
        !$expectedCommand -or
        ![string]::Equals(
            $expectedExecutable,
            [System.IO.Path]::GetFullPath($expectedRoleExecutable),
            [System.StringComparison]::OrdinalIgnoreCase
        ) -or
        ![string]::Equals(
            [string]$record.expected_command,
            $expectedCommand,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        Write-Warning "Stored process record for '$($record.role)' does not match the known demo launch commands; leaving it untouched."
        $remaining += $record
        continue
    }

    $actualExecutable = [string]$process.Path
    $matchesExecutable = [string]::Equals(
        $expectedExecutable,
        $actualExecutable,
        [System.StringComparison]::OrdinalIgnoreCase
    )
    $actualStartedAt = [DateTimeOffset]$process.StartTime.ToUniversalTime()
    $recordedStartedAt = [DateTimeOffset]::Parse([string]$record.started_at)
    $matchesStartTime = [Math]::Abs(
        ($actualStartedAt - $recordedStartedAt).TotalMilliseconds
    ) -lt 1000
    $matchesCommand = $true
    try {
        $processDetails = Get-CimInstance Win32_Process `
            -Filter "ProcessId = $processId" `
            -ErrorAction Stop
        if ($null -ne $processDetails) {
            $matchesCommand = ([string]$processDetails.CommandLine).IndexOf(
                [string]$record.expected_command,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -ge 0
        }
    } catch {
        Write-Warning "Could not read the command line for process $processId; verifying executable and exact start time instead."
    }

    if (-not ($matchesExecutable -and $matchesStartTime -and $matchesCommand)) {
        Write-Warning "Process ID $processId no longer matches the recorded DataSentinel command; leaving it untouched."
        $remaining += $record
        continue
    }

    Stop-Process -Id $processId -Force
    Write-Output "[PASS] Stopped DataSentinel $($record.role) process $processId."
}

if ($remaining.Count -gt 0) {
    $remaining | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statePath -Encoding UTF8
} else {
    Remove-Item -LiteralPath $statePath -Force
}

Write-Output 'Only matching processes recorded by start_demo.ps1 were stopped.'
