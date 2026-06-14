param(
    [switch]$Clean,
    [switch]$UseLocalBuildTools
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$entryPoint = Join-Path $repoRoot "src\intiface_bridge\__main__.py"
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$buildDistRoot = Join-Path $buildRoot "dist"
$packageRoot = Join-Path $distRoot "phantom-touch-bridge-windows"
$exePath = Join-Path $buildDistRoot "phantom-touch-bridge.exe"
$legacyExePath = Join-Path $distRoot "phantom-touch-bridge.exe"
$localBuildTools = Join-Path $repoRoot ".build-tools"
$pyInstallerWorkRoot = Join-Path $buildRoot "pyinstaller"

if ($Clean) {
    if (Test-Path $buildRoot) {
        Remove-Item -Recurse -Force $buildRoot
    }
    if (Test-Path $packageRoot) {
        Remove-Item -Recurse -Force $packageRoot
    }
    if (Test-Path $legacyExePath) {
        Remove-Item -Force $legacyExePath
    }
}

if (-not (Test-Path $entryPoint)) {
    throw "Entry point not found: $entryPoint"
}

Write-Host "[phantom-touch-bridge] Building Windows executable..."

$pyInstallerCommonArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name",
    "phantom-touch-bridge",
    "--distpath",
    $buildDistRoot,
    "--workpath",
    $pyInstallerWorkRoot,
    "--specpath",
    $buildRoot,
    "--paths",
    (Join-Path $repoRoot "src"),
    "--collect-all",
    "fastapi",
    "--collect-all",
    "starlette",
    "--collect-all",
    "uvicorn",
    $entryPoint
)

if ($UseLocalBuildTools) {
    if (-not (Test-Path $localBuildTools)) {
        throw "Local build tools were requested, but .build-tools was not found at $localBuildTools"
    }
    Write-Host "[phantom-touch-bridge] Using explicit local build tools from $localBuildTools"
    $previousPythonPath = $env:PYTHONPATH
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        $env:PYTHONPATH = $localBuildTools
    } else {
        $env:PYTHONPATH = "$localBuildTools;$previousPythonPath"
    }
    try {
        & py -3.12 -m PyInstaller --version | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Local PyInstaller version probe failed with exit code $LASTEXITCODE."
        }
        & py -3.12 -m PyInstaller @pyInstallerCommonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Local PyInstaller build failed with exit code $LASTEXITCODE."
        }
    } finally {
        $env:PYTHONPATH = $previousPythonPath
    }
} else {
    Write-Host "[phantom-touch-bridge] Using Python 3.12 environment build tools"
    & py -3.12 -m PyInstaller --version | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw 'PyInstaller is not available for Python 3.12. Run: py -3.12 -m pip install -e .[build]'
    }
    & py -3.12 -m PyInstaller @pyInstallerCommonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path $exePath)) {
    throw "Expected executable was not produced: $exePath"
}

if (Test-Path $packageRoot) {
    Remove-Item -Recurse -Force $packageRoot
}

New-Item -ItemType Directory -Path $packageRoot | Out-Null
Copy-Item $exePath -Destination (Join-Path $packageRoot "phantom-touch-bridge.exe") -Force
Copy-Item (Join-Path $repoRoot "start-server.bat") -Destination $packageRoot -Force
Copy-Item (Join-Path $repoRoot "phantom_touch_bridge.example.toml") -Destination $packageRoot -Force
if (Test-Path $legacyExePath) {
    Remove-Item -Force $legacyExePath
}

Write-Host "[phantom-touch-bridge] Build complete."
Write-Host "[phantom-touch-bridge] Portable output:"
Write-Host "  $packageRoot"
