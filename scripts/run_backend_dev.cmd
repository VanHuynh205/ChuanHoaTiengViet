@echo off
setlocal

set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
) else (
  set "PYTHON_EXE=python"
)

cd /d "%ROOT%\backend"
"%PYTHON_EXE%" -m uvicorn app.api.server:app --host localhost --port 8000
