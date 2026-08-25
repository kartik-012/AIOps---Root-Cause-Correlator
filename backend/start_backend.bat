@echo off
echo ===================================================
echo   Starting AIOps Root Cause Correlator Backend
echo ===================================================
cd /d "%~dp0"
python -m alembic upgrade head
python run_server.py
