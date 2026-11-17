@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\therasim.ps1" -Action Check
if errorlevel 1 pause
