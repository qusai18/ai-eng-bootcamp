$ErrorActionPreference = "Continue"
$repo = "C:\Users\azizk\ai-eng-bootcamp"
$logDir = Join-Path $env:LOCALAPPDATA "ai-eng-bootcamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "github-sync.log"

function Write-Log([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $log -Value $line
}

$git = "C:\Program Files\Git\cmd\git.exe"
if (-not (Test-Path -LiteralPath $git)) {
    $git = "git"
}

Set-Location -LiteralPath $repo
Write-Log "Sync started"

& $git fetch origin
if ($LASTEXITCODE -ne 0) {
    Write-Log "Fetch failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

$branch = (& $git rev-parse --abbrev-ref HEAD).Trim()
$upstream = & $git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $upstream) {
    Write-Log "Branch $branch has no upstream. Nothing to sync."
    exit 0
}
$upstream = $upstream.Trim()

$dirty = & $git status --porcelain
if ($dirty) {
    Write-Log "Working tree has uncommitted changes. Pull skipped so local edits stay untouched."
} else {
    & $git pull --ff-only
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Pull failed (exit $LASTEXITCODE). Push skipped."
        exit $LASTEXITCODE
    }
    Write-Log "Pull completed"
}

& $git push
if ($LASTEXITCODE -ne 0) {
    Write-Log "Push failed (exit $LASTEXITCODE)"
    exit $LASTEXITCODE
}

Write-Log "Push completed for $branch ($upstream)"
Write-Log "Sync finished"
exit 0
