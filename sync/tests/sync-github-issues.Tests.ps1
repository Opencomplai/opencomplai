$script:SyncScriptPath = Join-Path (Join-Path $PSScriptRoot "..") "sync-github-issues.ps1"
. $script:SyncScriptPath

Describe "ConvertTo-IssueSlug" {
    It "lowercases and hyphenates" {
        ConvertTo-IssueSlug -Title "Fix Auth Token Leak!" | Should Be "fix-auth-token-leak"
    }

    It "truncates long titles" {
        $long = "a" * 80
        (ConvertTo-IssueSlug -Title $long).Length | Should BeLessThan 61
    }

    It "returns fallback for empty title" {
        ConvertTo-IssueSlug -Title "!!!" | Should Be "issue"
    }
}

Describe "Get-IssueFileName" {
    It "pads issue number to 5 digits" {
        Get-IssueFileName -Number 42 -Title "Bug" | Should Be "00042-bug.md"
    }
}

Describe "Get-ContentHash" {
    It "produces stable sha256 prefix" {
        $issue = [PSCustomObject]@{
            title  = "Test"
            body   = "Body"
            state  = "open"
            labels = @([PSCustomObject]@{ name = "bug" })
        }
        $comments = @(
            [PSCustomObject]@{
                id        = 1
                body      = "comment"
                updatedAt = "2025-01-01T00:00:00Z"
            }
        )
        $h1 = Get-ContentHash -Issue $issue -Comments $comments
        $h2 = Get-ContentHash -Issue $issue -Comments $comments
        $h1 | Should Be $h2
        ($h1 -match '^sha256:[a-f0-9]{64}$') | Should Be $true
    }

    It "changes when comment body changes" {
        $issue = [PSCustomObject]@{
            title  = "Test"
            body   = "Body"
            state  = "open"
            labels = @()
        }
        $c1 = @([PSCustomObject]@{ id = 1; body = "a"; updatedAt = "2025-01-01T00:00:00Z" })
        $c2 = @([PSCustomObject]@{ id = 1; body = "b"; updatedAt = "2025-01-01T00:00:00Z" })
        (Get-ContentHash -Issue $issue -Comments $c1) | Should Not Be (Get-ContentHash -Issue $issue -Comments $c2)
    }
}

Describe "Test-IssueUnchanged" {
    It "returns false when no manifest entry" {
        $issue = [PSCustomObject]@{
            title = "T"; body = "B"; state = "open"; labels = @(); updatedAt = "2025-01-01T00:00:00Z"
        }
        (Test-IssueUnchanged -Issue $issue -Comments @() -ManifestEntry $null) | Should Be $false
    }

    It "returns true when fingerprint matches" {
        $issue = [PSCustomObject]@{
            title = "T"; body = "B"; state = "open"; labels = @(); updatedAt = "2025-01-01T00:00:00Z"
        }
        $comments = @()
        $hash = Get-ContentHash -Issue $issue -Comments $comments
        $entry = [PSCustomObject]@{
            updated_at          = "2025-01-01T00:00:00Z"
            comments_updated_at = $null
            comments_count      = 0
            content_hash        = $hash
        }
        (Test-IssueUnchanged -Issue $issue -Comments $comments -ManifestEntry $entry) | Should Be $true
    }
}

Describe "Get-MediaUrls" {
    It "extracts markdown image URLs" {
        $text = '![alt](https://user-images.githubusercontent.com/u/1/abc.png?jwt=secret)'
        $urls = Get-MediaUrls -Text $text
        $urls.Count | Should Be 1
        ($urls[0] -match 'user-images.githubusercontent.com') | Should Be $true
    }

    It "extracts HTML img src" {
        $text = '<img src="https://github.com/user-attachments/assets/xyz.gif">'
        $urls = Get-MediaUrls -Text $text
        $urls.Count | Should Be 1
    }
}

Describe "Test-MediaUrlAllowed" {
    It "allows githubusercontent hosts" {
        (Test-MediaUrlAllowed -Url "https://user-images.githubusercontent.com/x.png" -AllowSvg:$false) | Should Be $true
    }

    It "blocks arbitrary hosts" {
        (Test-MediaUrlAllowed -Url "https://evil.example.com/x.png" -AllowSvg:$false) | Should Be $false
    }

    It "blocks svg by default" {
        (Test-MediaUrlAllowed -Url "https://github.com/x.svg" -AllowSvg:$false) | Should Be $false
    }

    It "allows svg when opted in" {
        (Test-MediaUrlAllowed -Url "https://github.com/x.svg" -AllowSvg:$true) | Should Be $true
    }

    It "allows data image URIs" {
        (Test-MediaUrlAllowed -Url "data:image/png;base64,abc" -AllowSvg:$false) | Should Be $true
    }
}

Describe "Rewrite-MediaLinks" {
    It "replaces URLs in text" {
        $map = @{ "https://example.com/a.png" = "../assets/00001/abcd1234.png" }
        $result = Rewrite-MediaLinks -Text "![x](https://example.com/a.png)" -UrlMap $map
        $result | Should Be "![x](../assets/00001/abcd1234.png)"
    }
}

Describe "Read-SyncManifest" {
    It "returns empty manifest when file missing" {
        $dir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_.FullName }
        try {
            $m = Read-SyncManifest -OutputDir $dir.FullName
            $m.schemaVersion | Should Be 1
            $m.issues.Count | Should Be 0
        }
        finally {
            Remove-Item -LiteralPath $dir.FullName -Recurse -Force
        }
    }

    It "handles corrupt manifest gracefully" {
        $dir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_.FullName }
        try {
            Set-Content -LiteralPath (Join-Path $dir.FullName ".sync-manifest.json") -Value "{not json"
            $m = Read-SyncManifest -OutputDir $dir.FullName
            $m.issues.Count | Should Be 0
        }
        finally {
            Remove-Item -LiteralPath $dir.FullName -Recurse -Force
        }
    }
}

Describe "Invoke-Prune" {
    It "removes issue files not in active set" {
        $dir = New-TemporaryFile | ForEach-Object { Remove-Item $_; New-Item -ItemType Directory -Path $_.FullName }
        $issuesDir = Join-Path $dir.FullName "issues"
        $null = New-Item -ItemType Directory -Path $issuesDir -Force
        $keep = Join-Path $issuesDir "00001-keep.md"
        $drop = Join-Path $issuesDir "00099-drop.md"
        Set-Content -LiteralPath $keep -Value "keep"
        Set-Content -LiteralPath $drop -Value "drop"

        $script:Stats.Pruned = 0
        Invoke-Prune -OutputDir $dir.FullName -ActiveNumbers @(1) -DryRun:$false

        (Test-Path -LiteralPath $keep) | Should Be $true
        (Test-Path -LiteralPath $drop) | Should Be $false
        $script:Stats.Pruned | Should Be 1

        Remove-Item -LiteralPath $dir.FullName -Recurse -Force
    }
}

Describe "Format-IssueMarkdown" {
    It "includes frontmatter and body" {
        $issue = [PSCustomObject]@{
            number    = 7
            title     = "Sample Issue"
            body      = "Issue body"
            state     = "open"
            labels    = @([PSCustomObject]@{ name = "bug" })
            assignees = @()
            author    = [PSCustomObject]@{ login = "alice" }
            milestone = $null
            createdAt = "2025-01-01T00:00:00Z"
            updatedAt = "2025-01-02T00:00:00Z"
            closedAt  = $null
            url       = "https://github.com/o/r/issues/7"
        }
        $md = Format-IssueMarkdown -Issue $issue -Comments @() -Repo "o/r" -Body "Issue body" -IncludeComments $false
        ($md -match 'github_id: 7') | Should Be $true
        ($md -match '# Sample Issue') | Should Be $true
        ($md -match 'Issue body') | Should Be $true
    }
}

Describe "Normalize-GitHubComment" {
    It "maps snake_case API fields to camelCase" {
        $raw = [PSCustomObject]@{
            id         = 9
            body       = "looks good"
            created_at = "2025-01-01T00:00:00Z"
            updated_at = "2025-01-02T00:00:00Z"
            user       = [PSCustomObject]@{ login = "alice" }
        }
        $c = Normalize-GitHubComment -Comment $raw
        $c.updatedAt | Should Be "2025-01-02T00:00:00Z"
        $c.user.login | Should Be "alice"
    }
}

Describe "Normalize-GitHubIssue" {
    It "maps REST API issue to internal shape" {
        $raw = [PSCustomObject]@{
            number       = 12
            title        = "Bug"
            body         = "details"
            state        = "open"
            labels       = @()
            assignees    = @()
            user         = [PSCustomObject]@{ login = "bob" }
            created_at   = "2025-01-01T00:00:00Z"
            updated_at   = "2025-01-02T00:00:00Z"
            closed_at    = $null
            milestone    = $null
            html_url     = "https://github.com/o/r/issues/12"
            pull_request = $null
        }
        $issue = Normalize-GitHubIssue -Issue $raw
        $issue.number | Should Be 12
        $issue.updatedAt | Should Be "2025-01-02T00:00:00Z"
        $issue.isPullRequest | Should Be $false
        $issue.author.login | Should Be "bob"
    }
}

Describe "New-GitHubAuthHeaderValue" {
    It "uses Bearer for GitHub PAT tokens" {
        New-GitHubAuthHeaderValue -Username "x" -Password "ghp_abc123" | Should Be "Bearer ghp_abc123"
    }

    It "uses Basic auth for non-token passwords" {
        $v = New-GitHubAuthHeaderValue -Username "user" -Password "secret"
        ($v -match '^Basic ') | Should Be $true
    }
}

Describe "Get-UrlHash8" {
    It "returns 8 hex chars" {
        $h = Get-UrlHash8 -Url "https://github.com/x.png"
        ($h -match '^[a-f0-9]{8}$') | Should Be $true
    }
}
