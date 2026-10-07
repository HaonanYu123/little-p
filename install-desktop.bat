@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0scripts\python-runtime.bat"
if errorlevel 1 (
  echo 未找到可用的 Python 3.9 或更新版本，请安装 Python 后重试。
  pause
  exit /b 1
)
echo 使用 Python: %P_STUDIO_PYTHON%
"%P_STUDIO_PYTHON%" -m pip install -r "%~dp0desktop\requirements.txt"
if errorlevel 1 (
  echo 安装失败，请查看上方错误信息。
  pause
  exit /b 1
)
echo 桌宠组件已安装。现在可以双击 start.bat。
pause
exit /b 0
