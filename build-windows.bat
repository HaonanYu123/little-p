@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0scripts\python-runtime.bat"
if errorlevel 1 (
  echo 未找到可用的 Python 3.9 或更新版本。
  pause
  exit /b 1
)
set "BUILD_PYTHON=%~dp0output\build-venv\Scripts\python.exe"
if not exist "%BUILD_PYTHON%" "%P_STUDIO_PYTHON%" -m venv --system-site-packages "%~dp0output\build-venv"
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m pip install -r desktop\requirements.txt pyinstaller
if errorlevel 1 exit /b 1
"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean LittleP.spec
if errorlevel 1 exit /b 1
set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" set "ISCC_EXE=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC_EXE%" (
  "%ISCC_EXE%" installer\LittleP.iss
  if errorlevel 1 exit /b 1
  echo 安装包已生成到 output\installer。
) else (
  echo 便携程序已生成到 dist\LittleP。
  echo 安装 Inno Setup 6 后再次运行，可生成安装包。
)
pause
