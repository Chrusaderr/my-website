@echo off
setlocal
cd /d "%~dp0"
REM Launch from project root if this file is in the root; else adjust path below.
if exist backend\app.py (
  cd backend
)
echo Installing/validating dependencies...
python -m pip install -r requirements.txt >nul 2>&1
echo Starting AI Trader backend...
start "" http://127.0.0.1:5000
start "" http://127.0.0.1:5000/logs
python app.py
endlocal
