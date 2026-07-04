@echo off
chcp 65001 >nul

rem === needs admin to install a system driver ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo ============================================
echo   Installing ViGEmBus virtual gamepad driver
echo   (only needed for the AUTO-SCAN feature)
echo ============================================
echo.

set "FOUND="
for %%F in (ViGEmBus_*.exe) do (
    set "FOUND=1"
    echo Running %%F ...
    "%%F"
)

if not defined FOUND (
    echo [X] ViGEmBus installer not found here.
    echo     Run the one-click installer first, or download from:
    echo     https://github.com/nefarius/ViGEmBus/releases
)
echo.
echo Done. You can close this window.
pause
