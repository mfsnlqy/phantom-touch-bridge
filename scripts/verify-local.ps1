$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$srcPath = Join-Path $repoRoot "src"
$healthUrl = "http://127.0.0.1:8877/healthz"

Set-Location $repoRoot

$env:PYTHONPATH = $srcPath

Write-Host "Repository root: $repoRoot"
Write-Host "PYTHONPATH: $env:PYTHONPATH"
Write-Host ""
Write-Host "Checking imported package path..."
py -3.12 -c "import intiface_bridge; print(intiface_bridge.__file__)"

Write-Host ""
Write-Host "Running pytest..."
py -3.12 -m pytest -q

Write-Host ""
Write-Host "Starting local health check..."
$env:INTIFACE_BRIDGE_BACKEND_TYPE = "custom"
$env:INTIFACE_BRIDGE_PORT = "8877"

$process = Start-Process `
    -FilePath "py" `
    -ArgumentList "-3.12", "-m", "intiface_bridge", "serve" `
    -WorkingDirectory $repoRoot `
    -PassThru

try {
    $ready = $false

    for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Milliseconds 500

        try {
            $response = Invoke-WebRequest -UseBasicParsing $healthUrl
            $payload = $response.Content | ConvertFrom-Json

            if ($payload.ok -ne $true) {
                throw "Health check returned unexpected payload: $($response.Content)"
            }

            $ready = $true
            Write-Host "Health check passed: $($response.Content)"
            break
        } catch {
            if ($process.HasExited) {
                throw "Local server exited before health check passed."
            }
        }
    }

    if (-not $ready) {
        throw "Timed out waiting for $healthUrl"
    }
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
    }
}

Write-Host ""
Write-Host "Local verification completed successfully."
