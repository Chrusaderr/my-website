@echo off
setlocal
cd /d "%~dp0backend"
echo Installing/validating dependencies...
python -m pip install -r requirements.txt >nul 2>&1
echo Starting AI Trader backend...
start "" http://127.0.0.1:5000
python app.py
endlocal
