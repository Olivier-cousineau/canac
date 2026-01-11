param(
    [string]$EconoplusPath = "..\\econoplus",
    [string]$EconoplusRepoUrl = "",
    [string]$OutDir = "out_canac_json",
    [string]$CommitMessage = "Update CANAC liquidations"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-AbsolutePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "Path cannot be empty."
    }
    $resolved = Resolve-Path -Path $Path -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
        return $resolved.Path
    }
    return (Join-Path -Path (Get-Location) -ChildPath $Path)
}

$repoPath = Get-AbsolutePath -Path $EconoplusPath
$outPath = Get-AbsolutePath -Path $OutDir

if (-not (Test-Path -Path $repoPath)) {
    if ([string]::IsNullOrWhiteSpace($EconoplusRepoUrl)) {
        throw "Econoplus repo not found at '$repoPath' and no EconoplusRepoUrl provided."
    }
    git clone $EconoplusRepoUrl $repoPath
}

if (-not (Test-Path -Path $outPath)) {
    throw "Output directory '$outPath' not found."
}

git -C $repoPath pull --rebase

$canacPath = Join-Path -Path $repoPath -ChildPath "public\\canac"
if (Test-Path -Path $canacPath) {
    Remove-Item -Path $canacPath -Recurse -Force
}
New-Item -Path $canacPath -ItemType Directory | Out-Null

$copied = $false
$subdirectories = Get-ChildItem -Path $outPath -Directory
foreach ($dir in $subdirectories) {
    $sourceFile = Join-Path -Path $dir.FullName -ChildPath "liquidations.json"
    if (-not (Test-Path -Path $sourceFile)) {
        continue
    }
    $destinationDir = Join-Path -Path $canacPath -ChildPath $dir.Name
    New-Item -Path $destinationDir -ItemType Directory -Force | Out-Null
    Copy-Item -Path $sourceFile -Destination (Join-Path -Path $destinationDir -ChildPath "liquidations.json") -Force
    $copied = $true
}

$rootJsonFiles = Get-ChildItem -Path $outPath -File -Filter "*.json"
foreach ($file in $rootJsonFiles) {
    $slug = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $destinationDir = Join-Path -Path $canacPath -ChildPath $slug
    New-Item -Path $destinationDir -ItemType Directory -Force | Out-Null
    Copy-Item -Path $file.FullName -Destination (Join-Path -Path $destinationDir -ChildPath "liquidations.json") -Force
    $copied = $true
}

if (-not $copied) {
    throw "No liquidation JSON files were copied. Check the out_canac_json structure."
}

$gitName = git -C $repoPath config user.name
if ([string]::IsNullOrWhiteSpace($gitName)) {
    $defaultName = if ($env:GIT_USER_NAME) { $env:GIT_USER_NAME } else { "canac-bot" }
    git -C $repoPath config user.name $defaultName
}

$gitEmail = git -C $repoPath config user.email
if ([string]::IsNullOrWhiteSpace($gitEmail)) {
    $defaultEmail = if ($env:GIT_USER_EMAIL) { $env:GIT_USER_EMAIL } else { "canac-bot@users.noreply.github.com" }
    git -C $repoPath config user.email $defaultEmail
}

git -C $repoPath add public/canac

$changes = git -C $repoPath status --porcelain
if (-not [string]::IsNullOrWhiteSpace($changes)) {
    git -C $repoPath commit -m $CommitMessage
    git -C $repoPath push
} else {
    Write-Host "No changes to commit."
}
