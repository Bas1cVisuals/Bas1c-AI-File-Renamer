@echo off
setlocal
echo Installing dependencies for BAS1C AI Image Renamer...
python -m pip install --user --upgrade requests pillow
if errorlevel 1 (
  echo Installation failed. Check Python and internet connection.
  pause
  exit /b 1
)
echo.
echo Dependencies installed.
echo Make sure Ollama is installed and run:
echo   ollama pull minicpm-v
echo.
pause
