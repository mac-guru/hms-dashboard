# ══════════════════════════════════════════════════════════════════
#  HMS Dashboard — One-Time Task Scheduler Setup
#  Run this ONCE on the Windows server (as Administrator).
#  After this, every git push to main auto-deploys within 5 minutes.
# ══════════════════════════════════════════════════════════════════

$taskName   = "HMS-AutoDeploy"
$scriptPath = "C:\hms-dashboard\auto_deploy.ps1"
$workDir    = "C:\hms-dashboard"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  HMS Dashboard — Auto Deploy Setup" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# ── Verify script exists ───────────────────────────────────────────
if (-not (Test-Path $scriptPath)) {
    Write-Host "✗  auto_deploy.ps1 not found at $scriptPath" -ForegroundColor Red
    Write-Host "   Make sure C:\hms-dashboard exists and auto_deploy.ps1 is there." -ForegroundColor Yellow
    Write-Host "   Download it from: https://raw.githubusercontent.com/mac-guru/hms-dashboard/main/auto_deploy.ps1" -ForegroundColor Yellow
    exit 1
}

# ── Remove old task if it exists ──────────────────────────────────
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "  Removed old task '$taskName'" -ForegroundColor Yellow
}

# ── Define action, trigger, settings ──────────────────────────────
$action = New-ScheduledTaskAction `
    -Execute  "powershell.exe" `
    -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -NonInteractive -File `"$scriptPath`"" `
    -WorkingDirectory $workDir

# Runs every 5 minutes, indefinitely
$trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval  (New-TimeSpan -Minutes 5) `
    -RepetitionDuration  ([TimeSpan]::MaxValue)

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit    (New-TimeSpan -Minutes 3) `
    -RestartCount          3 `
    -RestartInterval       (New-TimeSpan -Minutes 1) `
    -MultipleInstances     IgnoreNew `
    -StartWhenAvailable    $true `
    -RunOnlyIfNetworkAvailable $true

# ── Register task (runs as SYSTEM — no password needed) ───────────
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

# ── Verify & run immediately ───────────────────────────────────────
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "  Task '$taskName' registered successfully." -ForegroundColor Green

    # Kick off the first run right now
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 5

    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Host ""
    Write-Host "  Last run result : $($info.LastTaskResult)" -ForegroundColor Cyan
    Write-Host "  Next run time   : $($info.NextRunTime)"    -ForegroundColor Cyan
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "  Done! Auto-deploy is now active." -ForegroundColor Green
    Write-Host "  Every git push to main deploys in ≤5 min." -ForegroundColor Green
    Write-Host "  Logs → C:\hms-dashboard\deploy.log" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
} else {
    Write-Host "✗  Failed to register task. Try running as Administrator." -ForegroundColor Red
    exit 1
}
