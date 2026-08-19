@echo off
chcp 65001 >nul
rem ==========================================
rem  AI4SE PaperTracker 一键启动（课题组用）
rem  双击本文件：自动启动后端 + 前端 + 打开浏览器
rem  关闭服务：分别关闭弹出的两个命令行窗口
rem ==========================================
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
    echo [错误] 未找到 backend\.venv，请先执行依赖安装
    pause
    exit /b 1
)

echo 正在启动后端（端口 8000）...
start "AI4SE-Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000"

echo 正在启动前端（端口 5173）...
start "AI4SE-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo 等待服务就绪...
timeout /t 10 /nobreak >nul
start http://localhost:5173

echo.
echo 已打开 http://localhost:5173
echo 提示：若页面未加载，稍等几秒刷新；关闭服务请关闭两个命令行窗口。
pause
