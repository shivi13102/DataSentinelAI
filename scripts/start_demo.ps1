$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backendPort = 8000
$frontendPort = 5173
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot = Join-Path $projectRoot 'frontend'
$vite = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'
$runtimeDir = Join-Path $projectRoot '.demo-runtime'
$statePath = Join-Path $runtimeDir 'processes.json'

if (!(Test-Path -LiteralPath (Join-Path $projectRoot 'api.py'))) {
    throw "DataSentinel API was not found under project root: $projectRoot"
}
if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Project virtual environment is missing. Create it and install requirements.txt first: $python"
}
if (!(Test-Path -LiteralPath $vite -PathType Leaf)) {
    throw "Frontend dependencies are missing. Run npm ci from $frontendRoot."
}

$importCheck = & $python -c "import api, uvicorn" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Backend dependency/import check failed:`n$($importCheck -join "`n")"
}
Write-Output '[PASS] Backend imports.'

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $runtimeDir 'logs') | Out-Null

$ownedProcesses = @()
if (Test-Path -LiteralPath $statePath) {
    try {
        $stored = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if ($null -ne $stored) {
            $ownedProcesses = @($stored)
        }
    } catch {
        throw "The demo process-state file is unreadable: $statePath. Inspect it before changing it."
    }
}

function Test-PortListening([int]$port) {
    return $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Wait-ForBackend([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod `
                -Uri 'http://127.0.0.1:8000/api/health' `
                -TimeoutSec 2
            if (
                $health.service -eq 'DataSentinel AI' -and
                $health.status -eq 'online' -and
                $health.analysis_engine_status -eq 'available'
            ) {
                return $health
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "DataSentinel backend health/analysis check did not pass within $seconds seconds."
}

function Wait-ForFrontend([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest `
                -Uri 'http://127.0.0.1:5173/' `
                -UseBasicParsing `
                -TimeoutSec 2
            if ($response.Content -match '<title>DataSentinel AI</title>') {
                return $response
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "DataSentinel frontend did not respond with its application page within $seconds seconds."
}

function Start-TrackedProcess(
    [string]$role,
    [string]$executable,
    [string[]]$arguments,
    [string]$workingDirectory,
    [string]$expectedCommand
) {
    $stdout = Join-Path $runtimeDir "logs\$role.out.log"
    $stderr = Join-Path $runtimeDir "logs\$role.err.log"
    $process = Start-Process `
        -FilePath $executable `
        -ArgumentList $arguments `
        -WorkingDirectory $workingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru

    $script:ownedProcesses += [pscustomobject]@{
        role = $role
        process_id = $process.Id
        executable = [System.IO.Path]::GetFullPath($executable)
        expected_command = $expectedCommand
        started_at = $process.StartTime.ToUniversalTime().ToString('o')
    }
    $script:ownedProcesses |
        ConvertTo-Json -Depth 4 |
        Set-Content -LiteralPath $statePath -Encoding UTF8
    return $process
}

if (Test-PortListening $backendPort) {
    try {
        $null = Wait-ForBackend 3
        Write-Output '[INFO] Backend and analysis engine are already healthy on 127.0.0.1:8000; leaving it untouched.'
    } catch {
        throw "Port $backendPort is occupied by a service that is not the DataSentinel API. No process was stopped."
    }
} else {
    $null = Start-TrackedProcess `
        'backend' `
        $python `
        @('-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', "$backendPort") `
        $projectRoot `
        'uvicorn api:app'
    $null = Wait-ForBackend 30
    Write-Output '[PASS] Backend started on 127.0.0.1:8000.'
}

if (Test-PortListening $frontendPort) {
    try {
        $null = Wait-ForFrontend 3
        Write-Output '[INFO] Frontend is already serving DataSentinel AI on 127.0.0.1:5173; leaving it untouched.'
    } catch {
        throw "Port $frontendPort is occupied by a service that is not responding as the frontend. No process was stopped."
    }
} else {
    $node = (Get-Command node.exe -ErrorAction Stop).Source
    $viteArgument = "`"$vite`""
    $null = Start-TrackedProcess `
        'frontend' `
        $node `
        @($viteArgument, '--host', '127.0.0.1', '--port', "$frontendPort", '--strictPort') `
        $frontendRoot `
        'node_modules\vite\bin\vite.js'
    $null = Wait-ForFrontend 30
    Write-Output '[PASS] Frontend started on 127.0.0.1:5173.'
}

Write-Output ''
Write-Output 'DataSentinel AI demo is available:'
Write-Output '  Frontend: http://127.0.0.1:5173'
Write-Output '  API:      http://127.0.0.1:8000'
Write-Output '  API docs: http://127.0.0.1:8000/docs'
Write-Output '  Stop:     powershell -ExecutionPolicy Bypass -File scripts\stop_demo.ps1'

try {
    $ai = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health/ai' -TimeoutSec 35
    if ($ai.status -eq 'AVAILABLE') {
        Write-Output "[PASS] Local AI inference verified: $($ai.model) ($($ai.response_time_ms) ms)."
    } else {
        Write-Output "[WARNING] AI status $($ai.status): $($ai.error)"
        Write-Output '          Deterministic analysis and protection remain available.'
    }
} catch {
    Write-Output '[WARNING] AI health check did not complete. Deterministic analysis and protection remain available.'
}
