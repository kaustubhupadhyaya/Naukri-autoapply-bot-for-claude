<#
.SYNOPSIS
    Self-healing Keepalive supervisor for Naukri Unattended Auto-Apply Bot.
    Inspired by the VPN keepalive pattern from work_experience (N01, N04).

.DESCRIPTION
    1. Checks if python.exe running run_naukri_unattended.py is alive via Get-CimInstance Win32_Process.
    2. Checks naukri_jobs.db via Python SQLite:
       - If today's count of 'Applied (Easy Apply)' >= daily cap (20), logs that cap is satisfied
         and sleeps peacefully until tomorrow (or exits 0 on -SinglePass).
    3. If process is dead and cap is NOT satisfied:
       - Applies exponential backoff if it crashes repeatedly within 2 minutes (5s -> 15s -> 60s -> 120s).
       - Starts run_naukri_unattended.py detached via Start-Process with absolute stdout/stderr paths.
    4. Writes timestamped self-trimming log to naukri_keepalive.log (trims to 500 lines over 200KB).
    5. Supports -SinglePass switch for Windows Task Scheduler or external orchestrators.

.PARAMETER SinglePass
    Run a single evaluation cycle and exit immediately. Default is continuous loop.

.PARAMETER DailyCap
    Daily maximum applications limit. 0 = unlimited (default; matches config.local.json's
    max_applications_per_session = 0). Only consulted when -AllDay is NOT set.

.PARAMETER CheckIntervalSeconds
    Frequency of liveness checks in continuous loop mode (default 60s).

.PARAMETER Status
    Show live status (process, daily application count, crash history) and exit without action.
#>

[CmdletBinding()]
param(
    [switch]$SinglePass,
    [int]$DailyCap = 0,
    [int]$CheckIntervalSeconds = 60,
    [switch]$Status,
    [string]$Profile = "default",
    [switch]$AllDay
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

$VenvPython = Join-Path $RepoDir ".venv\Scripts\python.exe"
$PythonExe  = if (Test-Path $VenvPython) { $VenvPython } else { "python.exe" }
$ScriptFile = "run_naukri_unattended.py"
$ScriptPath = Join-Path $RepoDir $ScriptFile

$ExtraFlags = if ($AllDay) { " --all-day" } else { "" }

if ($Profile -and $Profile -ne "default" -and $Profile -ne "profile1") {
    $ProfileDir = Join-Path $RepoDir "profiles\$Profile"
    New-Item -ItemType Directory -Force -Path $ProfileDir -ErrorAction SilentlyContinue | Out-Null
    $DbPath     = Join-Path $ProfileDir "naukri_jobs.db"
    $LogPath    = Join-Path $ProfileDir "naukri_keepalive.log"
    $StatePath  = Join-Path $ProfileDir "naukri_keepalive.state.json"
    $StdoutPath = Join-Path $ProfileDir "naukri_auto_stdout.log"
    $StderrPath = Join-Path $ProfileDir "naukri_auto_stderr.log"
    $ScriptArgs = "$ScriptFile --profile $Profile$ExtraFlags"
} else {
    $DbPath     = Join-Path $RepoDir "naukri_jobs.db"
    $LogPath    = Join-Path $RepoDir "naukri_keepalive.log"
    $StatePath  = Join-Path $RepoDir "naukri_keepalive.state.json"
    $StdoutPath = Join-Path $RepoDir "naukri_auto_stdout.log"
    $StderrPath = Join-Path $RepoDir "naukri_auto_stderr.log"
    $ScriptArgs = "$ScriptFile$ExtraFlags"
}

# ---------------------------------------------------------------- Logging
function Write-KeepaliveLog {
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
        Add-Content -Path $LogPath -Value $line -Encoding utf8 -ErrorAction SilentlyContinue
        
        # Self-trimming pattern from N01: keep last 500 lines if > 200KB
        if (Test-Path $LogPath) {
            $fileItem = Get-Item $LogPath -ErrorAction SilentlyContinue
            if ($fileItem -and $fileItem.Length -gt 200KB) {
                $lines = Get-Content -Path $LogPath -Tail 500 -ErrorAction SilentlyContinue
                Set-Content -Path $LogPath -Value $lines -Encoding utf8 -ErrorAction SilentlyContinue
            }
        }
    } catch {}
}

# ---------------------------------------------------------------- State Helpers
function Get-KeepaliveState {
    if (Test-Path $StatePath) {
        try {
            $raw = Get-Content -Path $StatePath -Raw -ErrorAction SilentlyContinue
            if ($raw) {
                return ($raw | ConvertFrom-Json)
            }
        } catch {}
    }
    return [PSCustomObject]@{
        LastLaunchTime     = $null
        ConsecutiveCrashes = 0
        LastCrashTime      = $null
        LastDailyCapDate   = $null
    }
}

function Save-KeepaliveState {
    param($State)
    try {
        $json = $State | ConvertTo-Json -Depth 5
        Set-Content -Path $StatePath -Value $json -Encoding utf8 -ErrorAction SilentlyContinue
    } catch {}
}

# ---------------------------------------------------------------- Database Query
function Get-DailyAppliedCount {
    param(
        [string]$DbFile,
        [string]$PyExe
    )
    if (-not (Test-Path $DbFile)) {
        return 0
    }
    $pyCode = @"
import sqlite3, sys
try:
    conn = sqlite3.connect(r'$DbFile')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM applied_jobs WHERE status = 'Applied (Easy Apply)' AND date(application_date) = date('now', 'localtime')")
    row = c.fetchone()
    print(row[0] if row else 0)
except Exception as e:
    sys.stderr.write(str(e) + '\n')
    print(-1)
"@
    try {
        $out = & $PyExe -c $pyCode 2>$null
        if ($out -match '^\d+$') {
            return [int]$out
        }
    } catch {
        return -1
    }
    return -1
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

# ---------------------------------------------------------------- Process Launch
function Start-BotDetached {
    Write-KeepaliveLog "Launching $ScriptArgs detached in background..." "INFO"

    # Pre-launch sweep: kill stale bot-profile Edge windows (profile lock causes a
    # FRESH Edge window + fresh login on every restart = taskbar pileup).
    try {
        $staleEdge = Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*browser_profile*" }
        foreach ($p in $staleEdge) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
        if ($staleEdge) {
            Write-KeepaliveLog "Pre-launch sweep: closed $($staleEdge.Count) stale bot-profile Edge process(es)." "INFO"
            Start-Sleep -Seconds 2
        }
    } catch {}

    # Pre-launch sweep: kill duplicate bot pythons ONLY if >1 exist (a lone survivor
    # from a flaky DEAD declaration must never be murdered).
    try {
        $dupes = @(Get-BotProcess)
        if ($dupes.Count -gt 1) {
            $keeper = Get-BotKeeper $dupes
            foreach ($d in $dupes) {
                if ($d.ProcessId -ne $keeper.ProcessId) {
                    Stop-Process -Id $d.ProcessId -Force -ErrorAction SilentlyContinue
                }
            }
            Write-KeepaliveLog "Pre-launch sweep: stopped $($dupes.Count - 1) duplicate bot(s), kept worker PID $($keeper.ProcessId)." "WARN"
            Start-Sleep -Seconds 2
            return
        } elseif ($dupes.Count -eq 1) {
            Write-KeepaliveLog "Pre-launch sweep: lone bot PID $($dupes[0].ProcessId) survived a flaky check, keeping it, aborting launch." "OK"
            return "SKIPPED"
        }
    } catch {}

    $env:PYTHONUNBUFFERED = "1"
    $env:NAUKRI_SKIP_EXTERNAL = "1"

    # H5 (2026-09-15): Start-Process truncates -RedirectStandardError/-Output on every launch,
    # so 68 relaunches/24h left zero trace of why the previous one died. Keep one prior copy.
    foreach ($p in @($StdoutPath, $StderrPath)) {
        if (Test-Path $p) {
            Copy-Item $p "$p.previous" -Force -ErrorAction SilentlyContinue
        }
    }

    $proc = Start-Process -FilePath $PythonExe `
        -ArgumentList $ScriptArgs `
        -WorkingDirectory $RepoDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -PassThru

    # Birth observation only (no killing): the launcher spawns the real worker as a child;
    # murdering it killed the bot. Keeper logic below protects the worker everywhere.
    Start-Sleep -Seconds 8
    try {
        $twins = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*run_naukri_unattended.py*" -and $_.ProcessId -ne $proc.Id })
        foreach ($t in $twins) {
            Write-KeepaliveLog "Birth observation: child/worker bot PID $($t.ProcessId) present post-launch (protected, never killed)." "INFO"
        }
    } catch {}

    return $proc
}


# ---------------------------------------------------------------- Keeper selection
# The venv launcher (idle, ~4MB) spawns the real worker (owns msedgedriver, burns CPU).
# Keeper = the worker: bot with a live msedgedriver child, else highest CPU time, else oldest.
function Get-BotKeeper {
    param($Bots)
    $list = @($Bots)
    if ($list.Count -eq 0) { return $null }
    if ($list.Count -eq 1) { return $list[0] }
    try {
        $drivers = @(Get-CimInstance Win32_Process -Filter "Name='msedgedriver.exe'" -ErrorAction SilentlyContinue)
        foreach ($b in ($list | Sort-Object CreationDate)) {
            if ($drivers | Where-Object { $_.ParentProcessId -eq $b.ProcessId }) {
                return $b
            }
        }
    } catch {}
    try {
        $timed = foreach ($b in $list) {
            $cpu = 0
            try {
                $p = Get-Process -Id $b.ProcessId -ErrorAction SilentlyContinue
                if ($p) { $cpu = $p.CPU }
            } catch {}
            [PSCustomObject]@{ Proc = $b; CPU = $cpu }
        }
        $best = ($timed | Sort-Object CPU -Descending | Select-Object -First 1)
        if ($best -and $best.CPU -gt 0) { return $best.Proc }
    } catch {}
    return ($list | Sort-Object CreationDate | Select-Object -First 1)
}

# ---------------------------------------------------------------- Core Keepalive Pass
function Invoke-KeepalivePass {
    $state = Get-KeepaliveState
    $now = Get-Date
    
    # 1. Inspect running process (debounced: WMI flakes cause false DEAD -> murder-relaunch churn)
    $runningProcs = $null
    try {
        $runningProcs = Get-BotProcess
    } catch {
        $runningProcs = $null
    }
    $isRunning = ($runningProcs -ne $null -and @($runningProcs).Count -gt 0)
    if (-not $isRunning) {
        $missed = 0
        try { $missed = [int]$state.MissedChecks } catch { $missed = 0 }
        $missed++
        $state | Add-Member -NotePropertyName "MissedChecks" -NotePropertyValue $missed -Force
        Save-KeepaliveState $state
        if ($missed -lt 2) {
            Write-KeepaliveLog "Bot not seen, waiting one more tick before relaunch as WMI-flake guard." "WARN"
            return
        }
        $state | Add-Member -NotePropertyName "MissedChecks" -NotePropertyValue 0 -Force
        Save-KeepaliveState $state
    } else {
        if ($state.MissedChecks) {
            $state | Add-Member -NotePropertyName "MissedChecks" -NotePropertyValue 0 -Force
            Save-KeepaliveState $state
        }
    }
    $activeProc = if ($isRunning) { @($runningProcs)[0] } else { $null }

    # 2. Query today's applications from SQLite
    $todayCount = Get-DailyAppliedCount -DbFile $DbPath -PyExe $PythonExe

    # Status only switch
    if ($Status) {
        Write-Host ""
        Write-Host "==================== NAUKRI KEEPALIVE STATUS ====================" -ForegroundColor Cyan
        if ($isRunning) {
            Write-Host "Process State    : RUNNING (PID $($activeProc.ProcessId), Started: $($activeProc.CreationDate))" -ForegroundColor Green
        } else {
            Write-Host "Process State    : STOPPED / DEAD" -ForegroundColor Yellow
        }
        $modeText = if ($AllDay -or $DailyCap -le 0) { "ALL-DAY 24/7 Continuous (Uncapped, Hourly Paced)" } else { "Session-Capped ($DailyCap/day)" }
        Write-Host "Execution Mode   : $modeText" -ForegroundColor Magenta
        Write-Host "Today Applied  : $todayCount / $(if ($AllDay -or $DailyCap -le 0) { "inf" } else { $DailyCap })" -ForegroundColor White
        Write-Host "Crash Count      : $($state.ConsecutiveCrashes)" -ForegroundColor White
        Write-Host "Last Launch Time : $($state.LastLaunchTime)" -ForegroundColor White
        Write-Host "=================================================================" -ForegroundColor Cyan
        return
    }

    # If running, check how long it's been up
    if ($isRunning) {
        # Duplicate guard: keeper = the real worker (owns msedgedriver). The idle venv
        # launcher is never killed while the worker lives; stale launcher-only dupes are reaped.
        try {
            $allBots = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
                Where-Object { $_.CommandLine -like "*run_naukri_unattended.py*" })
            if ($allBots.Count -gt 2) {
                $keeper = Get-BotKeeper $allBots
                foreach ($b in $allBots) {
                    if ($b.ProcessId -ne $keeper.ProcessId) {
                        $isLauncherLike = $true
                        try {
                            $pp = Get-Process -Id $b.ProcessId -ErrorAction SilentlyContinue
                            if ($pp -and $pp.CPU -gt 5) { $isLauncherLike = $false }
                        } catch {}
                        if ($isLauncherLike) {
                            Stop-Process -Id $b.ProcessId -Force -ErrorAction SilentlyContinue
                            Write-KeepaliveLog "Reaped stale launcher-like bot PID $($b.ProcessId) (kept worker PID $($keeper.ProcessId))." "WARN"
                        }
                    }
                }
                $runningProcs = Get-BotProcess
                $activeProc = if ($runningProcs) { $runningProcs[0] } else { $null }
            }
        } catch {}
        if (-not $activeProc) { return }
        $uptimeSec = [math]::Round(($now - $activeProc.CreationDate).TotalSeconds, 1)
        # If running stably for > 2 minutes, reset crash counter
        if ($uptimeSec -ge 120 -and $state.ConsecutiveCrashes -gt 0) {
            Write-KeepaliveLog "Process stable for $([math]::Round($uptimeSec/60, 1))m (>= 2m). Resetting consecutive crash count to 0." "INFO"
            $state.ConsecutiveCrashes = 0
            Save-KeepaliveState $state
        }
        $capDisplay = if ($AllDay -or $DailyCap -le 0) { "All-Day 24/7 continuous" } else { "$todayCount / $DailyCap" }
        Write-KeepaliveLog "Bot alive (PID $($activeProc.ProcessId), uptime $([math]::Round($uptimeSec/60, 1))m). Mode: $capDisplay." "OK"
        return
    }

    # 3. Process is DEAD - Check Daily Cap (only in session-capped mode)
    if (-not $AllDay -and $DailyCap -gt 0 -and $todayCount -ge $DailyCap) {
        Write-KeepaliveLog "Daily cap satisfied: $todayCount / $DailyCap applied today. Bot is peacefully resting until tomorrow." "OK"
        $state.LastDailyCapDate = $now.ToString("yyyy-MM-dd")
        $state.ConsecutiveCrashes = 0
        Save-KeepaliveState $state
        
        if (-not $SinglePass) {
            # Calculate sleep duration until next midnight
            $tomorrow = $now.Date.AddDays(1).AddMinutes(1)
            $sleepSec = [int]($tomorrow - (Get-Date)).TotalSeconds
            if ($sleepSec -gt 0) {
                Write-KeepaliveLog "Continuous mode: sleeping peacefully for $([math]::Round($sleepSec/3600, 2)) hours until tomorrow ($($tomorrow.ToString('yyyy-MM-dd HH:mm:ss')))..." "INFO"
                while ((Get-Date) -lt $tomorrow) {
                    $rem = [int]($tomorrow - (Get-Date)).TotalSeconds
                    $chunk = [Math]::Min(300, $rem)
                    if ($chunk -le 0) { break }
                    Start-Sleep -Seconds $chunk
                }
            }
        }
        return
    }

    # 4. Process is DEAD -> Handle restarts & exponential backoff
    if ($AllDay) {
        Write-KeepaliveLog "Process is DEAD. All-Day 24/7 continuous mode active ($todayCount applied today). Initiating autonomous launch/recovery..." "INFO"
    } else {
        Write-KeepaliveLog "Process is DEAD and daily cap not satisfied ($todayCount / $DailyCap applied)." "WARN"
    }

    if ($state.LastLaunchTime) {
        $lastLaunch = [datetime]$state.LastLaunchTime
        $runtimeSec = ($now - $lastLaunch).TotalSeconds
        if ($runtimeSec -lt 120) {
            # Died within 2 minutes: repeated crash!
            $state.ConsecutiveCrashes++
            $state.LastCrashTime = $now.ToString("o")
            
            # Exponential backoff: 5s -> 15s -> 60s -> 120s -> 300s
            $backoff = switch ($state.ConsecutiveCrashes) {
                1 { 5 }
                2 { 15 }
                3 { 60 }
                4 { 120 }
                default { 300 }
            }
            Write-KeepaliveLog "Process crashed within 2 minutes ($([math]::Round($runtimeSec, 1))s since launch). Crash count: $($state.ConsecutiveCrashes). Backing off for ${backoff}s..." "WARN"
            Save-KeepaliveState $state
            Start-Sleep -Seconds $backoff
        } else {
            # Last run lasted >= 2 minutes before exiting
            $state.ConsecutiveCrashes = 0
        }
    }

    # 5. Launch detached
    $newProc = Start-BotDetached
    if ($newProc -eq "SKIPPED") {
        return
    }
    if ($newProc -and -not $newProc.HasExited) {
        Write-KeepaliveLog "Bot started successfully (PID $($newProc.Id)). Redirecting to stdout: $StdoutPath, stderr: $StderrPath" "OK"
        $state.LastLaunchTime = (Get-Date).ToString("o")
        Save-KeepaliveState $state
    } else {
        Write-KeepaliveLog "Failed to start bot process." "ERROR"
    }
}

# ---------------------------------------------------------------- Execution
if ($Status) {
    Invoke-KeepalivePass
    exit 0
}

Write-KeepaliveLog "Naukri keepalive supervisor started (Mode: $(if ($SinglePass) { 'SinglePass' } else { 'Continuous' }), DailyCap: $DailyCap)." "INFO"

if ($SinglePass) {
    Invoke-KeepalivePass
    Write-KeepaliveLog "SinglePass evaluation completed." "INFO"
    exit 0
}

# Continuous loop
while ($true) {
    Invoke-KeepalivePass
    Start-Sleep -Seconds $CheckIntervalSeconds
}

