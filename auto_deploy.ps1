# HMS Dashboard - Auto Deploy
# Runs every 1 min via Windows Task Scheduler.
# Checks GitHub for new commits; if changed -> downloads app.py & restarts Flask.
# Also auto-restarts Flask if it has crashed.

$repo    = "mac-guru/hms-dashboard"
$branch  = "main"
$workDir = "C:\hms-dashboard"
$appFile = "$workDir\app.py"
$shaFile = "$workDir\.last_sha"
$logFile = "$workDir\deploy.log"
$maxLog  = 200

function Log($msg) {
    $ts   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$ts  $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
    $lines = Get-Content $logFile -ErrorAction SilentlyContinue
    if ($lines.Count -gt $maxLog) {
        $lines | Select-Object -Last $maxLog | Set-Content $logFile
    }
}

function IsFlaskRunning {
    $p = Get-Process python* -ErrorAction SilentlyContinue |
         Where-Object { $_.CommandLine -like "*app.py*" }
    return ($null -ne $p)
}

function StartFlask {
    Start-Process python `
        -WorkingDirectory $workDir `
        -ArgumentList "app.py" `
        -WindowStyle Hidden
    Start-Sleep -Seconds 3
    Log "Flask started."
}

function StopFlask {
    Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
}

Log "--- Check started ---"

# 1. Check GitHub for latest commit SHA
try {
    $headers = @{ "User-Agent" = "HMS-AutoDeploy/1.0" }
    $apiUrl  = "https://api.github.com/repos/$repo/commits/$branch"
    $resp    = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 10
    $newSha  = $resp.sha
    Log "GitHub SHA: $($newSha.Substring(0,7))"
} catch {
    Log "GitHub check failed: $_"
    if (-not (IsFlaskRunning)) {
        Log "Flask not running - restarting (no GitHub response)."
        StartFlask
    }
    exit 0
}

$lastSha = ""
if (Test-Path $shaFile) { $lastSha = (Get-Content $shaFile).Trim() }

# 2. New commit detected -> deploy
if ($newSha -ne $lastSha) {
    Log "New commit: $($newSha.Substring(0,7)) (was $($lastSha.Substring(0,[Math]::Min(7,$lastSha.Length))))"

    $rawUrl = "https://raw.githubusercontent.com/$repo/$branch/app.py"
    try {
        Invoke-WebRequest -Uri $rawUrl -OutFile $appFile -UseBasicParsing
        Log "Downloaded app.py OK"
    } catch {
        Log "Download failed: $_ - aborting deploy."
        exit 1
    }

    StopFlask
    StartFlask

    Set-Content -Path $shaFile -Value $newSha
    Log "Deploy complete - commit $($newSha.Substring(0,7))"

} else {
    # 3. No new code - make sure Flask is alive
    if (-not (IsFlaskRunning)) {
        Log "Flask crashed - restarting (same code, no new commit)."
        StartFlask
    } else {
        Log "No new commit. Flask is running. All OK."
    }
}
