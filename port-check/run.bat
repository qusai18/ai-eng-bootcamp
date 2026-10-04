@echo off
cd /d "%~dp0"
python app.py
if errorlevel 1 py -3 app.py
if errorlevel 1 pause
