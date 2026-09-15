<#
.SYNOPSIS
    Patient Watchdog and Heartbeat Monitor for Naukri Unattended Auto-Apply Bot.

.DESCRIPTION
    1. Monitors naukri_bot.log and the active python.exe run_naukri_unattended.py process.
    2. Updates naukri_heartbeat.txt whenever progress lines appear:
       - 'Application \d+ successful'
       - 'Save submission CONFIRMED'
       - 'Found \d+ new jobs'
       - 'Page \d+'
    3. Detects "Stuck" states:
       - Bot process alive but heartbeat has not advanced for > 60 minutes.
       - Explicit fatal error lines appear ('All login attempts failed', 'Session recovery failed.*Stopping').
    4. Implements Patient Alerting:
       - Enforces a 10-minute soft re-check before triggering an alert.
       - Dispatches a Windows notification balloon via System.Windows.Forms.NotifyIcon:
         "Naukri Bot Alert: [Reason]"
       - Tracks notification state in naukri_watchdog.state.json with a strict 4-hour cooldown
         to prevent spamming the user.
    5. Supports -TestNotification to verify the balloon alert system.
    6. Supports -SinglePass for integration with Task Scheduler or orchestrators.

.PARAMETER SinglePass
    Run a single evaluation pass and exit cleanly.

.PARAMETER TestNotification
    Fire a test Windows balloon notification immediately to verify delivery, then exit.

.PARAMETER StuckThresholdMinutes
    Minutes of inactive heartbeat before flagging as stuck (default: 60).

.PARAMETER SoftRecheckMinutes
    Minutes to wait and verify stuck condition before alerting (default: 10).

.PARAMETER CooldownHours
    Minimum hours between balloon notifications to avoid spam (default: 4).

.PARAMETER LoopIntervalSeconds
    Seconds to wait between checks in continuous loop mode (default: 60).

.PARAMETER Status
    Display live status of bot process, heartbeat, and watchdog state without mutating.
#>

[CmdletBinding()]
param(
    [switch]$SinglePass,
    [switch]$TestNotification,
    [int]$StuckThresholdMinutes = 60,
    [int]$SoftRecheckMinutes = 10,
    [int]$CooldownHours = 4,
    [int]$LoopIntervalSeconds = 60,
    [switch]$Status,
    [string]$Profile = "default"
)

$ErrorActionPreference = "Continue"

# ---------------------------------------------------------------- Configuration
$RepoDir = $PSScriptRoot
if (-not $RepoDir) {
    $RepoDir = (Split-Path -Parent $MyInvocation.MyCommand.Path)
}
if (-not $RepoDir) {
    $RepoDir = "C:\Users\Admin\GitHub\Naukri-autoapply-bot-for-claude"
}

if ($Profile -and $Profile -ne "default" -and $Profile -ne "profile1") {
    $ProfileDir      = Join-Path $RepoDir "profiles\$Profile"
    New-Item -ItemType Directory -Force -Path $ProfileDir -ErrorAction SilentlyContinue | Out-Null
    $BotLogPath      = Join-Path $ProfileDir "naukri_bot.log"
    $HeartbeatPath   = Join-Path $ProfileDir "naukri_heartbeat.txt"
    $StatePath       = Join-Path $ProfileDir "naukri_watchdog.state.json"
    $WatchdogLogPath = Join-Path $ProfileDir "naukri_watchdog.log"
} else {
    $BotLogPath      = Join-Path $RepoDir "naukri_bot.log"
    $HeartbeatPath   = Join-Path $RepoDir "naukri_heartbeat.txt"
    $StatePath       = Join-Path $RepoDir "naukri_watchdog.state.json"
    $WatchdogLogPath = Join-Path $RepoDir "naukri_watchdog.log"
}

$ProgressPattern = 'Application \d+ successful|Save submission CONFIRMED|Found \d+ new jobs|Page \d+'
$FatalPattern    = 'All login attempts failed|Session recovery failed'

# ---------------------------------------------------------------- Logging
function Write-WatchdogLog {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"

    $color = switch ($Level) {
        "ERROR" { "Red" }
        "WARN"  { "Yellow" }
        "OK"    { "Green" }
        default { "Cyan" }
    }
    Write-Host $line -ForegroundColor $color

    try {
        Add-Content -Path $WatchdogLogPath -Value $line -Encoding utf8 -ErrorAction SilentlyContinue
        
        # Self-trimming pattern from N01: keep last 500 lines if > 200KB
        if (Test-Path $WatchdogLogPath) {
            $f = Get-Item $WatchdogLogPath -ErrorAction SilentlyContinue
            if ($f -and $f.Length -gt 200KB) {
                $lines = Get-Content -Path $WatchdogLogPath -Tail 500 -ErrorAction SilentlyContinue
                Set-Content -Path $WatchdogLogPath -Value $lines -Encoding utf8 -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

# ---------------------------------------------------------------- Balloon Notification
function Send-BalloonNotification {
    param(
        [string]$Title = "Naukri Bot Alert",
        [string]$Message = "Naukri Bot alert triggered.",
        [System.Windows.Forms.ToolTipIcon]$Icon = [System.Windows.Forms.ToolTipIcon]::Warning,
        [int]$TimeoutMs = 5000
    )
    $notify = $null
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
        Add-Type -AssemblyName System.Drawing -ErrorAction SilentlyContinue

        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Warning
        $notify.BalloonTipTitle = $Title
        $notify.BalloonTipText = $Message
        $notify.BalloonTipIcon = $Icon
        $notify.Visible = $true
        $notify.ShowBalloonTip($TimeoutMs)

        # Allow the Windows Shell notification balloon to pop
        Start-Sleep -Milliseconds 1500
    } catch {
        Write-WatchdogLog "Failed to dispatch balloon notification: $_" "ERROR"
    } finally {
        if ($notify) {
            $notify.Visible = $false
            $notify.Dispose()
        }
    }
}

# ---------------------------------------------------------------- State Management
function Get-WatchdogState {
    if (Test-Path $StatePath) {
        try {
            $raw = Get-Content -Path $StatePath -Raw -ErrorAction SilentlyContinue
            if ($raw) {
                return ($raw | ConvertFrom-Json)
            }
        } catch {}
    }
    return [PSCustomObject]@{
        LastHeartbeatTime      = $null
        LastHeartbeatLine      = $null
        SuspectedStuckSince    = $null
        SuspectedReason        = $null
        LastNotificationTime   = $null
        LastNotificationReason = $null
    }
}

function Save-WatchdogState {
    param($State)
    try {
        $json = $State | ConvertTo-Json -Depth 5
        Set-Content -Path $StatePath -Value $json -Encoding utf8 -ErrorAction SilentlyContinue
    } catch {}
}

# ---------------------------------------------------------------- Process Inspection
function Get-BotProcess {
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -like "*run_naukri_unattended.py*" -and
            (
                ($Profile -eq "default" -and $_.CommandLine -notlike "*--profile*") -or
                ($Profile -ne "default" -and $_.CommandLine -like "*--profile $Profile*")
            )
        }
    return $procs
}

# ---------------------------------------------------------------- Heartbeat Sync
function Update-Heartbeat {
    param(
        $State,
        $ActiveProc
    )
    $now = Get-Date

    # 1. Inspect naukri_bot.log for progress lines
    if (Test-Path $BotLogPath) {
        $lines = Get-Content -Path $BotLogPath -Tail 500 -ErrorAction SilentlyContinue
        if ($lines) {
            # Search backwards for the newest progress line
            for ($i = $lines.Count - 1; $i -ge 0; $i--) {
                $line = $lines[$i]
                if ($line -match $ProgressPattern) {
                    if ($line -match '^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})') {
                        try {
                            $lineTime = [datetime]::ParseExact($matches[1], "yyyy-MM-dd HH:mm:ss", [System.Globalization.CultureInfo]::InvariantCulture)
                            $currentTime = if ($State.LastHeartbeatTime) { [datetime]$State.LastHeartbeatTime } else { [datetime]::MinValue }
                            
                            if ($lineTime -gt $currentTime) {
                                $State.LastHeartbeatTime = $lineTime.ToString("o")
                                $State.LastHeartbeatLine = $line.Trim()
                                
                                # Write to naukri_heartbeat.txt
                                $hbText = @"
Timestamp: $($lineTime.ToString("yyyy-MM-dd HH:mm:ss"))
Line: $($line.Trim())
Updated: $($now.ToString("yyyy-MM-dd HH:mm:ss"))
"@
                                Set-Content -Path $HeartbeatPath -Value $hbText -Encoding utf8 -ErrorAction SilentlyContinue
                                Write-WatchdogLog "Heartbeat updated from log: $($lineTime.ToString('yyyy-MM-dd HH:mm:ss')) | $($line.Trim())" "INFO"
                                break
                            }
                        } catch {}
                    }
                }
            }
        }
    }

    # 2. If heartbeat file exists but state is empty, initialize state from file
    if (-not $State.LastHeartbeatTime -and (Test-Path $HeartbeatPath)) {
        try {
            $hbContent = Get-Content -Path $HeartbeatPath -ErrorAction SilentlyContinue
            foreach ($hbLine in $hbContent) {
                if ($hbLine -match '^Timestamp:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})') {
                    $dt = [datetime]::ParseExact($matches[1], "yyyy-MM-dd HH:mm:ss", [System.Globalization.CultureInfo]::InvariantCulture)
                    $State.LastHeartbeatTime = $dt.ToString("o")
                    break
                }
            }
        } catch {}
    }

    # 3. If bot is alive, ensure heartbeat is not older than process start time
    if ($ActiveProc -ne $null) {
        $procStart = $ActiveProc.CreationDate
        $currentHb = if ($State.LastHeartbeatTime) { [datetime]$State.LastHeartbeatTime } else { [datetime]::MinValue }
        if ($procStart -gt $currentHb) {
            # Bot was restarted recently; anchor heartbeat to process start so fresh runs are never falsely flagged
            $State.LastHeartbeatTime = $procStart.ToString("o")
            $State.LastHeartbeatLine = "Bot Process Started (PID $($ActiveProc.ProcessId))"
            
            $hbText = @"
Timestamp: $($procStart.ToString("yyyy-MM-dd HH:mm:ss"))
Line: Bot Process Started (PID $($ActiveProc.ProcessId))
Updated: $($now.ToString("yyyy-MM-dd HH:mm:ss"))
"@
            Set-Content -Path $HeartbeatPath -Value $hbText -Encoding utf8 -ErrorAction SilentlyContinue
            Write-WatchdogLog "Heartbeat anchored to bot process start time: $($procStart.ToString('yyyy-MM-dd HH:mm:ss')) (PID $($ActiveProc.ProcessId))" "INFO"
        }
    }

    Save-WatchdogState $State
    return $State
}

# ---------------------------------------------------------------- Core Watchdog Pass
function Invoke-WatchdogPass {
    $state = Get-WatchdogState
    $now = Get-Date

    # 1. Check running process
    $runningProcs = Get-BotProcess
    $isRunning = ($runningProcs -ne $null -and $runningProcs.Count -gt 0)
    $activeProc = if ($isRunning) { $runningProcs[0] } else { $null }

    # 2. Update heartbeat
    $state = Update-Heartbeat -State $state -ActiveProc $activeProc

    $lastHbTime = if ($state.LastHeartbeatTime) { [datetime]$state.LastHeartbeatTime } else { $null }
    $heartbeatAgeMin = if ($lastHbTime) { [math]::Round(($now - $lastHbTime).TotalMinutes, 1) } else { 0 }

    # Handle Status request
    if ($Status) {
        Write-Host ""
        Write-Host "==================== NAUKRI WATCHDOG STATUS ====================" -ForegroundColor Cyan
        if ($isRunning) {
            Write-Host "Process State       : RUNNING (PID $($activeProc.ProcessId), Started: $($activeProc.CreationDate))" -ForegroundColor Green
        } else {
            Write-Host "Process State       : NOT RUNNING" -ForegroundColor Yellow
        }
        Write-Host "Last Heartbeat Time : $($state.LastHeartbeatTime) ($heartbeatAgeMin min ago)" -ForegroundColor White
        Write-Host "Last Heartbeat Line : $($state.LastHeartbeatLine)" -ForegroundColor White
        Write-Host "Suspected Stuck     : $($state.SuspectedStuckSince) (Reason: $($state.SuspectedReason))" -ForegroundColor White
        Write-Host "Last Notification   : $($state.LastNotificationTime) (Reason: $($state.LastNotificationReason))" -ForegroundColor White
        Write-Host "================================================================" -ForegroundColor Cyan
        return
    }

    # 3. Check for Fatal Errors in recent log
    $fatalErrorFound = $false
    $fatalReason = $null
    if (Test-Path $BotLogPath) {
        $recentLines = Get-Content -Path $BotLogPath -Tail 200 -ErrorAction SilentlyContinue
        if ($recentLines) {
            for ($j = $recentLines.Count - 1; $j -ge 0; $j--) {
                $chkLine = $recentLines[$j]
                if ($chkLine -match $FatalPattern) {
                    if ($chkLine -match '^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})') {
                        try {
                            $errDt = [datetime]::ParseExact($matches[1], "yyyy-MM-dd HH:mm:ss", [System.Globalization.CultureInfo]::InvariantCulture)
                            # Only treat as fatal if occurred during current process lifetime or within last 60m
                            $minTime = if ($activeProc) { $activeProc.CreationDate } else { $now.AddMinutes(-60) }
                            if ($errDt -ge $minTime) {
                                $fatalErrorFound = $true
                                $fatalReason = "Fatal log error: $($chkLine.Trim())"
                                break
                            }
                        } catch {}
                    }
                }
            }
        }
    }

    # 4. Stuck Detection
    $isStuck = $false
    $stuckReason = $null

    if ($fatalErrorFound) {
        $isStuck = $true
        $stuckReason = $fatalReason
    } elseif ($isRunning -and $heartbeatAgeMin -gt $StuckThresholdMinutes) {
        $isStuck = $true
        $stuckReason = "Bot process alive (PID $($activeProc.ProcessId)) but heartbeat stalled for ${heartbeatAgeMin}m (threshold: ${StuckThresholdMinutes}m)"
    }

    # 5. Patient Alerting
    if ($isStuck) {
        if (-not $state.SuspectedStuckSince) {
            # First detection -> Arm soft re-check window (+10 minutes)
            $state.SuspectedStuckSince = $now.ToString("o")
            $state.SuspectedReason = $stuckReason
            Save-WatchdogState $state
            Write-WatchdogLog "Stuck detected: $stuckReason. Soft re-check window (+${SoftRecheckMinutes}m) initiated before alerting." "WARN"
        } else {
            # Stuck was already suspected -> check duration
            $suspectDurationMin = [math]::Round(($now - [datetime]$state.SuspectedStuckSince).TotalMinutes, 1)
            if ($suspectDurationMin -lt $SoftRecheckMinutes) {
                Write-WatchdogLog "Stuck condition persists ($stuckReason). Soft re-check in progress (${suspectDurationMin} / ${SoftRecheckMinutes}m elapsed). Alert withheld." "WARN"
            } else {
                # Soft re-check elapsed and STILL stuck -> evaluate 4-hour cooldown
                $canAlert = $true
                if ($state.LastNotificationTime) {
                    $hoursSinceAlert = [math]::Round(($now - [datetime]$state.LastNotificationTime).TotalHours, 2)
                    if ($hoursSinceAlert -lt $CooldownHours) {
                        $canAlert = $false
                        Write-WatchdogLog "Stuck confirmed after soft re-check, but 4-hour cooldown is ACTIVE (${hoursSinceAlert}h / ${CooldownHours}h elapsed). Notification suppressed." "WARN"
                    }
                }

                if ($canAlert) {
                    Write-WatchdogLog "ALERT TRIGGERED: Stuck confirmed after ${SoftRecheckMinutes}m re-check ($stuckReason). Firing balloon notification." "ERROR"
                    Send-BalloonNotification -Title "Naukri Bot Alert" -Message $stuckReason -Icon ([System.Windows.Forms.ToolTipIcon]::Error)
                    $state.LastNotificationTime = $now.ToString("o")
                    $state.LastNotificationReason = $stuckReason
                    $state.SuspectedStuckSince = $null
                    $state.SuspectedReason = $null
                    Save-WatchdogState $state
                }
            }
        }
    } else {
        # Not stuck (progress active or healthy)
        if ($state.SuspectedStuckSince) {
            Write-WatchdogLog "Bot progress resumed or recovered. Clearing suspected stuck condition." "OK"
            $state.SuspectedStuckSince = $null
            $state.SuspectedReason = $null
            Save-WatchdogState $state
        } else {
            if ($isRunning) {
                Write-WatchdogLog "Bot healthy (PID $($activeProc.ProcessId)). Heartbeat age: ${heartbeatAgeMin}m (threshold: ${StuckThresholdMinutes}m)." "OK"
            } else {
                Write-WatchdogLog "Bot is not running. Heartbeat age: ${heartbeatAgeMin}m." "INFO"
            }
        }
    }
}

# ---------------------------------------------------------------- Execution
if ($TestNotification) {
    Write-WatchdogLog "Testing Windows balloon notification..." "INFO"
    Send-BalloonNotification -Title "Naukri Bot Alert" -Message "Test Notification: Windows balloon notification verified successfully." -Icon ([System.Windows.Forms.ToolTipIcon]::Info)
    Write-WatchdogLog "Test notification successfully sent." "OK"
    exit 0
}

if ($Status) {
    Invoke-WatchdogPass
    exit 0
}

Write-WatchdogLog "Naukri watchdog started (Mode: $(if ($SinglePass) { 'SinglePass' } else { 'Continuous' }), StuckThreshold: ${StuckThresholdMinutes}m, SoftRecheck: ${SoftRecheckMinutes}m, Cooldown: ${CooldownHours}h)." "INFO"

if ($SinglePass) {
    Invoke-WatchdogPass
    Write-WatchdogLog "SinglePass watchdog pass completed." "INFO"
    exit 0
}

# Continuous loop
while ($true) {
    Invoke-WatchdogPass
    Start-Sleep -Seconds $LoopIntervalSeconds
}
