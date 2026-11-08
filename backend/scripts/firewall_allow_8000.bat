@echo off
rem 放行 8000 端口入站，真机联调用；需以管理员身份运行。
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 不是管理员，请右键本文件选择“以管理员身份运行”。
    pause
    exit /b 1
)
netsh advfirewall firewall add rule name="elder_care_8000" dir=in action=allow protocol=TCP localport=8000
echo 已放行 8000 端口入站。
pause
