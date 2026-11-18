@echo off
chcp 65001 > nul
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 以上が見つかりません。Microsoft Store または python.org からインストールしてください。
    pause
    exit /b 1
)
python -B -I "%~dp0patcher.py" uninstall
pause
