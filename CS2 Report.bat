@echo off
rem Launches the CS2 Performance Report desktop app. Drag demos onto the window.
cd /d "%~dp0"
start "" pythonw "%~dp0app.py"
