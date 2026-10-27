# Schedule a project to run weekly in Windows Task Scheduler (runs hidden, as you).
# Usage:  .\schedule-project.ps1 weekly_sales_email -Day Monday -At 8am
# Remove: Unregister-ScheduledTask -TaskName "Automation - weekly_sales_email"
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$Day = "Monday",
    [string]$At = "8am"
)

if (-not (Test-Path (Join-Path $PSScriptRoot "projects\$Name\main.py"))) {
    Write-Error "No project named '$Name' in projects\."
    exit 1
}

$taskName = "Automation - $Name"
$action = New-ScheduledTaskAction -Execute (Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe") `
    -Argument "-m projects.$Name.main" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
# StartWhenAvailable: if the PC was off at the scheduled time, run at next startup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "automation-toolkit project: $Name" -Force | Out-Null

$next = (Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo).NextRunTime
Write-Host "Scheduled '$taskName' - next run: $next"
Write-Host "Logs: logs\$Name.log"
