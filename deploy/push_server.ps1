<#
.SYNOPSIS
Publishes the committed code, the trained model and .env.production to a server
and (re)starts the system there with Docker Compose.

.EXAMPLE
.\deploy\push_server.ps1 -Server azureuser@your-label.your-region.cloudapp.azure.com

Builds a clean copy from the last commit (uncommitted changes are not included),
adds models/final.tar.gz, uploads it over SSH, installs Docker on the first run,
and starts the containers. The first build on the server takes 15 to 25 minutes.
#>
param(
    [Parameter(Mandatory = $true)][string]$Server,
    [string]$Key = (Join-Path $HOME ".ssh\azure_airline"),
    [string]$Model = "models\final.tar.gz",
    [string]$EnvFile = ".env.production",
    # Prepare the upload but do not send it
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $Model)) { throw "Trained model not found: $Model. Train it with 'rasa train' first." }
if (-not (Test-Path $EnvFile)) { throw "$EnvFile not found. Copy deploy\env.production.example to $EnvFile and fill it in." }
if (-not (Test-Path $Key)) { throw "SSH key not found: $Key (see docs/deployment.md)." }
if (git status --porcelain) { Write-Warning "You have uncommitted changes; only the last commit is published." }

$tmp = [IO.Path]::GetTempPath()
$stage = Join-Path $tmp "airline-server"
$bundle = Join-Path $tmp "airline-server.tar.gz"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory $stage | Out-Null

# Clean copy of the last commit, plus the model and the server's settings
$archive = Join-Path $tmp "airline-server.zip"
git archive --format=zip -o $archive HEAD
Expand-Archive $archive -DestinationPath $stage
Remove-Item $archive
New-Item -ItemType Directory (Join-Path $stage "models") -Force | Out-Null
Copy-Item $Model (Join-Path $stage "models")
Copy-Item $EnvFile (Join-Path $stage ".env")

tar -czf $bundle -C $stage .
# The staged copy contains the server's secrets, so do not leave it behind
Remove-Item $stage -Recurse -Force
$commit = git rev-parse --short HEAD
if ($DryRun) {
    Write-Host "Dry run: $bundle is ready (commit $commit) and was not uploaded. It contains your secrets; delete it when done."
    return
}

$ssh = @("-i", $Key, "-o", "StrictHostKeyChecking=accept-new")
scp @ssh $bundle "${Server}:/tmp/airline-server.tar.gz"
$uploaded = $LASTEXITCODE -eq 0
Remove-Item $bundle -Force
if (-not $uploaded) { throw "Upload failed. If it timed out, this network may block SSH (port 22); try a phone hotspot." }

# Replace the old copy, keep the database volume, rebuild and restart
$remote = @'
set -e
mkdir -p ~/airline-assistant
cd ~/airline-assistant
find . -mindepth 1 -maxdepth 1 -exec rm -rf {} +
tar -xzf /tmp/airline-server.tar.gz
rm /tmp/airline-server.tar.gz
chmod 600 .env
bash deploy/setup_server.sh
sudo docker compose -f deploy/compose.yaml up -d --build
sudo docker compose -f deploy/compose.yaml ps
'@
ssh @ssh $Server ($remote -replace "`r", "")
if ($LASTEXITCODE) { throw "Starting the system on the server failed" }
Write-Host "Deployed commit $commit. Follow the start-up with:"
Write-Host "  ssh -i $Key $Server sudo docker compose -f airline-assistant/deploy/compose.yaml logs -f app"
