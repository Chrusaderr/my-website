@echo off
cd /d "%~dp0"
cd backend
python -m pip install -r requirements.txt
python app.py
pause
