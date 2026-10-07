@echo off
set "P_STUDIO_PYTHON="
set "P_STUDIO_FALLBACK="
set "P_STUDIO_READY="
if exist "%~dp0..\.venv\Scripts\python.exe" call :try_python "%~dp0..\.venv\Scripts\python.exe"
for /f "delims=" %%P in ('where python.exe 2^>nul') do call :try_python "%%P"
for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do call :try_python "%%P"
if defined P_STUDIO_READY exit /b 0
if defined P_STUDIO_FALLBACK (
  set "P_STUDIO_PYTHON=%P_STUDIO_FALLBACK%"
  exit /b 0
)
exit /b 1

:try_python
if defined P_STUDIO_READY exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>&1
if errorlevel 1 exit /b 0
if not defined P_STUDIO_FALLBACK set "P_STUDIO_FALLBACK=%~1"
"%~1" -c "from PyQt5.QtWebEngineWidgets import QWebEngineView; from PyQt5.QtWebChannel import QWebChannel" >nul 2>&1
if errorlevel 1 exit /b 0
set "P_STUDIO_PYTHON=%~1"
set "P_STUDIO_READY=1"
exit /b 0
