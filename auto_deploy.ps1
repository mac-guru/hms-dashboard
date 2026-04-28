# HMS Dashboard - Auto Deploy
# Runs every 1 min via Windows Task Scheduler.
# Pulls latest app.py from GitHub when commit changes, then restarts
# the HMSDashboard Windows service (which runs waitress on port 5055).
# Also auto-restarts the service if it has crashed and kills any
# stray "python app.py" instances that older versions of this script
# may have spawned.

$repo        = "mac-guru/hms-dashboard"
$branch      = "main"
$workDir     = "C:\hms-dashboard"
$appFile     = "$workDir\app.py"
$shaFile     = "$workDir\.last_sha"
$logFile     = "$workDir\deploy.log"
$serviceName = "HMSDashboard"
$port        = 5055
$maxLog      = 200

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

# ── Health: did the service end up serving on $port? ─────────────
function IsServingOnPort {
    $listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return ($null -ne $listening -and ($listening | Where-Object { $_.LocalAddress -eq '0.0.0.0' -or $_.LocalAddress -eq '::' }))
}

function IsServiceRunning {
    $svc = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    return ($null -ne $svc -and $svc.Status -eq 'Running')
}

# ── Kill orphan "python app.py" instances (NOT waitress). ────────
function KillStrayDevServers {
    $strays = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
              Where-Object {
                  $_.CommandLine -and
                  $_.CommandLine -like "*app.py*" -and
                  $_.CommandLine -notlike "*waitress*"
              }
    foreach ($p in $strays) {
        Log "Killing stray python app.py PID=$($p.ProcessId)"
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function RestartService($reason) {
    Log "Restarting $serviceName ($reason)"
    Restart-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
    KillStrayDevServers
}

function StartServiceIfStopped {
    if (-not (IsServiceRunning)) {
        Log "$serviceName is not Running; starting"
        Start-Service -Name $serviceName -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 5
    }
}

Log "--- Check started ---"

# Always clean up any lingering dev-server orphans first.
KillStrayDevServers

# 1. Check GitHub for latest commit SHA
try {
    $headers = @{ "User-Agent" = "HMS-AutoDeploy/1.0" }
    $apiUrl  = "https://api.github.com/repos/$repo/commits/$branch"
    $resp    = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 10
    $newSha  = $resp.sha
    Log "GitHub SHA: $($newSha.Substring(0,7))"
} catch {
    Log "GitHub check failed: $_"
    StartServiceIfStopped
    if (-not (IsServingOnPort)) { RestartService "no listener on $port (no GitHub)" }
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

    RestartService "new commit $($newSha.Substring(0,7))"
    Set-Content -Path $shaFile -Value $newSha
    Log "Deploy complete - commit $($newSha.Substring(0,7))"

} else {
    # 3. No new code - make sure the service is alive AND serving on port
    StartServiceIfStopped
    if (-not (IsServingOnPort)) {
        RestartService "no listener on $port"
    } else {
        Log "No new commit. Service running and listening on $port. All OK."
    }
}
