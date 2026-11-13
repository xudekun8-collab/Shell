@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0.."

set START_T=%TIME%

echo [1/5] 后端 pytest
pushd backend
.venv\Scripts\python.exe -m pytest -q > "%TEMP%\elder_pytest.txt" 2>&1
if errorlevel 1 (
  echo FAIL: pytest 未通过
  type "%TEMP%\elder_pytest.txt"
  popd
  exit /b 1
)
findstr /c:"passed" "%TEMP%\elder_pytest.txt" >nul
if errorlevel 1 (
  echo FAIL: 未检测到 passed 统计行
  popd
  exit /b 1
)
popd

echo [2/5] 前端 JS 语法
for %%f in (miniprogram\pages\chat\chat.js miniprogram\pages\game\game.js miniprogram\pages\records\records.js miniprogram\pages\memory\memory.js miniprogram\pages\family\family.js miniprogram\pages\login\login.js miniprogram\utils\request.js miniprogram\utils\user.js miniprogram\utils\constants.js miniprogram\app.js) do (
  node --check "%%f" >nul 2>&1
  if errorlevel 1 (
    echo FAIL: JS 语法错误 %%f
    exit /b 1
  )
)

echo [3/5] JSON 合法性
backend\.venv\Scripts\python.exe -c "import json; [json.load(open(f,encoding='utf-8')) for f in ['miniprogram/app.json','miniprogram/sitemap.json','miniprogram/pages/chat/chat.json','miniprogram/pages/game/game.json','miniprogram/pages/records/records.json','miniprogram/pages/memory/memory.json','miniprogram/pages/family/family.json','miniprogram/pages/login/login.json']]" >nul 2>&1
if errorlevel 1 (
  echo FAIL: JSON 校验失败
  exit /b 1
)

echo [4/5] 静态红线检查
powershell -NoProfile -Command "if (Select-String -Path (Get-ChildItem miniprogram -Recurse -Include *.wxss,*.wxml).FullName -Pattern 'font-size:\s*([0-9]|1[0-9]|2[0-9])rpx') { Write-Output 'FAIL: 存在 font-size 小于 30rpx'; exit 1 }"
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "if (Select-String -Path (Get-ChildItem miniprogram -Recurse -Filter *.wxss).FullName -Pattern 'break-all') { Write-Output 'FAIL: 存在 break-all'; exit 1 }"
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "if (Select-String -Path (Get-ChildItem miniprogram -Recurse -Filter *.js | Where-Object { $_.FullName -notlike '*\login\*' }).FullName -Pattern 'demo_user_1') { Write-Output 'FAIL: 业务页面存在 demo_user_1 硬编码'; exit 1 }"
if errorlevel 1 exit /b 1

echo [5/5] 汇总
for /f "tokens=1-4 delims=:.," %%a in ("%START_T%") do set /a "ss=(((%%a*60)+1%%b %% 100)*60+1%%c %% 100)"
for /f "tokens=1-4 delims=:.," %%a in ("%TIME%") do set /a "ee=(((%%a*60)+1%%b %% 100)*60+1%%c %% 100)"
set /a "elapsed=ee-ss"
if %elapsed% lss 0 set /a "elapsed+=86400"

echo ALL CHECKS PASSED
echo 总耗时 %elapsed% 秒
endlocal
