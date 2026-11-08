@echo off
chcp 65001 >nul
cd /d "%~dp0.."

if not exist deploy\certs mkdir deploy\certs

D:\Git\usr\bin\openssl.exe req -x509 -newkey rsa:2048 -nodes -days 825 ^
  -keyout deploy\certs\key.pem -out deploy\certs\cert.pem ^
  -subj "/CN=localhost" ^
  -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"

if errorlevel 1 (
  echo FAIL: 证书生成失败
  exit /b 1
)

echo 证书已生成到 deploy\certs\key.pem 与 deploy\certs\cert.pem
