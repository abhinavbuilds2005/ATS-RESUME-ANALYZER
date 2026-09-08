@echo off
title ATS Resume Scorer - Web Application
echo ===================================================
echo Starting ATS Resume Scorer on http://localhost:8000
echo Open http://localhost:8000 in your web browser
echo ===================================================
cd /d "%~dp0"
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
pause
