[CmdletBinding()]
param(
    [string]$RepositoryPath = (Get-Location).Path,
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$RemoteUrl = "https://github.com/MashmanAU/jg-energy-manager.git",
    [string]$CommitMessage = "Release v0.3.2",
    [switch]$NoPush,
    [switch]$ForceTag
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ExpectedVersion = "0.3.2"

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Native {
    param([string]$File, [string[]]$Arguments, [string]$WorkingDirectory)
    Push-Location $WorkingDirectory
    try {
        & $File @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$File $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
        }
    }
    finally { Pop-Location }
}

function Get-Python {
    foreach ($candidate in @("python", "python3", "py")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    throw "Python 3.12 or later is required."
}

$RepoRoot = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $RepositoryPath).Path)
$ManifestPath = Join-Path $RepoRoot "custom_components\jg_energy_manager\manifest.json"
if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "RepositoryPath is not a JG Energy Manager package: $RepoRoot"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is required. Install Git for Windows and retry."
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.version -ne $ExpectedVersion) {
    throw "Expected manifest version $ExpectedVersion; found $($manifest.version)."
}
$Tag = "v$ExpectedVersion"
$Python = Get-Python

Write-Step "Validating package structure, versions and sensitive-file exclusions"
Invoke-Native -File $Python -Arguments @("scripts/validate_package.py") -WorkingDirectory $RepoRoot

Write-Step "Running controller tests"
& $Python -c "import pytest" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pytest is not installed; installing it for the current user." -ForegroundColor Yellow
    Invoke-Native -File $Python -Arguments @("-m", "pip", "install", "--user", "pytest") -WorkingDirectory $RepoRoot
}
Invoke-Native -File $Python -Arguments @("-m", "pytest") -WorkingDirectory $RepoRoot

Write-Step "Building HACS and manual-install archives"
Invoke-Native -File $Python -Arguments @("scripts/build_release.py") -WorkingDirectory $RepoRoot
Get-ChildItem -LiteralPath (Join-Path $RepoRoot "dist") | Format-Table Name, Length

if ($NoPush) {
    Write-Host "`nValidation and packaging completed. -NoPush prevented Git changes." -ForegroundColor Green
    exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".git") -PathType Container)) {
    Write-Step "Initialising Git repository"
    Invoke-Native -File "git" -Arguments @("init", "-b", $Branch) -WorkingDirectory $RepoRoot
}

$remoteNames = @(& git -C $RepoRoot remote)
if ($remoteNames -contains $Remote) {
    $currentUrl = (& git -C $RepoRoot remote get-url $Remote).Trim()
    if ($currentUrl -ne $RemoteUrl) {
        Write-Step "Updating $Remote remote"
        Invoke-Native -File "git" -Arguments @("remote", "set-url", $Remote, $RemoteUrl) -WorkingDirectory $RepoRoot
    }
}
else {
    Write-Step "Adding $Remote remote"
    Invoke-Native -File "git" -Arguments @("remote", "add", $Remote, $RemoteUrl) -WorkingDirectory $RepoRoot
}

$userName = "$(& git -C $RepoRoot config user.name)".Trim()
$userEmail = "$(& git -C $RepoRoot config user.email)".Trim()
if ([string]::IsNullOrWhiteSpace($userName) -or [string]::IsNullOrWhiteSpace($userEmail)) {
    throw "Configure git user.name and user.email before publishing."
}

Write-Step "Staging repository"
Invoke-Native -File "git" -Arguments @("add", "--all") -WorkingDirectory $RepoRoot
& git -C $RepoRoot diff --cached --quiet
$hasChanges = $LASTEXITCODE -ne 0
if ($hasChanges) {
    Invoke-Native -File "git" -Arguments @("commit", "-m", $CommitMessage) -WorkingDirectory $RepoRoot
}
else {
    Write-Host "No uncommitted changes; using the existing HEAD commit."
}

$currentBranch = "$(& git -C $RepoRoot branch --show-current)".Trim()
if ($currentBranch -ne $Branch) {
    Invoke-Native -File "git" -Arguments @("branch", "-M", $Branch) -WorkingDirectory $RepoRoot
}

$existingTag = "$(& git -C $RepoRoot tag --list $Tag)".Trim()
if ($existingTag) {
    $tagCommit = (& git -C $RepoRoot rev-list -n 1 $Tag).Trim()
    $headCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
    if ($tagCommit -ne $headCommit) {
        if (-not $ForceTag) {
            throw "Tag $Tag already points to another commit. Use -ForceTag only for a deliberate replacement."
        }
        Invoke-Native -File "git" -Arguments @("tag", "-d", $Tag) -WorkingDirectory $RepoRoot
        Invoke-Native -File "git" -Arguments @("tag", "-a", $Tag, "-m", "JG Energy Manager $ExpectedVersion") -WorkingDirectory $RepoRoot
        Invoke-Native -File "git" -Arguments @("push", $Remote, ":refs/tags/$Tag") -WorkingDirectory $RepoRoot
    }
}
else {
    Invoke-Native -File "git" -Arguments @("tag", "-a", $Tag, "-m", "JG Energy Manager $ExpectedVersion") -WorkingDirectory $RepoRoot
}

Write-Step "Pushing $Branch and $Tag to the private GitHub repository"
Invoke-Native -File "git" -Arguments @("push", "-u", $Remote, $Branch) -WorkingDirectory $RepoRoot
Invoke-Native -File "git" -Arguments @("push", $Remote, $Tag) -WorkingDirectory $RepoRoot

Write-Host "`nPublished JG Energy Manager $ExpectedVersion to $RemoteUrl" -ForegroundColor Green
