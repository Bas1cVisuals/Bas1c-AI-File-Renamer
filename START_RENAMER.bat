@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer and enable Add Python to PATH.
  pause
  exit /b 1
)
python -c "import requests, PIL" >nul 2>nul
if errorlevel 1 (
  echo Installing required Python packages...
  python -m pip install --user requests pillow
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)
python ai_image_renamer_gui.py
if errorlevel 1 pause
