param(
    [string]$Host = $env:UFC_EC2_HOST,
    [string]$User = $env:UFC_EC2_USER,
    [string]$KeyPath = $env:UFC_EC2_KEY_PATH,
    [string]$RemoteDir = $env:UFC_EC2_APP_DIR,
[string]$Env = "prod",
[switch]$RestartService
)

$ErrorActionPreference = "Stop"
$origin = Get-Location

function Require-Cmd($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "$name is required but not found in PATH."
    }
}

if (-not $Host) { throw "Set UFC_EC2_HOST env var or pass -Host (public DNS or IP)." }
if (-not $KeyPath) { throw "Set UFC_EC2_KEY_PATH env var or pass -KeyPath (path to .pem)." }
if (-not (Test-Path $KeyPath)) { throw "Key file not found: $KeyPath" }
if (-not $User) { $User = "ubuntu" }
if (-not $RemoteDir) { $RemoteDir = "/opt/ufc-app" }

Require-Cmd ssh
Require-Cmd scp
Require-Cmd tar

$envName = $Env.ToLower()
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

try {
    Set-Location $repoRoot

    $tempArchive = Join-Path $env:TEMP ("ufc_sync_{0:yyyyMMdd_HHmmss}.tar.gz" -f (Get-Date))

    # Build tar command that includes the whole repo but excludes local-only artifacts.
    $tarArgs = @(
        "-czf", $tempArchive,
        "--exclude=.git",
        "--exclude=.venv",
        "--exclude=battles",
        "--exclude=sessions",
        "--exclude=__pycache__",
        "--exclude=*.pyc",
        "--exclude=*.pyo",
        "--exclude=*.log",
        "--exclude=.env",                 # keep remote prod secrets
        "--exclude=data/dev",             # skip dev data
        "--exclude=data/*/last_run*",     # skip transient backups
        "--exclude=assets/fight_theme*.mp3" # optional large audio
    )

    # If a specific env is requested, ensure its data folder exists so it’s included.
    $envData = Join-Path "data" $envName
    if (-not (Test-Path $envData)) {
        Write-Warning "Data folder not found: $envData (continuing without it)"
    }

    # Add entire repo; excludes handle the rest.
    $tarArgs += "."
    tar @tarArgs
    Write-Host "Created archive (code + data/$envName + follower_pp): $tempArchive"

    $remoteTmp = "/tmp/ufc_sync.tar.gz"
    scp -i $KeyPath $tempArchive "$User@$Host:$remoteTmp"
    Write-Host "Uploaded archive to $Host:$remoteTmp"

    $remoteCmd = @(
        "set -e"
        "mkdir -p $RemoteDir"
        "cd $RemoteDir"
        "tar -xzf $remoteTmp -C $RemoteDir"
        "rm -f $remoteTmp"
    )
    if ($RestartService) {
        $remoteCmd += "sudo systemctl restart ufc-streamlit"
    }

    $joined = ($remoteCmd -join "; ")
    ssh -i $KeyPath "$User@$Host" $joined
    Write-Host "Sync complete."
} finally {
    if ($tempArchive -and (Test-Path $tempArchive)) {
        Remove-Item $tempArchive -Force -ErrorAction SilentlyContinue
    }
    Set-Location $origin
}
