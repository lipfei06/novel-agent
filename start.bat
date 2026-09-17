@echo off
chcp 65001 >nul
title novel-agent 启动器
cd /d %~dp0

echo ============================================
echo   novel-agent 一键启动（后端 + 前端）
echo ============================================
echo.

rem 后端独立窗口（mock 模式，离线可用；--reload 代码变更自动重载）
echo [1/2] 启动后端 http://127.0.0.1:8000 ...
start "novel-agent-backend" cmd /k "set NOVEL_ENGINE_MOCK=1 && C:\Users\lpf\.conda\envs\novel-agent\python.exe -m novel_agent.cli.app serve --port 8000 --root %~dp0 --reload"

rem 前端独立窗口
echo [2/2] 启动前端 http://localhost:5173 ...
start "novel-agent-web" cmd /k "cd /d %~dp0web && npm run dev"

echo.
echo 已在新窗口启动。请保持「后端窗口」开启 —— 关闭它服务即停止。
echo 浏览器打开 http://localhost:5173
pause
