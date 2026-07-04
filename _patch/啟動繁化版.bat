@echo off
chcp 65001 >nul

rem === elevate (auto-scan needs admin) ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ============================================
echo   NTE Drive Calc (Traditional Chinese)
echo ============================================
echo.

rem === find python: prefer one that already has packages, skip Store stub ===
set "PYLIST=%TEMP%\nte_pylist.txt"
type nul > "%PYLIST%"
if exist "%LOCALAPPDATA%\Programs\Python" dir /b /s "%LOCALAPPDATA%\Programs\Python\python.exe" >> "%PYLIST%" 2>nul
if exist "%LOCALAPPDATA%\Python" dir /b /s "%LOCALAPPDATA%\Python\python.exe" >> "%PYLIST%" 2>nul
dir /b /s "%ProgramFiles%\Python*\python.exe" >> "%PYLIST%" 2>nul
for /f "delims=" %%P in ('where python 2^>nul') do echo %%P>> "%PYLIST%"
for /f "delims=" %%P in ('where py 2^>nul') do echo %%P>> "%PYLIST%"
set "PYEXE="
set "PYFALL="
for /f "usebackq delims=" %%P in ("%PYLIST%") do (
    echo %%P | find /i "WindowsApps" >nul
    if errorlevel 1 (
        if not defined PYFALL set "PYFALL=%%P"
        if not defined PYEXE (
            "%%P" -c "import PySide6" >nul 2>&1
            if not errorlevel 1 set "PYEXE=%%P"
        )
    )
)
if not defined PYEXE set "PYEXE=%PYFALL%"
if not defined PYEXE (
    echo [X] Python not found. Please run the installer again,
    echo     or install Python from https://www.python.org/downloads/
    pause
    exit /b
)
echo Python: !PYEXE!
echo.

echo Launching...
"!PYEXE!" "%~dp0_launcher.py"
echo.
echo [Program ended] If there is an error above, screenshot it.
pause