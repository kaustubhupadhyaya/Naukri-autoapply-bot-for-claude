@echo off
rem Naukri failure watcher - separate from the bot, safe to run any time (read-only).
rem   watch.cmd                        live: attach to the running bot until Ctrl+C
rem   watch.cmd live --minutes 30
rem   watch.cmd postmortem --since 6h  from naukri_bot.log only (no browser needed)
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
".venv\Scripts\python.exe" -m naukri_watch %*
