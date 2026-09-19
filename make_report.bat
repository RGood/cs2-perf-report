@echo off
rem Command-line report. Examples:
rem   make_report latest            make_report latest de_nuke
rem   make_report list              make_report "C:\path\to\demo.dem.zst"
rem On the first run (or after requirements.txt changes) the required Python packages are installed first.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.12 from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  exit /b 1
)
python "%~dp0ensure_deps.py"
if errorlevel 1 exit /b 1
if "%~1"=="" (python cs2report.py latest) else if "%~1"=="latest" (
  if "%~2"=="" (python cs2report.py latest) else (python cs2report.py latest --map %~2)
) else (python cs2report.py %*)
if "%~1"=="list" goto :done
for /f "delims=" %%f in ('dir /b /o-d reports\*_performance.html 2^>nul') do (start "" "reports\%%f" & goto :done)
:done
