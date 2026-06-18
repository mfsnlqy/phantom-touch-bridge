param(
    [switch]$Clean,
    [switch]$UseLocalBuildTools
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repoSrcPath = Join-Path $repoRoot "src"
$pyInstallerRunner = Join-Path $PSScriptRoot "run_pyinstaller.py"
$entryPoint = Join-Path $repoRoot "src\intiface_bridge\__main__.py"
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$buildDistRoot = Join-Path $buildRoot "dist"
$packageRoot = Join-Path $distRoot "phantom-touch-bridge-windows"
$exePath = Join-Path $buildDistRoot "phantom-touch-bridge.exe"
$legacyExePath = Join-Path $distRoot "phantom-touch-bridge.exe"
$localBuildTools = Join-Path $repoRoot ".build-tools"
$pyInstallerWorkRoot = Join-Path $buildRoot "pyinstaller"
$previousPythonPath = $env:PYTHONPATH

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

if (-not (Test-Path $pyInstallerRunner)) {
    throw "PyInstaller runner not found: $pyInstallerRunner"
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
    $repoSrcPath,
    "--collect-all",
    "fastapi",
    "--collect-all",
    "starlette",
    "--collect-all",
    "uvicorn",
    $entryPoint
)

try {
    if ($UseLocalBuildTools) {
        if (-not (Test-Path $localBuildTools)) {
            throw "Local build tools were requested, but .build-tools was not found at $localBuildTools"
        }
        Write-Host "[phantom-touch-bridge] Using explicit local build tools from $localBuildTools"
        $env:PYTHONPATH = "$localBuildTools;$repoSrcPath"
        $env:PHANTOM_TOUCH_BRIDGE_BUILD_EXTRA_PATHS = $localBuildTools
    } else {
        Write-Host "[phantom-touch-bridge] Using Python 3.12 environment build tools"
        $env:PYTHONPATH = $repoSrcPath
        Remove-Item Env:PHANTOM_TOUCH_BRIDGE_BUILD_EXTRA_PATHS -ErrorAction SilentlyContinue
    }

    Write-Host "[phantom-touch-bridge] Isolated PYTHONPATH: $env:PYTHONPATH"

    if ($UseLocalBuildTools) {
        & py -3.12 -m PyInstaller --version | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "Local PyInstaller version probe failed with exit code $LASTEXITCODE."
        }
        & py -3.12 $pyInstallerRunner @pyInstallerCommonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Local PyInstaller build failed with exit code $LASTEXITCODE."
        }
    } else {
        & py -3.12 -m PyInstaller --version | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw 'PyInstaller is not available for Python 3.12. Run: py -3.12 -m pip install -e .[build]'
        }
        & py -3.12 $pyInstallerRunner @pyInstallerCommonArgs
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller build failed with exit code $LASTEXITCODE."
        }
    }
} finally {
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPATH = $previousPythonPath
    }
    Remove-Item Env:PHANTOM_TOUCH_BRIDGE_BUILD_EXTRA_PATHS -ErrorAction SilentlyContinue
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
Copy-Item (Join-Path $repoRoot "LICENSE") -Destination $packageRoot -Force
if (Test-Path $legacyExePath) {
    Remove-Item -Force $legacyExePath
}

Write-Host "[phantom-touch-bridge] Build complete."
Write-Host "[phantom-touch-bridge] Portable output:"
Write-Host "  $packageRoot"
