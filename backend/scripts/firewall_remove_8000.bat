@echo off
rem 删除 8000 端口入站规则，答辩结束后清理用；需以管理员身份运行。
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 不是管理员，请右键本文件选择“以管理员身份运行”。
    pause
    exit /b 1
)
netsh advfirewall firewall delete rule name="elder_care_8000"
echo 已删除 elder_care_8000 入站规则。
pause
