@echo off
title ATS Scorer - Frontend (Streamlit)
echo Starting ATS Scorer Frontend on http://localhost:8501 ...
cd /d "%~dp0"
streamlit run frontend/streamlit_app.py
pause
