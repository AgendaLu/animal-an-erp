@echo off
REM 打包 Windows 桌面版 → dist\animal-an-erp\
REM 需求:專案 .venv 已建好(pip install -e ".[dev]")
cd /d "%~dp0.."

set PY=.venv\Scripts\python.exe

%PY% -m pip show pyinstaller >nul 2>&1 || %PY% -m pip install "pyinstaller>=6.0"
if errorlevel 1 goto :error

%PY% -m PyInstaller packaging\animal_an.spec --distpath dist --workpath build\pyinstaller -y
if errorlevel 1 goto :error

echo.
echo 打包完成: dist\animal-an-erp\
echo 啟動: dist\animal-an-erp\animal-an-erp.exe
echo 資料庫會建立在 dist\animal-an-erp\data\animal_an.db
goto :eof

:error
echo 打包失敗,請檢查上方錯誤訊息
exit /b 1
