@echo off
chcp 65001 >nul
cd /d "%~dp0..\backend"

if not exist ..\deploy\certs\key.pem (
  echo 请先运行 scripts\gen_cert.bat 生成证书
  exit /b 1
)

start "elder_care_https" .venv\Scripts\python.exe -m uvicorn app.main:app ^
  --host 0.0.0.0 --port 8443 ^
  --ssl-keyfile ..\deploy\certs\key.pem ^
  --ssl-certfile ..\deploy\certs\cert.pem

ping -n 5 127.0.0.1 >nul
start "" https://127.0.0.1:8443/api/health
