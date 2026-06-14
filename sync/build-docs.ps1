param(
    [switch]$Serve = $false
)

$ErrorActionPreference = "Stop"

Write-Host "🔨 Building OpenComplai Documentation..." -ForegroundColor Green
Write-Host ""

# Check Python/MkDocs
Write-Host "📋 Checking MkDocs installation..." -ForegroundColor Cyan
try {
    $mkdocsVersion = mkdocs --version 2>$null
    if (-not $mkdocsVersion) {
        throw "MkDocs not found"
    }
} catch {
    Write-Host "❌ MkDocs not installed" -ForegroundColor Red
    Write-Host "   Run: pip install -r requirements-docs.txt"
    exit 1
}

# Build documentation
Write-Host "📚 Building documentation..." -ForegroundColor Yellow
Push-Location docs/
mkdocs build --strict
Pop-Location

# Create build manifest
Write-Host "📝 Creating build manifest..." -ForegroundColor Yellow

try {
    $gitVersion = & git describe --tags 2>$null
    if (-not $gitVersion) {
        $gitVersion = "dev"
    }
} catch {
    $gitVersion = "dev"
}

$gitCommit = & git rev-parse --short HEAD
$gitCommitFull = & git rev-parse HEAD
$gitBranch = & git rev-parse --abbrev-ref HEAD
$buildTime = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")

$manifest = @{
    version = $gitVersion
    commit = $gitCommit
    commit_hash = $gitCommitFull
    branch = $gitBranch
    built_at = $buildTime
    build_source = "opencomplai"
} | ConvertTo-Json

$manifest | Set-Content "docs/site/build-manifest.json" -Encoding UTF8

# Statistics
Write-Host ""
Write-Host "✅ Documentation built successfully!" -ForegroundColor Green
Write-Host "📍 Output location: ./docs/site" -ForegroundColor Green

$fileCount = @(Get-ChildItem -Path "docs/site" -Recurse -File).Count
Write-Host "📊 Total files: $fileCount" -ForegroundColor Green

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run: mkdocs serve (to preview locally)"
Write-Host "  2. Visit: http://127.0.0.1:8000"

if ($Serve) {
    Write-Host ""
    Write-Host "Starting local preview server..." -ForegroundColor Cyan
    Push-Location docs/
    mkdocs serve
    Pop-Location
}
