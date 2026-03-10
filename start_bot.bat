@echo off
chcp 65001 >nul
color 0B
echo ===================================================
echo     AlphaTW 台股交易推手 - 一鍵啟動腳本
echo ===================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 Python，請確定您已經安裝 Python 並且加到 PATH 環境變數中。
    pause
    exit /b
)

npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 NPM，請確定您已經安裝 Node.js 並且加到 PATH 環境變數中。
    pause
    exit /b
)

echo [1/3] 正在背景啟動 FastAPI 後端伺服器 (Port 8000)...
start "AlphaTW Backend" cmd /c "python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload & pause"

echo [2/3] 等待後端啟動...
timeout /t 5 /nobreak >nul

echo [3/3] 正在啟動 React 前端開發伺服器...
cd frontend
start "AlphaTW Frontend" cmd /c "npm run dev & pause"

echo.
echo ===================================================
echo   啟動完成！
echo   如果沒有自動開啟瀏覽器，請手動前往:
echo   http://localhost:5173
echo ===================================================
echo.
timeout /t 3 >nul

start http://localhost:5173
exit
