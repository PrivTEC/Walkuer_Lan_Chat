@echo off
setlocal
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  python -m venv .venv
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\main.py
