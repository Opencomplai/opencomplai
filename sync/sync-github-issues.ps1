<#
.SYNOPSIS
    Sync GitHub issues to local markdown files with comments and embedded media.

.DESCRIPTION
    Pull-only sync from the current git repo's GitHub remote into ./github-issues/.
    Uses git credential helper for authentication (same as git push/pull).
    Skips unchanged issues on subsequent runs using .sync-manifest.json.

.PARAMETER Repo
    Override owner/repo. Auto-detected from git remote when omitted.

.PARAMETER OutputDir
    Export directory. Defaults to {gitRoot}/github-issues.

.EXAMPLE
    ./scripts/sync-github-issues.ps1

.EXAMPLE
    ./scripts/sync-github-issues.ps1 -State open -Prune

.EXAMPLE
    ./scripts/sync-github-issues.ps1 -DryRun

.NOTES
    Prerequisites:
      - Git installed with credential helper configured for GitHub
      - Run from inside the target git repository

    Exit codes: 0=ok, 1=prereq, 2=partial failure, 3=auth, 4=usage
#>
[CmdletBinding()]
param(
    [string]$Repo = "",
    [string]$OutputDir = "",
    [ValidateSet("open", "closed", "all")]
    [string]$State = "all",
    [string[]]$Labels = @(),
    [switch]$IncludeComments,
    [switch]$DownloadMedia,
    [switch]$Force,
    [switch]$Prune,
    [switch]$DryRun,
    [switch]$ContinueOnError,
    [switch]$AllowSvg
)

$ErrorActionPreference = "Stop"

# Defaults for switch params when not specified
if (-not $PSBoundParameters.ContainsKey("IncludeComments")) { $IncludeComments = $true }
if (-not $PSBoundParameters.ContainsKey("DownloadMedia")) { $DownloadMedia = $true }

$script:ExitOk = 0
$script:ExitPrereq = 1
$script:ExitPartial = 2
$script:ExitAuth = 3
$script:ExitUsage = 4

$script:Stats = @{
    Fetched   = 0
    Changed   = 0
    Skipped   = 0
    Written   = 0
    Downloaded = 0
    Reused    = 0
    Pruned    = 0
    Errors    = 0
}

$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$script:GitHubApiHeaders = $null

#region Preflight

function Test-GitInstalled {
    $gitCmd = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCmd) {
        Write-Host "Git is not installed or not on PATH." -ForegroundColor Red
        Write-Host "Install from: https://git-scm.com/download/win"
        exit $script:ExitPrereq
    }
    $version = (git --version 2>$null | Select-Object -First 1)
    Write-Host "Using $version" -ForegroundColor Cyan
}

function Get-GitRoot {
    try {
        $root = git rev-parse --show-toplevel 2>$null
        if (-not $root) { throw "Not a git repository" }
        return $root.Trim()
    }
    catch {
        Write-Host "Not inside a git repository. Run from the repo root or a subdirectory." -ForegroundColor Red
        exit $script:ExitPrereq
    }
}

function Resolve-GitHubRepo {
    param([string]$GitRoot, [string]$RepoOverride)

    if ($RepoOverride) {
        if ($RepoOverride -notmatch '^[\w.-]+/[\w.-]+$') {
            Write-Host "Invalid -Repo format. Expected owner/repo." -ForegroundColor Red
            exit $script:ExitUsage
        }
        return $RepoOverride
    }

    Push-Location $GitRoot
    try {
        $remote = git remote get-url origin 2>$null
        if ($remote -match 'github\.com[:/](?<owner>[^/]+)/(?<name>[^/]+?)(?:\.git)?$') {
            return "$($Matches.owner)/$($Matches.name)"
        }
        if ($remote -match 'git@github\.com:(?<owner>[^/]+)/(?<name>[^/]+?)(?:\.git)?$') {
            return "$($Matches.owner)/$($Matches.name)"
        }
    }
    catch { }
    finally {
        Pop-Location
    }

    Write-Host "Could not detect GitHub repo from git remote origin. Pass -Repo owner/repo explicitly." -ForegroundColor Red
    exit $script:ExitPrereq
}

function Get-GitHubHost {
    param([string]$GitRoot)

    Push-Location $GitRoot
    try {
        $remote = git remote get-url origin 2>$null
        if ($remote -match '(?:git@|https?://)([^/:]+)') {
            return $Matches[1].ToLowerInvariant()
        }
    }
    catch { }
    finally {
        Pop-Location
    }
    return "github.com"
}

function Get-GitCredential {
    param([string]$GitHubHost = "github.com")

    $input = "protocol=https`nhost=$GitHubHost`n`n"
    $output = $input | git credential fill 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to read git credentials for $GitHubHost." -ForegroundColor Red
        Write-Host "Ensure git credential helper is configured (same credentials used for git push/pull)." -ForegroundColor Red
        exit $script:ExitAuth
    }

    $username = $null
    $password = $null
    foreach ($line in ($output -split "`n")) {
        if ($line -match '^username=(.+)$') { $username = $Matches[1].Trim() }
        if ($line -match '^password=(.+)$') { $password = $Matches[1].Trim() }
    }

    if (-not $password) {
        Write-Host "No GitHub credentials found in git credential store for $GitHubHost." -ForegroundColor Red
        exit $script:ExitAuth
    }

    return @{
        Username = $username
        Password = $password
    }
}

function New-GitHubAuthHeaderValue {
    param([string]$Username, [string]$Password)

    if ($Password -match '^(ghp_|github_pat_|gho_|ghs_|ghr_)') {
        return "Bearer $Password"
    }

    $pair = "{0}:{1}" -f $Username, $Password
    $bytes = [Text.Encoding]::ASCII.GetBytes($pair)
    return "Basic $([Convert]::ToBase64String($bytes))"
}

function Initialize-GitHubAuth {
    param([string]$GitHubHost)

    $cred = Get-GitCredential -GitHubHost $GitHubHost
    $authValue = New-GitHubAuthHeaderValue -Username $cred.Username -Password $cred.Password
    $script:GitHubApiHeaders = @{
        Authorization = $authValue
        "User-Agent"  = "opencomplai-issue-sync"
        Accept        = "application/vnd.github+json"
    }
    Write-Host "Using git credentials for $GitHubHost" -ForegroundColor Cyan
}

function Acquire-SyncLock {
    param([string]$OutputDir)

    $lockPath = Join-Path $OutputDir ".sync.lock"
    if (Test-Path -LiteralPath $lockPath) {
        Write-Host "Sync already in progress ($lockPath exists)." -ForegroundColor Red
        exit $script:ExitPrereq
    }
    if (-not $DryRun) {
        $null = New-Item -ItemType File -Path $lockPath -Force
    }
    return $lockPath
}

function Release-SyncLock {
    param([string]$LockPath)
    if ($LockPath -and (Test-Path -LiteralPath $LockPath)) {
        Remove-Item -LiteralPath $LockPath -Force -ErrorAction SilentlyContinue
    }
}

#endregion

#region Fetch

function Invoke-GitHubApi {
    param(
        [Parameter(Mandatory)][string]$Path,
        [hashtable]$Query = @{},
        [int]$MaxRetries = 3
    )

    if (-not $script:GitHubApiHeaders) {
        throw "GitHub API not initialized. Call Initialize-GitHubAuth first."
    }

    $results = New-Object 'System.Collections.ArrayList'
    $page = 1
    $perPage = 100

    while ($true) {
        $queryParams = @{
            per_page = $perPage
            page     = $page
        }
        foreach ($key in $Query.Keys) {
            $queryParams[$key] = $Query[$key]
        }

        $queryString = ($queryParams.GetEnumerator() | ForEach-Object {
                "$($_.Key)=$([uri]::EscapeDataString([string]$_.Value))"
            }) -join "&"

        $uri = "https://api.github.com/$Path"
        if ($queryString) { $uri += "?$queryString" }

        $attempt = 0
        $response = $null
        while ($true) {
            $attempt++
            try {
                $response = Invoke-WebRequest -Uri $uri -Headers $script:GitHubApiHeaders -UseBasicParsing
                break
            }
            catch {
                $status = $null
                if ($_.Exception.Response) {
                    $status = [int]$_.Exception.Response.StatusCode
                }
                $msg = $_.Exception.Message

                if ($status -eq 401 -or $status -eq 403) {
                    Write-Host "GitHub API authentication failed ($status). Check git credentials for this host." -ForegroundColor Red
                    exit $script:ExitAuth
                }

                if ($attempt -lt $MaxRetries -and ($status -eq 429 -or ($status -ge 500 -and $status -lt 600))) {
                    $sleep = [Math]::Min(60, [Math]::Pow(2, $attempt))
                    Write-Warning "GitHub API error ($status); retry $attempt/$MaxRetries in ${sleep}s..."
                    Start-Sleep -Seconds $sleep
                    continue
                }

                throw "GitHub API request failed ($status): $msg"
            }
        }

        if (-not $response.Content) { break }
        $batch = @($response.Content | ConvertFrom-Json)
        if ($batch.Count -eq 0) { break }

        foreach ($item in $batch) {
            [void]$results.Add($item)
        }

        if ($batch.Count -lt $perPage) { break }
        $page++
    }

    return ,@($results.ToArray())
}

function Normalize-GitHubIssue {
    param($Issue)

    return [PSCustomObject]@{
        number        = $Issue.number
        title         = $Issue.title
        body          = $Issue.body
        state         = $Issue.state
        labels        = $Issue.labels
        assignees     = $Issue.assignees
        author        = $Issue.user
        createdAt     = $Issue.created_at
        updatedAt     = $Issue.updated_at
        closedAt      = $Issue.closed_at
        milestone     = $Issue.milestone
        url           = $Issue.html_url
        isPullRequest = [bool]$Issue.pull_request
    }
}

function Normalize-GitHubComment {
    param($Comment)

    $user = $Comment.user
    if (-not $user -and $Comment.author) { $user = $Comment.author }

    return [PSCustomObject]@{
        id        = $Comment.id
        body      = $Comment.body
        createdAt = if ($Comment.PSObject.Properties['createdAt']) { $Comment.createdAt } else { $Comment.created_at }
        updatedAt = if ($Comment.PSObject.Properties['updatedAt']) { $Comment.updatedAt } else { $Comment.updated_at }
        user      = $user
    }
}

function Get-GitHubIssues {
    param(
        [string]$Repo,
        [string]$State,
        [string[]]$Labels
    )

    $owner, $repoName = $Repo -split '/', 2
    $query = @{ state = $State }
    if ($Labels -and $Labels.Count -gt 0) {
        $query.labels = ($Labels -join ",")
    }

    $raw = Invoke-GitHubApi -Path "repos/$owner/$repoName/issues" -Query $query
    $issues = @($raw | ForEach-Object { Normalize-GitHubIssue -Issue $_ })
    return @($issues | Where-Object { -not $_.isPullRequest })
}

function Get-GitHubComments {
    param(
        [string]$Owner,
        [string]$Name,
        [int]$Number
    )

    $raw = Invoke-GitHubApi -Path "repos/$Owner/$Name/issues/$Number/comments"
    if (-not $raw) { return @() }
    return @($raw | ForEach-Object { Normalize-GitHubComment -Comment $_ })
}

#endregion

#region Manifest

function Read-SyncManifest {
    param([string]$OutputDir)

    $path = Join-Path $OutputDir ".sync-manifest.json"
    if (-not (Test-Path -LiteralPath $path)) {
        return @{
            schemaVersion = 1
            repo          = ""
            git_root      = ""
            last_sync_at  = ""
            issues        = @{}
        }
    }

    try {
        $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        $data = $raw | ConvertFrom-Json
        $issues = @{}
        if ($data.issues) {
            $data.issues.PSObject.Properties | ForEach-Object {
                $issues[$_.Name] = $_.Value
            }
        }
        return @{
            schemaVersion = if ($data.schemaVersion) { $data.schemaVersion } else { 1 }
            repo          = $data.repo
            git_root      = $data.git_root
            last_sync_at  = $data.last_sync_at
            issues        = $issues
        }
    }
    catch {
        Write-Warning "Corrupt manifest at $path; treating as empty (full re-sync)."
        return @{
            schemaVersion = 1
            repo          = ""
            git_root      = ""
            last_sync_at  = ""
            issues        = @{}
        }
    }
}

function Write-SyncManifest {
    param(
        [string]$OutputDir,
        [hashtable]$Manifest,
        [switch]$DryRun
    )

    if ($DryRun) { return }

    $issuesObj = [ordered]@{}
    foreach ($key in ($Manifest.issues.Keys | Sort-Object { [int]$_ })) {
        $issuesObj[$key] = $Manifest.issues[$key]
    }

    $out = [ordered]@{
        schemaVersion = 1
        repo          = $Manifest.repo
        git_root      = $Manifest.git_root
        last_sync_at  = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        issues        = $issuesObj
    }

    $json = $out | ConvertTo-Json -Depth 20
    $tmp = Join-Path $OutputDir ".sync-manifest.json.tmp"
    $final = Join-Path $OutputDir ".sync-manifest.json"
    [System.IO.File]::WriteAllText($tmp, $json, $Utf8NoBom)
    Move-Item -LiteralPath $tmp -Destination $final -Force
}

function Get-CommentsUpdatedAt {
    param($Comments)
    if (-not $Comments -or $Comments.Count -eq 0) { return $null }
    return ($Comments | ForEach-Object { $_.updatedAt } | Sort-Object -Descending | Select-Object -First 1)
}

function Get-ContentHash {
    param($Issue, $Comments)

    $labels = @($Issue.labels | ForEach-Object { $_.name } | Sort-Object)
    $commentData = @($Comments | Sort-Object { $_.id } | ForEach-Object {
            [ordered]@{
                id         = $_.id
                body       = if ($_.body) { $_.body } else { "" }
                updated_at = $_.updatedAt
            }
        })

    $payload = [ordered]@{
        title    = $Issue.title
        body     = if ($Issue.body) { $Issue.body } else { "" }
        state    = $Issue.state
        labels   = $labels
        comments = $commentData
    }

    $json = $payload | ConvertTo-Json -Compress -Depth 20
    $bytes = $Utf8NoBom.GetBytes($json)
    $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $hex = -join ($hash | ForEach-Object { $_.ToString("x2") })
    return "sha256:$hex"
}

function Test-IssueUnchanged {
    param(
        $Issue,
        $Comments,
        $ManifestEntry
    )

    if (-not $ManifestEntry) { return $false }

    $issueUpdated = $Issue.updatedAt
    if ($ManifestEntry.updated_at -ne $issueUpdated) { return $false }

    $commentsUpdated = Get-CommentsUpdatedAt -Comments $Comments
    $manifestCommentsUpdated = $ManifestEntry.comments_updated_at
    if ($manifestCommentsUpdated -ne $commentsUpdated) { return $false }

    $count = if ($Comments) { @($Comments).Count } else { 0 }
    if ($ManifestEntry.comments_count -ne $count) { return $false }

    $hash = Get-ContentHash -Issue $Issue -Comments $Comments
    if ($ManifestEntry.content_hash -ne $hash) { return $false }

    return $true
}

#endregion

#region Render

function ConvertTo-IssueSlug {
    param([string]$Title)

    $slug = $Title.ToLowerInvariant()
    $slug = $slug -replace '[^a-z0-9]+', '-'
    $slug = $slug -replace '(^-|-$)', ''
    if ($slug.Length -gt 60) { $slug = $slug.Substring(0, 60).TrimEnd('-') }
    if (-not $slug) { $slug = "issue" }
    return $slug
}

function Get-IssueFileName {
    param([int]$Number, [string]$Title)
    $slug = ConvertTo-IssueSlug -Title $Title
    return "{0:D5}-{1}.md" -f $Number, $slug
}

function Escape-YamlString {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    if ($Value -match '[:#\[\]{}&*!|>''"%@`]' -or $Value -match '^\s|\s$' -or $Value -match '[\r\n]') {
        return '"' + ($Value -replace '\\', '\\\\' -replace '"', '\"') + '"'
    }
    return $Value
}

function Format-YamlList {
    param([string[]]$Items)
    if (-not $Items -or $Items.Count -eq 0) { return "[]" }
    $quoted = $Items | ForEach-Object { '"' + ($_ -replace '"', '\"') + '"' }
    return "[" + ($quoted -join ", ") + "]"
}

function Format-IssueMarkdown {
    param(
        $Issue,
        $Comments,
        [string]$Repo,
        [string]$Body,
        [bool]$IncludeComments
    )

    $labels = @($Issue.labels | ForEach-Object { $_.name })
    $assignees = @($Issue.assignees | ForEach-Object { $_.login })
    $author = if ($Issue.author.login) { $Issue.author.login } else { "unknown" }
    $milestone = if ($Issue.milestone) { $Issue.milestone.title } else { $null }
    $syncedAt = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    $commentsCount = if ($Comments) { @($Comments).Count } else { 0 }

    $lines = @(
        "---"
        "github_id: $($Issue.number)"
        "number: $($Issue.number)"
        "title: $(Escape-YamlString $Issue.title)"
        "state: $($Issue.state)"
        "labels: $(Format-YamlList $labels)"
        "assignees: $(Format-YamlList $assignees)"
        "author: $author"
        "milestone: $(if ($milestone) { Escape-YamlString $milestone } else { 'null' })"
        "created_at: $($Issue.createdAt)"
        "updated_at: $($Issue.updatedAt)"
        "closed_at: $(if ($Issue.closedAt) { $Issue.closedAt } else { 'null' })"
        "url: $($Issue.url)"
        "synced_at: $syncedAt"
        "repo: $Repo"
        "comments_count: $commentsCount"
        "---"
        ""
        "# $($Issue.title)"
        ""
        $Body
    )

    if ($IncludeComments -and $Comments -and $Comments.Count -gt 0) {
        $lines += ""
        $lines += "---"
        $lines += ""
        $lines += "## Comments"
        $lines += ""

        foreach ($comment in ($Comments | Sort-Object { $_.createdAt })) {
            $user = if ($comment.user.login) { $comment.user.login } else { "unknown" }
            $lines += "### @$user - $($comment.createdAt)"
            $lines += ""
            $commentBody = if ($comment.body) { $comment.body } else { "" }
            $lines += $commentBody
            $lines += ""
        }
    }

    return ($lines -join "`n").TrimEnd() + "`n"
}

#endregion

#region Media

function Get-UrlHash8 {
    param([string]$Url)
    $bytes = $Utf8NoBom.GetBytes($Url)
    $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $hex = -join ($hash | ForEach-Object { $_.ToString("x2") })
    return $hex.Substring(0, 8)
}

function Test-MediaUrlAllowed {
    param([string]$Url, [bool]$AllowSvg)

    if ($Url -match '^data:image/') {
        if ($Url -match '^data:image/svg') { return $AllowSvg }
        return $true
    }

    try {
        $uri = [Uri]$Url
        $hostName = $uri.Host.ToLowerInvariant()
        $allowed = (
            $hostName -eq "github.com" -or
            $hostName -like "*.github.com" -or
            $hostName -like "*.githubusercontent.com"
        )
        if (-not $allowed) { return $false }
        if (-not $AllowSvg -and ($Url -match '\.svg($|\?)' -or $Url -match '^data:image/svg')) {
            return $false
        }
        return $true
    }
    catch {
        return $false
    }
}

function Get-MediaUrls {
    param([string]$Text)

    if (-not $Text) { return @() }

    $mediaUrlSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

    $mdPattern = '!\[[^\]]*\]\(([^)]+)\)'
    foreach ($match in [regex]::Matches($Text, $mdPattern)) {
        $u = $match.Groups[1].Value.Trim()
        if ($u) { [void]$mediaUrlSet.Add($u) }
    }

    $htmlPattern = '<img[^>]+src=["'']([^"'']+)["'']'
    foreach ($match in [regex]::Matches($Text, $htmlPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
        $u = $match.Groups[1].Value.Trim()
        if ($u) { [void]$mediaUrlSet.Add($u) }
    }

    $result = New-Object string[] $mediaUrlSet.Count
    $mediaUrlSet.CopyTo($result)
    return ,$result
}

function Get-MediaExtension {
    param([string]$Url, [string]$ContentType = "")

    if ($Url -match '^data:image/([^;]+)') {
        $ext = $Matches[1].ToLowerInvariant()
        if ($ext -eq "jpeg") { return "jpg" }
        return $ext
    }

    if ($ContentType) {
        switch -Regex ($ContentType) {
            'image/png'  { return "png" }
            'image/jpeg' { return "jpg" }
            'image/gif'  { return "gif" }
            'image/webp' { return "webp" }
            'image/svg'  { return "svg" }
        }
    }

    $path = ($Url -split '\?')[0]
    if ($path -match '\.(\w{2,5})$') {
        $ext = $Matches[1].ToLowerInvariant()
        if ($ext -eq "jpeg") { return "jpg" }
        return $ext
    }
    return "bin"
}

function Save-RemoteMedia {
    param(
        [string]$Url,
        [string]$DestDir,
        [string]$RelativePrefix,
        [bool]$AllowSvg,
        [hashtable]$ExistingMap,
        [string]$OutputDir,
        [switch]$DryRun
    )

    $normalizedUrl = $Url
    if ($Url -notmatch '^data:') {
        $normalizedUrl = ($Url -split '\?')[0]
    }

    if ($ExistingMap -and $ExistingMap.ContainsKey($Url)) {
        $rel = $ExistingMap[$Url]
        $full = Join-Path $OutputDir ($rel -replace '/', [IO.Path]::DirectorySeparatorChar)
        if (Test-Path -LiteralPath $full) {
            $script:Stats.Reused++
            return $rel
        }
    }

    if (-not (Test-MediaUrlAllowed -Url $Url -AllowSvg:$AllowSvg)) {
        Write-Warning "Skipping disallowed or unsupported media URL: $($normalizedUrl)"
        return $null
    }

    $hash8 = Get-UrlHash8 -Url $Url
    $ext = Get-MediaExtension -Url $Url
    $fileName = "$hash8.$ext"
    $relPath = "$RelativePrefix/$fileName" -replace '\\', '/'
    $destPath = Join-Path $DestDir $fileName

    if ($DryRun) {
        Write-Host "  [dry-run] would download: $normalizedUrl -> $relPath" -ForegroundColor DarkGray
        $script:Stats.Downloaded++
        return $relPath
    }

    if (-not (Test-Path -LiteralPath $DestDir)) {
        $null = New-Item -ItemType Directory -Path $DestDir -Force
    }

    if ($Url -match '^data:image/[^;]+;base64,(.+)$') {
        $bytes = [Convert]::FromBase64String($Matches[1])
        [System.IO.File]::WriteAllBytes($destPath, $bytes)
    }
    else {
        try {
            $headers = $script:GitHubApiHeaders
            if ($headers) {
                Invoke-WebRequest -Uri $Url -Headers $headers -OutFile $destPath -UseBasicParsing | Out-Null
            }
            else {
                Invoke-WebRequest -Uri $Url -OutFile $destPath -UseBasicParsing | Out-Null
            }
        }
        catch {
            Write-Warning "Failed to download $normalizedUrl : $_"
            return $null
        }
    }

    $script:Stats.Downloaded++
    return $relPath
}

function Rewrite-MediaLinks {
    param(
        [string]$Text,
        [hashtable]$UrlMap
    )

    if (-not $Text -or $UrlMap.Count -eq 0) { return $Text }

    $result = $Text
    foreach ($entry in $UrlMap.GetEnumerator()) {
        if ($entry.Value) {
            $result = $result.Replace($entry.Key, $entry.Value)
        }
    }
    return $result
}

function Sync-IssueMedia {
    param(
        [string]$Body,
        [object[]]$Comments,
        [int]$IssueNumber,
        [string]$OutputDir,
        [hashtable]$ManifestMediaUrls,
        [bool]$AllowSvg,
        [switch]$DryRun
    )

    $issuePadded = "{0:D5}" -f $IssueNumber
    $assetsDir = Join-Path (Join-Path $OutputDir "assets") $issuePadded
    $relativePrefix = "../assets/$issuePadded"

    $texts = @($Body)
    if ($Comments) {
        $texts += @($Comments | ForEach-Object { $_.body })
    }

    $urlMap = @{}
    $mediaManifest = @{}

    foreach ($text in $texts) {
        foreach ($url in (Get-MediaUrls -Text $text)) {
            if ($urlMap.ContainsKey($url)) { continue }

            $existing = @{}
            if ($ManifestMediaUrls) {
                $ManifestMediaUrls.GetEnumerator() | ForEach-Object { $existing[$_.Key] = $_.Value }
            }

            $rel = Save-RemoteMedia -Url $url `
                -DestDir $assetsDir `
                -RelativePrefix $relativePrefix `
                -AllowSvg:$AllowSvg `
                -ExistingMap $existing `
                -OutputDir $OutputDir `
                -DryRun:$DryRun

            if ($rel) {
                $urlMap[$url] = $rel
                $leaf = Split-Path $rel -Leaf
                $mediaManifest[$url] = "assets/$issuePadded/$leaf"
            }
        }
    }

    $newBody = Rewrite-MediaLinks -Text $Body -UrlMap $urlMap
    $newComments = @()
    if ($Comments) {
        foreach ($c in $Comments) {
            $clone = [PSCustomObject]@{
                id        = $c.id
                body      = Rewrite-MediaLinks -Text $c.body -UrlMap $urlMap
                createdAt = $c.createdAt
                updatedAt = $c.updatedAt
                user      = $c.user
            }
            $newComments += $clone
        }
    }

    return @{
        Body          = $newBody
        Comments      = $newComments
        MediaManifest = $mediaManifest
    }
}

#endregion

#region Orchestrate

function Write-AtomicTextFile {
    param(
        [string]$Path,
        [string]$Content,
        [switch]$DryRun
    )

    if ($DryRun) { return }

    $dir = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $dir)) {
        $null = New-Item -ItemType Directory -Path $dir -Force
    }

    $tmp = "$Path.tmp"
    [System.IO.File]::WriteAllText($tmp, $Content, $Utf8NoBom)
    Move-Item -LiteralPath $tmp -Destination $Path -Force
}

function Invoke-Prune {
    param(
        [string]$OutputDir,
        [int[]]$ActiveNumbers,
        [switch]$DryRun
    )

    $issuesDir = Join-Path $OutputDir "issues"
    $assetsDir = Join-Path $OutputDir "assets"
    $activeSet = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($n in $ActiveNumbers) { [void]$activeSet.Add($n) }

    if (Test-Path -LiteralPath $issuesDir) {
        Get-ChildItem -LiteralPath $issuesDir -Filter "*.md" -File | ForEach-Object {
            if ($_.BaseName -match '^(\d{5})-') {
                $num = [int]$Matches[1]
                if (-not $activeSet.Contains($num)) {
                    Write-Host "  Prune issue file: $($_.Name)" -ForegroundColor Yellow
                    if (-not $DryRun) { Remove-Item -LiteralPath $_.FullName -Force }
                    $script:Stats.Pruned++
                }
            }
        }
    }

    if (Test-Path -LiteralPath $assetsDir) {
        Get-ChildItem -LiteralPath $assetsDir -Directory | ForEach-Object {
            if ($_.Name -match '^\d{5}$') {
                $num = [int]$_.Name
                if (-not $activeSet.Contains($num)) {
                    Write-Host "  Prune assets: $($_.Name)" -ForegroundColor Yellow
                    if (-not $DryRun) { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
                }
            }
        }
    }
}

function Write-Summary {
    Write-Host ""
    Write-Host "Sync summary" -ForegroundColor Green
    Write-Host "  Fetched:    $($script:Stats.Fetched)"
    Write-Host "  Changed:    $($script:Stats.Changed)"
    Write-Host "  Skipped:    $($script:Stats.Skipped)"
    Write-Host "  Written:    $($script:Stats.Written)"
    Write-Host "  Downloaded: $($script:Stats.Downloaded)"
    Write-Host "  Reused:     $($script:Stats.Reused)"
    Write-Host "  Pruned:     $($script:Stats.Pruned)"
    Write-Host "  Errors:     $($script:Stats.Errors)"
}

function Sync-GitHubIssues {
    Test-GitInstalled

    $gitRoot = Get-GitRoot
    $resolvedRepo = Resolve-GitHubRepo -GitRoot $gitRoot -RepoOverride $Repo
    $githubHost = Get-GitHubHost -GitRoot $gitRoot
    Initialize-GitHubAuth -GitHubHost $githubHost

    if (-not $OutputDir) {
        $OutputDir = Join-Path $gitRoot "github-issues"
    }
    elseif (-not [IO.Path]::IsPathRooted($OutputDir)) {
        $OutputDir = Join-Path $gitRoot $OutputDir
    }

    $OutputDir = [IO.Path]::GetFullPath($OutputDir)
    $issuesDir = Join-Path $OutputDir "issues"

    Write-Host "Syncing issues for $resolvedRepo" -ForegroundColor Green
    Write-Host "Output: $OutputDir" -ForegroundColor Cyan
    if ($DryRun) { Write-Host "Dry run - no files will be written." -ForegroundColor Yellow }

    if (-not $DryRun) {
        foreach ($dir in @($OutputDir, $issuesDir)) {
            if (-not (Test-Path -LiteralPath $dir)) {
                $null = New-Item -ItemType Directory -Path $dir -Force
            }
        }
    }

    $lockPath = Acquire-SyncLock -OutputDir $OutputDir
    $hadErrors = $false

    try {
        $owner, $name = $resolvedRepo -split '/', 2
        $manifest = Read-SyncManifest -OutputDir $OutputDir
        $manifest.repo = $resolvedRepo
        $manifest.git_root = $gitRoot

        $issues = Get-GitHubIssues -Repo $resolvedRepo -State $State -Labels $Labels
        $script:Stats.Fetched = $issues.Count
        Write-Host "Fetched $($issues.Count) issues" -ForegroundColor Cyan

        $activeNumbers = @($issues | ForEach-Object { $_.number })

        foreach ($issue in $issues) {
            $numKey = "$($issue.number)"
            $fileName = Get-IssueFileName -Number $issue.number -Title $issue.title
            $relFile = "issues/$fileName"
            $outPath = Join-Path $OutputDir $relFile

            $manifestEntry = $null
            if ($manifest.issues.ContainsKey($numKey)) {
                $manifestEntry = $manifest.issues[$numKey]
            }

            $comments = @()

            if (-not $Force -and $manifestEntry) {
                if ($manifestEntry.updated_at -ne $issue.updatedAt) {
                    $script:Stats.Changed++
                }
                else {
                    if ($IncludeComments) {
                        $comments = Get-GitHubComments -Owner $owner -Name $name -Number $issue.number
                    }
                    if (Test-IssueUnchanged -Issue $issue -Comments $comments -ManifestEntry $manifestEntry) {
                        Write-Host "  #$($issue.number) unchanged - skip" -ForegroundColor DarkGray
                        $script:Stats.Skipped++
                        continue
                    }
                    $script:Stats.Changed++
                }
            }
            else {
                $script:Stats.Changed++
            }

            if ($comments.Count -eq 0 -and $IncludeComments) {
                $comments = Get-GitHubComments -Owner $owner -Name $name -Number $issue.number
            }

            Write-Host "  #$($issue.number) $($issue.title)" -ForegroundColor White

            $body = if ($issue.body) { $issue.body } else { "" }
            $mediaResult = @{
                Body          = $body
                Comments      = $comments
                MediaManifest = @{}
            }

            if ($DownloadMedia) {
                $existingMedia = @{}
                if ($manifestEntry -and $manifestEntry.media_urls) {
                    $manifestEntry.media_urls.PSObject.Properties | ForEach-Object {
                        $existingMedia[$_.Name] = $_.Value
                    }
                }
                $mediaResult = Sync-IssueMedia -Body $body -Comments $comments `
                    -IssueNumber $issue.number -OutputDir $OutputDir `
                    -ManifestMediaUrls $existingMedia -AllowSvg:$AllowSvg -DryRun:$DryRun
            }

            $markdown = Format-IssueMarkdown -Issue $issue -Comments $mediaResult.Comments `
                -Repo $resolvedRepo -Body $mediaResult.Body -IncludeComments:$IncludeComments

            if ($DryRun) {
                Write-Host "  [dry-run] would write $relFile" -ForegroundColor DarkGray
            }
            else {
                Write-AtomicTextFile -Path $outPath -Content $markdown -DryRun:$false
                $script:Stats.Written++
            }

            $mediaUrlsObj = @{}
            foreach ($entry in $mediaResult.MediaManifest.GetEnumerator()) {
                $mediaUrlsObj[$entry.Key] = $entry.Value
            }

            $manifest.issues[$numKey] = [PSCustomObject]@{
                file                  = $relFile
                updated_at            = $issue.updatedAt
                comments_updated_at   = Get-CommentsUpdatedAt -Comments $comments
                comments_count        = if ($comments) { @($comments).Count } else { 0 }
                content_hash          = Get-ContentHash -Issue $issue -Comments $comments
                media_urls            = $mediaUrlsObj
                synced_at             = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
            }
        }

        if ($Prune) {
            Write-Host "Pruning stale local files..." -ForegroundColor Yellow
            Invoke-Prune -OutputDir $OutputDir -ActiveNumbers $activeNumbers -DryRun:$DryRun
        }

        Write-SyncManifest -OutputDir $OutputDir -Manifest $manifest -DryRun:$DryRun
    }
    catch {
        $hadErrors = $true
        $script:Stats.Errors++
        Write-Host "Error: $_" -ForegroundColor Red
        if (-not $ContinueOnError) { throw }
    }
    finally {
        Release-SyncLock -LockPath $lockPath
    }

    Write-Summary

    if ($hadErrors -or $script:Stats.Errors -gt 0) {
        exit $script:ExitPartial
    }
    exit $script:ExitOk
}

#endregion

if ($MyInvocation.InvocationName -ne '.' -and $PSCommandPath -eq $MyInvocation.MyCommand.Path) {
    Sync-GitHubIssues
}
