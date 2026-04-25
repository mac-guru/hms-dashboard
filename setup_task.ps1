# HMS Dashboard - One-Time Task Scheduler Setup
# Run this ONCE on the Windows server (as Administrator).
# After this, every git push to main auto-deploys within 1 minute.

$taskName   = "HMS-AutoDeploy"
$scriptPath = "C:\hms-dashboard\auto_deploy.ps1"
$workDir    = "C:\hms-dashboard"

Write-Host ""
Write-Host "HMS Dashboard - Auto Deploy Setup" -ForegroundColor Cyan
Write-Host "-----------------------------------" -ForegroundColor Cyan
Write-Host ""

# Verify script exists
if (-not (Test-Path $scriptPath)) {
    Write-Host "ERROR: auto_deploy.ps1 not found at $scriptPath" -ForegroundColor Red
    exit 1
}

# Remove old task if it exists
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed old task '$taskName'" -ForegroundColor Yellow
}

# Action
$action = New-ScheduledTaskAction `
    -Execute  "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -NonInteractive -File `"$scriptPath`"" `
    -WorkingDirectory $workDir

# Runs every 1 minute, indefinitely
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval  (New-TimeSpan -Minutes 1) `
    -RepetitionDuration  ([TimeSpan]::MaxValue)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit    (New-TimeSpan -Minutes 3) `
    -RestartCount          3 `
    -RestartInterval       (New-TimeSpan -Minutes 1) `
    -MultipleInstances     IgnoreNew `
    -StartWhenAvailable    $true `
    -RunOnlyIfNetworkAvailable $true

# Register task as SYSTEM (no password needed)
$principal = New-ScheduledTaskPrincipal `
    -UserId    "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel  Highest

Register-ScheduledTask `
    -TaskName   $taskName `
    -Action     $action `
    -Trigger    $trigger `
    -Settings   $settings `
    -Principal  $principal `
    -Force | Out-Null

# Verify and run immediately
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "Task '$taskName' registered OK." -ForegroundColor Green
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 5
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Host "Last run result : $($info.LastTaskResult)" -ForegroundColor Cyan
    Write-Host "Next run time   : $($info.NextRunTime)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Done! Auto-deploy active. Every push deploys in 1 min." -ForegroundColor Green
    Write-Host "Logs: C:\hms-dashboard\deploy.log" -ForegroundColor Green
} else {
    Write-Host "ERROR: Failed to register task. Run as Administrator." -ForegroundColor Red
    exit 1
}
