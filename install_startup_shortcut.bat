@echo off
setlocal
cd /d %~dp0

set "TARGET=%CD%\dist\WalkuerLanChat.exe"
if not exist "%TARGET%" (
  echo dist\WalkuerLanChat.exe not found. Build first with build_exe.bat
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup') + '\\WalkuerLanChat.lnk'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%CD%'; $s.IconLocation='%TARGET%'; $s.Save()"

echo Startup shortcut created.
