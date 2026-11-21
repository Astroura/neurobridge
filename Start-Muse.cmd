@echo off
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYINSTALLER_RESET_ENVIRONMENT=1
set NEUROBRIDGE_STOP_FILE=
"%~dp0NeuroBridge-Worker.exe" --worker terminal-stream --backend bleak --lsltime
if errorlevel 1 pause
