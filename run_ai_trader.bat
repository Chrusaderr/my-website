@echo off
REM AI Trader v4.8 Pro Studio launcher
cd /d "%~dp0backend"
echo Setting up Python environment...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt
start "" http://127.0.0.1:5000
python app.py
