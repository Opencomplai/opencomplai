<#
.SYNOPSIS
Install the opencomplai CLI with uv and a uv-managed Python.

.DESCRIPTION
Wraps `uv tool install`, so no Python has to be installed beforehand. The
interpreter is requested from uv (default 3.11, the minimum the packages
support). Only PyPI packages are downloaded; nothing is sent anywhere.
The script does not edit the user PATH or the registry.

Environment: OPENCOMPLAI_PYTHON (default for -Python), OPENCOMPLAI_SPEC
(package to install, default opencomplai), OPENCOMPLAI_FIND_LINKS (directory
of local wheels to prefer, used by CI).

.PARAMETER InstallUv
If uv is missing, run the official uv installer (https://astral.sh/uv/install.ps1) first.

.PARAMETER Python
Interpreter to request from uv (default: $env:OPENCOMPLAI_PYTHON or 3.11).
#>
[CmdletBinding()]
param(
    [switch]$InstallUv,
    [string]$Python
)

$ErrorActionPreference = 'Stop'

if (-not $Python) {
    $Python = if ($env:OPENCOMPLAI_PYTHON) { $env:OPENCOMPLAI_PYTHON } else { '3.11' }
}
$Spec = if ($env:OPENCOMPLAI_SPEC) { $env:OPENCOMPLAI_SPEC } else { 'opencomplai' }

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    if ($InstallUv) {
        Write-Output 'Installing uv with the official installer (https://astral.sh/uv/install.ps1)...'
        $env:UV_NO_MODIFY_PATH = '1'
        $installer = Invoke-RestMethod -Uri 'https://astral.sh/uv/install.ps1'
        & ([scriptblock]::Create($installer))
        $env:Path = (Join-Path $HOME '.local\bin') + ';' + $env:Path
    }
    else {
        Write-Warning 'install.ps1: uv is not installed.'
        Write-Warning 'Install it first: https://docs.astral.sh/uv/getting-started/installation/'
        Write-Warning 'or re-run this script with -InstallUv to run the official uv installer.'
        exit 1
    }
}

$toolArgs = @('tool', 'install', '--python', $Python, '--force')
if ($env:OPENCOMPLAI_FIND_LINKS) {
    $toolArgs += @('--find-links', $env:OPENCOMPLAI_FIND_LINKS)
}
$toolArgs += $Spec
& uv @toolArgs
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed with exit code $LASTEXITCODE" }

$bin = (& uv tool dir --bin | Select-Object -First 1)
if ($LASTEXITCODE -ne 0) { throw "uv tool dir failed with exit code $LASTEXITCODE" }
if (($env:Path -split ';') -notcontains $bin) {
    Write-Output "Add $bin to your PATH to run opencomplai from any shell."
}

& (Join-Path $bin 'opencomplai.exe') --version
if ($LASTEXITCODE -ne 0) { throw "opencomplai --version failed with exit code $LASTEXITCODE" }
