<#
.SYNOPSIS
Publishes the committed code and the trained model to a Hugging Face Docker Space.

.EXAMPLE
.\deploy\push_space.ps1 -Space your-hf-username/airline-assistant

Builds a clean copy from the last commit (uncommitted changes are not included),
adds models/final.tar.gz, and force-pushes it to the Space's own Git repository.
Git asks for your Hugging Face username and an access token with write permission
the first time. The Space then rebuilds and restarts by itself.
#>
param(
    [Parameter(Mandatory = $true)][string]$Space,
    [string]$Model = "models\final.tar.gz",
    # Prepare and commit the Space copy but do not push it
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $Model)) { throw "Trained model not found: $Model. Train it with 'rasa train' first." }
if (git status --porcelain) { Write-Warning "You have uncommitted changes; only the last commit is published." }

$stage = Join-Path ([IO.Path]::GetTempPath()) "airline-space"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory $stage | Out-Null

# Clean copy of the last commit
$archive = Join-Path ([IO.Path]::GetTempPath()) "airline-space.zip"
git archive --format=zip -o $archive HEAD
Expand-Archive $archive -DestinationPath $stage
Remove-Item $archive

# The Space needs the Dockerfile and its own README at the top level
Move-Item (Join-Path $stage "README.md") (Join-Path $stage "PROJECT_README.md")
Copy-Item deploy\Dockerfile (Join-Path $stage "Dockerfile")
Copy-Item deploy\space_README.md (Join-Path $stage "README.md")
New-Item -ItemType Directory (Join-Path $stage "models") -Force | Out-Null
Copy-Item $Model (Join-Path $stage "models")

# Hugging Face rejects binary files that are not stored with Git LFS
@"

# Added for the Hugging Face Space
*.tar.gz filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
"@ | Add-Content (Join-Path $stage ".gitattributes") -Encoding ascii

$commit = git rev-parse --short HEAD
Push-Location $stage
try {
    git init -q -b main
    git config core.autocrlf false
    git lfs install --local | Out-Null
    git add -A
    # .gitignore excludes models/, but the Space needs the trained model
    git add -f models
    git commit -q -m "Deploy $commit"
    if ($DryRun) {
        Write-Host "Dry run: the Space copy is ready in $stage and was not pushed."
        return
    }
    git push --force "https://huggingface.co/spaces/$Space" main
}
finally {
    Pop-Location
}
Write-Host "Pushed commit $commit. Follow the build at https://huggingface.co/spaces/$Space"
