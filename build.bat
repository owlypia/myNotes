@echo off
setlocal
cd /d "%~dp0"

set PY=python
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set PY=py -3

echo [1/4] Syncing version...
%PY% tools\sync_version.py
if errorlevel 1 goto :fail

echo [2/4] Creating app icon...
%PY% tools\make_icon.py
if errorlevel 1 goto :fail

echo [3/4] Packaging MyNotes.exe...
%PY% -m PyInstaller --noconfirm MyNotes.spec
if errorlevel 1 goto :fail

echo [4/4] Building Windows installer...
if not exist "dist\installer" mkdir "dist\installer"
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "installer\MyNotes.iss"
if errorlevel 1 goto :fail

echo.
echo Installer is ready:
echo   %~dp0dist\installer\MyNotesSetup.exe
echo.
exit /b 0

:fail
echo.
echo Build failed.
exit /b 1
