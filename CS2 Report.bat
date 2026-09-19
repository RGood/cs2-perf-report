@echo off
rem Launches the CS2 Performance Report desktop app. Drag demos onto the window.
rem On the first run (or after requirements.txt changes) the required Python packages are installed first.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
python "%~dp0ensure_deps.py"
if errorlevel 1 (
  pause
  exit /b 1
)
start "" pythonw "%~dp0app.py"
