@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Installation au premier lancement...
  python -m venv .venv || (echo Python introuvable : installe-le depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH". & pause & exit /b 1)
  .venv\Scripts\python -m pip install -r requirements.txt
)
start "" http://127.0.0.1:5050
.venv\Scripts\python -m fut_tracker.app
pause
