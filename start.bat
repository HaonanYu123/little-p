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
if not defined P_STUDIO_READY (
  echo 正在安装桌宠组件，首次启动可能需要几分钟……
  "%P_STUDIO_PYTHON%" -m pip install -r "%~dp0desktop\requirements.txt"
  if errorlevel 1 (
    echo 桌宠组件安装失败。请保留此窗口中的错误信息。
    pause
    exit /b 1
  )
)
echo 请在打开的 http://127.0.0.1:8086 页面点击“召唤”。
echo 桌宠服务运行期间，请保持此窗口打开。
"%P_STUDIO_PYTHON%" -u "%~dp0serve.py" %*
if errorlevel 1 (
  echo 本地服务启动失败，请查看上方错误信息。
  pause
  exit /b 1
)
exit /b 0
