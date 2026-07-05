@echo off
chcp 65001 >nul

rem === elevate (driver install needs admin) ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
setlocal enabledelayedexpansion

echo ============================================
echo   NTE Drive Calc - One-click Traditional Setup
echo ============================================
echo.

rem ---- 1) find python: prefer one that already has packages, skip Store stub ----
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

rem ---- no python: install via winget, then ask to re-run ----
if not defined PYEXE (
    echo Python not found. Trying to install via winget...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [X] winget not available. Please install Python manually:
        echo     https://www.python.org/downloads/
        echo     IMPORTANT: check "Add Python to PATH" during install.
        pause
        exit /b
    )
    winget install --id Python.Python.3.11 -e --accept-source-agreements --accept-package-agreements
    echo.
    echo ============================================
    echo   Python installed!
    echo   Please CLOSE this window and run this file AGAIN.
    echo ============================================
    pause
    exit /b
)
echo Using Python: !PYEXE!
echo.

rem ---- close the running program (if any) so its folder can be replaced ----
echo Closing the program if it is running...
powershell -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like '*_launcher.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
timeout /t 2 /nobreak >nul 2>&1

rem ---- 2) download source ----
set "SRCZIP=%TEMP%\nte_src.zip"
set "TARGET=%~dp0NTE-Drive-Calc-main"
set "DATABK=%~dp0_accounts_backup"
echo [1/5] Downloading program source from GitHub...
powershell -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/hxwd94666/NTE-Drive-Calc/archive/refs/heads/main.zip' -OutFile '%SRCZIP%'"
if errorlevel 1 (
    echo [X] Download failed. Check your internet connection.
    pause
    exit /b
)

rem ================= preserve user data (accounts) =================
rem SAFETY: never delete a backup blindly - a leftover backup may be the ONLY
rem copy left if a previous update failed to restore. Keep it aside as _old.
if exist "%DATABK%" (
    if exist "%DATABK%_old" rmdir /s /q "%DATABK%_old"
    move "%DATABK%" "%DATABK%_old" >nul 2>&1
)

rem Move current scan data out to the backup, then VERIFY it actually moved.
rem If it didn't move (program still locking a file), ABORT before deleting anything.
if exist "%TARGET%\accounts" (
    move "%TARGET%\accounts" "%DATABK%" >nul 2>&1
    if not exist "%DATABK%" (
        echo.
        echo [X] Could not back up your scan data ^(the program may still be running^).
        echo     Update ABORTED on purpose - NOTHING was deleted, your data is intact.
        echo     Please fully close the program AND the console, then run this again.
        if exist "%DATABK%_old" move "%DATABK%_old" "%DATABK%" >nul 2>&1
        pause
        exit /b
    )
    echo [i] Existing scan data safely backed up.
)

echo [2/5] Extracting...
rem Try to remove the old program folder (accounts are already moved out and verified).
if exist "%TARGET%" rmdir /s /q "%TARGET%" 2>nul
if exist "%TARGET%\main.py" (
    echo.
    echo [X] The program is still RUNNING - cannot replace it.
    echo     Please CLOSE the program window first, then run this again.
    rem roll back: put data back where it was
    if exist "%DATABK%" move "%DATABK%" "%TARGET%\accounts" >nul 2>&1
    if exist "%DATABK%_old" move "%DATABK%_old" "%DATABK%" >nul 2>&1
    pause
    exit /b
)
powershell -Command "Expand-Archive -Path '%SRCZIP%' -DestinationPath '%~dp0' -Force"
if not exist "%TARGET%\main.py" (
    echo [X] Extract failed or unexpected structure.
    rem roll back: put data back so it is never lost
    if exist "%DATABK%" move "%DATABK%" "%TARGET%\accounts" >nul 2>&1
    if exist "%DATABK%_old" move "%DATABK%_old" "%DATABK%" >nul 2>&1
    pause
    exit /b
)

rem ---- restore user data (and VERIFY) ----
if exist "%DATABK%" (
    if exist "%TARGET%\accounts" rmdir /s /q "%TARGET%\accounts"
    move "%DATABK%" "%TARGET%\accounts" >nul 2>&1
    if exist "%TARGET%\accounts" (
        echo [i] Your scan data has been restored.
        if exist "%DATABK%_old" rmdir /s /q "%DATABK%_old"
    ) else (
        echo.
        echo [X] Could not auto-restore scan data - but DON'T WORRY, it is SAFE at:
        echo     %DATABK%
        echo     Manually move the "default" folder inside it into:
        echo     %TARGET%\accounts\
        echo.
        pause
    )
)
rem A leftover backup from a PREVIOUS failed update - keep it, just inform.
if exist "%DATABK%_old" (
    echo [!] A backup from a previous update was kept at:
    echo     %DATABK%_old
    echo     If your data looks complete now, you may delete that folder later.
)

rem ---- 3) copy patch files from _patch into program folder ----
copy /y "%~dp0_patch\*.py" "%TARGET%\" >nul
copy /y "%~dp0_patch\*.bat" "%TARGET%\" >nul

rem ---- 4) install ALL required packages ----
cd /d "%TARGET%"
echo [3/5] Installing packages (may take several minutes)...
"!PYEXE!" -m pip install opencc-python-reimplemented pyside6 rapidocr-onnxruntime onnxruntime opencv-python numpy scipy pillow pydantic loguru pyautogui keyboard mss pypinyin vgamepad

rem ---- 5) convert to Traditional ----
echo [4/5] Converting to Traditional Chinese...
"!PYEXE!" "%TARGET%\nte_traditionalizer.py" "%TARGET%"

rem ---- 6) install ViGEmBus virtual gamepad driver (needed for auto-scan) ----
echo [5/5] Checking virtual gamepad driver...
"!PYEXE!" -c "import vgamepad; vgamepad.VX360Gamepad()" >nul 2>&1
if errorlevel 1 (
    echo     Installing ViGEmBus driver - please click through its wizard...
    for %%F in ("%TARGET%\ViGEmBus_*.exe") do "%%F"
) else (
    echo     Driver already OK.
)

rem --- record installed commit id (for launch-time update checks) ---
powershell -Command "try { $c=(Invoke-RestMethod -Headers @{'User-Agent'='NTE'} -Uri 'https://api.github.com/repos/hxwd94666/NTE-Drive-Calc/commits/main').sha.Substring(0,12); Set-Content -Path '%TARGET%\_installed_commit.txt' -Value $c -Encoding ascii } catch {}"

echo.
echo ============================================
echo   ALL DONE!  Installation/update complete.
echo   Go back to the Console and click "Re-check".
echo   This window closes automatically...
echo ============================================
ping -n 4 127.0.0.1 >nul
exit
