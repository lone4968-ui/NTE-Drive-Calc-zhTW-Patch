@echo off
chcp 65001 >nul

rem === elevate (auto-scan controls a game that usually runs as admin) ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ============================================
echo   NTE Traditional-Chinese Console - starting
echo ============================================
echo.

rem === collect candidate pythons, prefer one that already has packages ===
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
del "%PYLIST%" >nul 2>&1

rem === no python at all: install via winget, then ask to re-run ===
if not defined PYEXE (
    echo No Python found. Installing it via winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [X] Cannot auto-install. Please install Python manually:
        echo     https://www.python.org/downloads/
        echo     Check "Add Python to PATH" during install.
        pause
        exit /b
    )
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
    echo.
    echo ============================================
    echo   Python installed!
    echo   Please CLOSE this window and run this file again.
    echo ============================================
    pause
    exit /b
)

rem 用 pythonw.exe（無主控台版）開，避免留一個黑視窗
set "PYW=!PYEXE:python.exe=pythonw.exe!"
if not exist "!PYW!" set "PYW=!PYEXE!"
start "" "!PYW!" "%~dp0控制台.py"
