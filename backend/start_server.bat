@echo off
rem 为什么必须 0.0.0.0：127.0.0.1 只接受本机连接，手机连不进来，真机预览必须监听 0.0.0.0。
cd /d %~dp0
start "elder_care_backend" .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
ping -n 5 127.0.0.1 >nul
start "" http://127.0.0.1:8000/api/health
