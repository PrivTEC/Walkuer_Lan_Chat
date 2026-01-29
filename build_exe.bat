@echo off
setlocal
cd /d %~dp0

if not exist .venv\Scripts\python.exe (
  python -m venv .venv
)

.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install pyinstaller

if not exist build (
  mkdir build
)

.venv\Scripts\python.exe -c "import sys; from pathlib import Path; sys.path.append('src'); from util.images import write_app_icon; Path('build').mkdir(exist_ok=True); write_app_icon(r'build\\walkuer.ico')"

set "ICON_ARG="
if exist build\walkuer.ico set "ICON_ARG=--icon build\walkuer.ico"

.venv\Scripts\python.exe -m PyInstaller --noconsole --onefile --name WalkuerLanChat %ICON_ARG% --add-data "src\assets\splash.svg;assets" src\main.py

echo Build OK: dist\WalkuerLanChat.exe
