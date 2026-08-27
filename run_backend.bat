@echo off
title ATS Scorer - Backend (FastAPI)
echo Starting ATS Scorer Backend on http://localhost:8000 ...
cd /d "%~dp0"
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
pause
