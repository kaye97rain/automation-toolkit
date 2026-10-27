# Create a new automation project from the template.
# Usage:  .\new-project.ps1 invoice_processor
param([Parameter(Mandatory = $true)][string]$Name)

if ($Name -notmatch '^[a-z][a-z0-9_]*$') {
    Write-Error "Use lowercase letters, digits and underscores only (e.g. invoice_processor)."
    exit 1
}

$dest = Join-Path $PSScriptRoot "projects\$Name"
if (Test-Path $dest) {
    Write-Error "Project '$Name' already exists."
    exit 1
}

New-Item -ItemType Directory -Path $dest | Out-Null
$template = Get-Content (Join-Path $PSScriptRoot "templates\project_template\main.py") -Raw
$template.Replace("__PROJECT__", $Name) | Set-Content (Join-Path $dest "main.py") -Encoding utf8

Write-Host "Created projects\$Name\main.py"
Write-Host "Run it with:  python -m projects.$Name.main"
